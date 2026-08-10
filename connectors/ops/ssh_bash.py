"""Allowlisted local argv and remote SSH action execution.

Both modes require a per-plugin capability, an allowlisted action definition,
a deployment-approved destructive action, and an approval identifier. No local
command is interpreted by a shell. Key material is referenced by path only.
"""
import json
import os
import re
import shlex

from hub.base import BaseConnector, ConnectorError, register
from hub.security import SecurityError, SecurityPolicy, bounded_run

LOCAL_TIMEOUT = 60
SSH_CONNECT_TIMEOUT = 10


@register
class OpsSshConnector(BaseConnector):
    name = "ops_ssh"
    required_env = []  # gate is enforced manually in __init__
    description = "Local bash and remote SSH command runner (gated)"

    def __init__(self, config=None):
        super().__init__(config)
        self.mock = False
        self.missing_env = []
        self.security = SecurityPolicy(self.config)

    read_only_actions = frozenset(['list_hosts'])
    mutating_actions = frozenset(['run_local', 'run_ssh'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['run_local', 'run_ssh'])

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

    def _action_argv(self, action_id, args, remote=False):
        cfg = self.security.plugin(self.name)
        definitions = cfg.get("remote_actions" if remote else "local_actions", {})
        definition = definitions.get(action_id)
        if not isinstance(definition, dict):
            raise SecurityError(f"{self.name}: action_id '{action_id}' is not allowlisted")
        executable = definition.get("executable")
        if not isinstance(executable, str) or (not remote and not os.path.isabs(executable)):
            raise SecurityError("allowlisted executable must be an absolute path")
        if not isinstance(args, list) or not all(isinstance(v, str) for v in args):
            raise SecurityError("args must be a string array")
        if len(args) > int(definition.get("max_args", 16)):
            raise SecurityError("too many command arguments")
        pattern = re.compile(definition.get("arg_pattern", r"^[A-Za-z0-9_./:@%+=,-]{1,256}$"))
        if any(not pattern.fullmatch(v) for v in args):
            raise SecurityError("command argument contains disallowed characters")
        fixed = definition.get("fixed_args", [])
        if not isinstance(fixed, list) or not all(isinstance(v, str) for v in fixed):
            raise SecurityError("fixed_args must be a string array")
        return [executable] + fixed + args

    def _authorized_argv(self, params, remote=False):
        action_id = params.get("action_id")
        if not action_id:
            raise SecurityError("'action_id' is required")
        self.security.require_capability(self.name, "ssh_exec" if remote else "local_exec",
                                         action_id, params.get("approval"), True)
        return action_id, self._action_argv(action_id, params.get("args", []), remote)

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
            try:
                action_id, argv = self._authorized_argv(params)
                timeout = int(params.get("timeout", LOCAL_TIMEOUT))
                if timeout < 1 or timeout > LOCAL_TIMEOUT:
                    raise SecurityError(f"timeout must be between 1 and {LOCAL_TIMEOUT} seconds")
                proc = bounded_run(argv, timeout,
                                   self.security.max_output)
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")
            return {
                "ok": proc["returncode"] == 0, "action_id": action_id,
                "exit_code": proc["returncode"], "stdout": proc["stdout"],
                "stderr": proc["stderr"], "truncated": proc["truncated"],
            }

        if action == "run_ssh":
            host_id = params.get("host_id")
            if not host_id:
                raise ConnectorError(f"{self.name}: 'host_id' is required")
            try:
                action_id, remote_argv = self._authorized_argv(params, remote=True)
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")
            h = self._find_host(host_id)
            user = h.get("user", "root")
            host = h.get("host")
            if not host:
                raise ConnectorError(f"{self.name}: host '{host_id}' has no 'host' field")
            port = int(h.get("port", 22))
            if port not in self.security.ports:
                raise ConnectorError(f"{self.name}: SSH port {port} is not allowed")
            address = self.security.resolve_host(host, port)[0]
            ssh_cmd = [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT}",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"HostKeyAlias={host}",
                "-p", str(port),
            ]
            key_path = h.get("key_path")
            expanded_key = None
            if key_path:
                expanded_key = os.path.expanduser(key_path)
                ssh_cmd += ["-i", expanded_key]
            remote_command = " ".join(shlex.quote(v) for v in remote_argv)
            ssh_cmd += [f"{user}@{address}", remote_command]
            try:
                proc = bounded_run(ssh_cmd, LOCAL_TIMEOUT, self.security.max_output,
                                   secrets=(expanded_key,))
            except FileNotFoundError:
                raise ConnectorError(f"{self.name}: system 'ssh' binary not found")
            except SecurityError:
                raise ConnectorError(
                    f"{self.name}: ssh to '{host_id}' timed out after {LOCAL_TIMEOUT}s"
                )
            return {
                "ok": proc["returncode"] == 0,
                "host_id": host_id,
                "target": f"{user}@{host}:{port}",
                "action_id": action_id,
                "exit_code": proc["returncode"], "stdout": proc["stdout"],
                "stderr": proc["stderr"], "truncated": proc["truncated"],
            }

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
