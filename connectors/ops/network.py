"""Policy-constrained network diagnostics connector."""
import shutil
import socket
import ssl

from hub.base import BaseConnector, ConnectorError, register
from hub.security import SecurityError, SecurityPolicy, bounded_run, pinned_urlopen

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
        self.security = SecurityPolicy(self.config)

    read_only_actions = frozenset(['ping', 'dns_lookup', 'port_check', 'traceroute', 'http_headers'])
    mutating_actions = frozenset([])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset([])

    def actions(self):
        return ["ping", "dns_lookup", "port_check", "traceroute", "http_headers"]

    def _exec_allowed(self):
        return self.env("HUB_ALLOW_LOCAL_EXEC") == "1"

    def _gated(self, action):
        return {
            "ok": False,
            "executed": False,
            "state": "policy_required",
            "gated": True,
            "action": action,
            "note": "system command blocked: set HUB_ALLOW_LOCAL_EXEC=1 to enable",
        }
    def _authorize_exec(self, action, approval):
        self.security.require_capability(self.name, "local_exec", action, approval, True)

    # --- live actions --------------------------------------------------------
    def _live(self, action, **params):
        if action == "ping":
            host = params.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: 'host' is required")
            try:
                self._authorize_exec(action, params.get("approval"))
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")
            count = int(params.get("count", 4))
            if count < 1 or count > 10:
                raise ConnectorError(f"{self.name}: count must be between 1 and 10")
            addresses = self.security.resolve_host(host, 0, socket.SOCK_RAW)
            try:
                proc = bounded_run(["ping", "-c", str(count), "-W", "5", addresses[0]],
                                   count * 5 + 10, self.security.max_output)
            except FileNotFoundError:
                raise ConnectorError(f"{self.name}: system 'ping' binary not found")
            except SecurityError:
                raise ConnectorError(f"{self.name}: ping to {host} timed out")
            return {
                "ok": proc["returncode"] == 0,
                "host": host,
                "count": count,
                "exit_code": proc["returncode"], "stdout": proc["stdout"],
                "stderr": proc["stderr"], "truncated": proc["truncated"],
            }

        if action == "dns_lookup":
            domain = params.get("domain")
            if not domain:
                raise ConnectorError(f"{self.name}: 'domain' is required")
            try:
                addresses = self.security.resolve_host(domain, 0)
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")
            families = sorted({"AF_INET6" if ":" in a else "AF_INET" for a in addresses})
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
                if port not in self.security.ports:
                    raise ConnectorError(f"{self.name}: port {port} is not allowed")
                addresses = self.security.resolve_host(host, port)
                family = socket.AF_INET6 if ":" in addresses[0] else socket.AF_INET
                s = socket.socket(family, socket.SOCK_STREAM)
                s.settimeout(5)
                try:
                    results[str(port)] = s.connect_ex((addresses[0], port)) == 0
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
            try:
                self._authorize_exec(action, params.get("approval"))
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")
            address = self.security.resolve_host(host, 0, socket.SOCK_RAW)[0]
            if not shutil.which("traceroute"):
                return {
                    "ok": False,
                    "executed": False,
                    "state": "dependency_required",
                    "host": host,
                    "note": "system 'traceroute' binary not installed",
                    "hops": [],
                }
            proc = bounded_run(["traceroute", "-m", "20", "-w", "3", address],
                               90, self.security.max_output)
            return {
                "ok": proc["returncode"] == 0,
                "host": host,
                "exit_code": proc["returncode"], "stdout": proc["stdout"],
                "stderr": proc["stderr"], "truncated": proc["truncated"],
            }

        if action == "http_headers":
            url = params.get("url")
            if not url:
                raise ConnectorError(f"{self.name}: 'url' is required")
            try:
                resp = pinned_urlopen(self.security, url, headers={"User-Agent": USER_AGENT},
                                      timeout=20, max_bytes=64 * 1024)
                return {"ok": resp["status"] < 400, "url": resp["url"],
                        "status": resp["status"], "headers": resp["headers"]}
            except (OSError, SecurityError, ssl.SSLError) as e:
                raise ConnectorError(f"{self.name}: http_headers failed {url}: {e}")

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
