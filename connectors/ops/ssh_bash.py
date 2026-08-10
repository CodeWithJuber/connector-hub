"""Local bash + remote SSH command execution.

SAFETY GATE: real execution only happens when HUB_ALLOW_LOCAL_EXEC=1 is set in
the environment. Without it the connector is forced into mock mode regardless
of any other configuration, and call() returns the standard mock echo.

Env:
  HUB_ALLOW_LOCAL_EXEC=1   — hard gate for real execution
  SSH_HOSTS — JSON array of host entries:
    [{"id": "web1", "host": "1.2.3.4", "user": "root", "port": 22,
      "key_path": "~/.ssh/id_ed25519"}, ...]

Key material is referenced by path only; contents are never read or logged here.
"""
import json
import subprocess

from hub.base import BaseConnector, ConnectorError, register

LOCAL_TIMEOUT = 60
SSH_CONNECT_TIMEOUT = 10


@register
class OpsSshConnector(BaseConnector):
    name = "ops_ssh"
    required_env = []  # gate is enforced manually in __init__
    description = "Local bash and remote SSH command runner (gated)"

    def __init__(self, config=None):
        super().__init__(config)
        if self.env("HUB_ALLOW_LOCAL_EXEC") != "1":
            self.mock = True
            if "HUB_ALLOW_LOCAL_EXEC" not in self.missing_env:
                self.missing_env.append("HUB_ALLOW_LOCAL_EXEC=1")

    def actions(self):
        return ["run_local", "run_ssh", "list_hosts"]

    # --- helpers -----------------------------------------------------------
    def _hosts(self):
        raw = self.env("SSH_HOSTS", "").strip()
        if not raw:
            return []
        try:
            hosts = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConnectorError(f"{self.name}: SSH_HOSTS is not valid JSON: {e}")
        if not isinstance(hosts, list):
            raise ConnectorError(f"{self.name}: SSH_HOSTS must be a JSON array")
        return hosts

    def _find_host(self, host_id):
        for h in self._hosts():
            if h.get("id") == host_id:
                return h
        known = [h.get("id") for h in self._hosts()]
        raise ConnectorError(
            f"{self.name}: unknown host_id '{host_id}'. Known: {known}"
        )

    # --- live actions -------------------------------------------------------
    def _live(self, action, **params):
        if action == "list_hosts":
            # Return only non-sensitive metadata — never key contents.
            return {
                "ok": True,
                "hosts": [
                    {
                        "id": h.get("id"),
                        "host": h.get("host"),
                        "user": h.get("user"),
                        "port": h.get("port", 22),
                        "key_path_configured": bool(h.get("key_path")),
                    }
                    for h in self._hosts()
                ],
            }

        if action == "run_local":
            command = params.get("command")
            if not command:
                raise ConnectorError(f"{self.name}: 'command' is required")
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=LOCAL_TIMEOUT,
            )
            return {
                "ok": proc.returncode == 0,
                "command": command,
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }

        if action == "run_ssh":
            host_id = params.get("host_id")
            command = params.get("command")
            if not host_id or not command:
                raise ConnectorError(f"{self.name}: 'host_id' and 'command' are required")
            h = self._find_host(host_id)
            user = h.get("user", "root")
            host = h.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: host '{host_id}' has no 'host' field")
            port = int(h.get("port", 22))
            ssh_cmd = [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
                "-o", "StrictHostKeyChecking=accept-new",
                "-p", str(port),
            ]
            key_path = h.get("key_path")
            expanded_key = None
            if key_path:
                import os
                expanded_key = os.path.expanduser(key_path)
                ssh_cmd += ["-i", expanded_key]
            ssh_cmd += [f"{user}@{host}", command]
            try:
                proc = subprocess.run(
                    ssh_cmd,
                    capture_output=True,
                    text=True,
                    timeout=LOCAL_TIMEOUT,
                )
            except FileNotFoundError:
                raise ConnectorError(f"{self.name}: system 'ssh' binary not found")
            except subprocess.TimeoutExpired:
                raise ConnectorError(
                    f"{self.name}: ssh to '{host_id}' timed out after {LOCAL_TIMEOUT}s"
                )
            stdout, stderr = proc.stdout, proc.stderr
            # Redact key path from ssh's own diagnostics — key material and
            # its location are never surfaced by this connector.
            if expanded_key:
                stdout = stdout.replace(expanded_key, "***")
                stderr = stderr.replace(expanded_key, "***")
            return {
                "ok": proc.returncode == 0,
                "host_id": host_id,
                "target": f"{user}@{host}:{port}",
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
