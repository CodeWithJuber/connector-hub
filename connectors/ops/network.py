"""Network diagnostics connector.

Socket-based checks (dns_lookup, port_check, http_headers) are read-only and
run without any gate. System commands (ping, traceroute) shell out to local
binaries and are gated behind HUB_ALLOW_LOCAL_EXEC=1; without the gate they
return a structured gated note instead of executing.

required_env=[] — always live for socket checks.
"""
import shutil
import socket
import ssl
import subprocess
import urllib.request
import urllib.error

from hub.base import BaseConnector, ConnectorError, register

COMMON_PORTS = [22, 80, 443, 2083, 2087]
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@register
class OpsNetworkConnector(BaseConnector):
    name = "ops_network"
    required_env = []
    description = "ping / dns / port / traceroute / header diagnostics"

    def __init__(self, config=None):
        super().__init__(config)
        self.mock = False
        self.missing_env = []

    def actions(self):
        return ["ping", "dns_lookup", "port_check", "traceroute", "http_headers"]

    def _exec_allowed(self):
        return self.env("HUB_ALLOW_LOCAL_EXEC") == "1"

    def _gated(self, action):
        return {
            "ok": True,
            "gated": True,
            "action": action,
            "note": "system command blocked: set HUB_ALLOW_LOCAL_EXEC=1 to enable",
        }

    # --- live actions --------------------------------------------------------
    def _live(self, action, **params):
        if action == "ping":
            host = params.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: 'host' is required")
            if not self._exec_allowed():
                return self._gated(action)
            count = int(params.get("count", 4))
            try:
                proc = subprocess.run(
                    ["ping", "-c", str(count), "-W", "5", host],
                    capture_output=True, text=True, timeout=count * 5 + 10,
                )
            except FileNotFoundError:
                raise ConnectorError(f"{self.name}: system 'ping' binary not found")
            except subprocess.TimeoutExpired:
                raise ConnectorError(f"{self.name}: ping to {host} timed out")
            return {
                "ok": proc.returncode == 0,
                "host": host,
                "count": count,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }

        if action == "dns_lookup":
            domain = params.get("domain")
            if not domain:
                raise ConnectorError(f"{self.name}: 'domain' is required")
            try:
                infos = socket.getaddrinfo(domain, None)
            except socket.gaierror as e:
                return {"ok": False, "domain": domain, "error": str(e)}
            addresses = sorted({info[4][0] for info in infos})
            families = sorted({socket.AddressFamily(i[0]).name for i in infos})
            return {"ok": True, "domain": domain, "addresses": addresses,
                    "families": families}

        if action == "port_check":
            host = params.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: 'host' is required")
            ports = params.get("ports") or COMMON_PORTS
            results = {}
            for port in ports:
                port = int(port)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                try:
                    results[str(port)] = s.connect_ex((host, port)) == 0
                except socket.gaierror as e:
                    raise ConnectorError(f"{self.name}: cannot resolve {host}: {e}")
                finally:
                    s.close()
            return {"ok": True, "host": host, "ports": results,
                    "open": [int(p) for p, is_open in results.items() if is_open]}

        if action == "traceroute":
            host = params.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: 'host' is required")
            if not self._exec_allowed():
                return self._gated(action)
            if not shutil.which("traceroute"):
                return {
                    "ok": True,
                    "host": host,
                    "note": "system 'traceroute' binary not installed",
                    "hops": [],
                }
            proc = subprocess.run(
                ["traceroute", "-m", "20", "-w", "3", host],
                capture_output=True, text=True, timeout=90,
            )
            return {
                "ok": proc.returncode == 0,
                "host": host,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }

        if action == "http_headers":
            url = params.get("url")
            if not url:
                raise ConnectorError(f"{self.name}: 'url' is required")
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", USER_AGENT)
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return {
                        "ok": True,
                        "url": url,
                        "status": resp.status,
                        "headers": dict(resp.headers.items()),
                    }
            except urllib.error.HTTPError as e:
                return {
                    "ok": e.code < 400,
                    "url": url,
                    "status": e.code,
                    "headers": dict(e.headers.items()) if e.headers else {},
                }
            except (urllib.error.URLError, socket.timeout, TimeoutError,
                    ssl.SSLError) as e:
                raise ConnectorError(f"{self.name}: http_headers failed {url}: {e}")

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
