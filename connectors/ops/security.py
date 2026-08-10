"""Server security audit connector (stdlib only).

Always allowed (no gate): audit_password_strength, check_ssl, generate_secret.
Gated behind HUB_ALLOW_LOCAL_EXEC=1: scan_common_exposure (outbound socket
probing of risky ports) and ssh_config_audit (reads local sshd_config).

required_env=[] — never in mock mode; no external service credentials needed.
Passwords/secrets passed in are never echoed back.
"""
import math
import os
import re
import secrets
import socket
import ssl
import string
from datetime import datetime, timezone

from hub.base import BaseConnector, ConnectorError, register

RISKY_PORTS = {21: "ftp", 23: "telnet", 3306: "mysql", 6379: "redis", 27017: "mongodb"}
SSHD_CONFIG_DEFAULT = "/etc/ssh/sshd_config"


@register
class OpsSecurityConnector(BaseConnector):
    name = "ops_security"
    required_env = []
    description = "Password audit, SSL cert check, exposure scan, sshd audit, secret gen"

    def __init__(self, config=None):
        super().__init__(config)
        self.mock = False
        self.missing_env = []

    read_only_actions = frozenset(['audit_password_strength', 'check_ssl', 'scan_common_exposure', 'ssh_config_audit', 'generate_secret'])
    mutating_actions = frozenset([])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset([])

    def actions(self):
        return [
            "audit_password_strength",
            "check_ssl",
            "scan_common_exposure",
            "ssh_config_audit",
            "generate_secret",
        ]

    def _exec_allowed(self):
        return self.env("HUB_ALLOW_LOCAL_EXEC") == "1"

    def _gated(self, action):
        return {
            "ok": False,
            "executed": False,
            "state": "policy_required",
            "gated": True,
            "action": action,
            "note": "blocked: set HUB_ALLOW_LOCAL_EXEC=1 to enable local/socket ops",
        }

    # --- password audit -------------------------------------------------------
    @staticmethod
    def _entropy_bits(pw):
        pool = 0
        if re.search(r"[a-z]", pw):
            pool += 26
        if re.search(r"[A-Z]", pw):
            pool += 26
        if re.search(r"\d", pw):
            pool += 10
        if re.search(r"[^a-zA-Z0-9]", pw):
            pool += 33
        if pool == 0:
            return 0.0
        return round(len(pw) * math.log2(pool), 1)

    def _audit_pw(self, pw):
        issues = []
        if len(pw) < 12:
            issues.append("length < 12 characters")
        if not re.search(r"[a-z]", pw):
            issues.append("no lowercase letters")
        if not re.search(r"[A-Z]", pw):
            issues.append("no uppercase letters")
        if not re.search(r"\d", pw):
            issues.append("no digits")
        if not re.search(r"[^a-zA-Z0-9]", pw):
            issues.append("no symbols")
        if re.search(r"(.)\1{2,}", pw):
            issues.append("contains 3+ repeated characters")
        lowered = pw.lower()
        for word in ("password", "qwerty", "letmein", "admin", "welcome", "123456"):
            if word in lowered:
                issues.append(f"contains common word/pattern '{word}'")
        entropy = self._entropy_bits(pw)
        score = "strong" if entropy >= 70 and not issues else (
            "moderate" if entropy >= 45 else "weak"
        )
        # Never echo the password itself back.
        return {
            "ok": True,
            "length": len(pw),
            "entropy_bits": entropy,
            "score": score,
            "issues": issues,
        }

    # --- live actions ----------------------------------------------------------
    def _live(self, action, **params):
        if action == "audit_password_strength":
            pw = params.get("password")
            if pw is None:
                raise ConnectorError(f"{self.name}: 'password' is required")
            return self._audit_pw(str(pw))

        if action == "check_ssl":
            domain = params.get("domain")
            if not domain:
                raise ConnectorError(f"{self.name}: 'domain' is required")
            port = int(params.get("port", 443))
            ctx = ssl.create_default_context()
            try:
                with socket.create_connection((domain, port), timeout=10) as sock:
                    with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                        cert = ssock.getpeercert()
            except ssl.SSLCertVerificationError as e:
                return {"ok": False, "domain": domain, "port": port,
                        "error": f"certificate verification failed: {e}"}
            except (socket.timeout, socket.gaierror, OSError) as e:
                raise ConnectorError(f"{self.name}: ssl check failed {domain}:{port}: {e}")
            not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            not_after = not_after.replace(tzinfo=timezone.utc)
            days_left = (not_after - datetime.now(timezone.utc)).days
            issuer = dict(x[0] for x in cert.get("issuer", ()))
            sans = [v for t, v in cert.get("subjectAltName", ()) if t == "DNS"]
            return {
                "ok": True,
                "domain": domain,
                "port": port,
                "issuer": issuer.get("organizationName") or issuer.get("commonName"),
                "expires": not_after.date().isoformat(),
                "days_until_expiry": days_left,
                "expired": days_left < 0,
                "subject_alt_names": sans,
            }

        if action == "scan_common_exposure":
            host = params.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: 'host' is required")
            if not self._exec_allowed():
                return self._gated(action)
            open_ports = []
            for port, service in RISKY_PORTS.items():
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                try:
                    if s.connect_ex((host, port)) == 0:
                        open_ports.append({"port": port, "service": service})
                finally:
                    s.close()
            return {
                "ok": True,
                "host": host,
                "risky_ports_checked": sorted(RISKY_PORTS),
                "exposed": open_ports,
                "warning": ("risky service(s) reachable from network — "
                            "restrict firewall/bind address") if open_ports else None,
            }

        if action == "ssh_config_audit":
            if not self._exec_allowed():
                return self._gated(action)
            path = params.get("path") or SSHD_CONFIG_DEFAULT
            if not os.path.isfile(path) or not os.access(path, os.R_OK):
                return {
                    "ok": True,
                    "path": path,
                    "readable": False,
                    "note": "sshd_config not readable (need root or custom path)",
                }
            settings = {}
            with open(path, "r", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(None, 1)
                    if len(parts) == 2:
                        settings[parts[0].lower()] = parts[1].strip()
            findings = []
            if settings.get("permitrootlogin", "").lower() == "yes":
                findings.append("PermitRootLogin yes — disable root SSH login")
            if settings.get("passwordauthentication", "").lower() == "yes":
                findings.append("PasswordAuthentication yes — prefer key-only auth")
            return {
                "ok": True,
                "path": path,
                "readable": True,
                "permit_root_login": settings.get("permitrootlogin"),
                "password_authentication": settings.get("passwordauthentication"),
                "findings": findings,
                "hardened": not findings,
            }

        if action == "generate_secret":
            length = int(params.get("length", 32))
            if length < 8:
                raise ConnectorError(f"{self.name}: length must be >= 8")
            alphabet = string.ascii_letters + string.digits + "-_"
            secret = "".join(secrets.choice(alphabet) for _ in range(length))
            return {"ok": True, "length": length, "secret": secret}

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
