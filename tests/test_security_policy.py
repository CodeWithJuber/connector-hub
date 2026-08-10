import os
import sys
import unittest
from unittest import mock

from hub.base import ConnectorError
from hub.security import SecurityError, SecurityPolicy, bounded_run, pinned_urlopen, redact
from connectors.ops.ssh_bash import OpsSshConnector


def addr(ip):
    family = 10 if ":" in ip else 2
    return (family, 1, 6, "", (ip, 443))


class _Response:
    def __init__(self, status, location=None, body=b""):
        self.status, self.location, self.body = status, location, body

    def getheader(self, name):
        return self.location if name == "Location" else None

    def getheaders(self):
        return []

    def read(self, amount=None):
        return self.body if amount is None else self.body[:amount]


class _Connection:
    responses = []
    targets = []

    def __init__(self, target, timeout):
        self.targets.append(target)

    def request(self, *args, **kwargs):
        pass

    def getresponse(self):
        return self.responses.pop(0)

    def close(self):
        pass


class SecurityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = SecurityPolicy({"allowed_ports": [80, 443]})

    @mock.patch("hub.security.policy.socket.getaddrinfo")
    def test_rejects_alternate_private_ip_representations(self, resolve):
        for host in ("2130706433", "0177.0.0.1", "0x7f000001"):
            resolve.return_value = [addr("127.0.0.1")]
            with self.assertRaisesRegex(SecurityError, "non-public"):
                self.policy.validate_url("http://" + host)

    @mock.patch("hub.security.policy.socket.getaddrinfo")
    def test_rejects_metadata_host_and_address(self, resolve):
        with self.assertRaisesRegex(SecurityError, "metadata"):
            self.policy.validate_url("http://metadata.google.internal/latest")
        resolve.return_value = [addr("169.254.169.254")]
        with self.assertRaisesRegex(SecurityError, "metadata"):
            self.policy.validate_url("http://metadata.attacker.example/latest")

    @mock.patch("hub.security.policy._PinnedHTTPConnection", _Connection)
    @mock.patch("hub.security.policy.socket.getaddrinfo")
    def test_redirect_target_is_revalidated(self, resolve):
        resolve.side_effect = [[addr("93.184.216.34")], [addr("127.0.0.1")]]
        _Connection.responses = [_Response(302, "http://internal.example/admin")]
        with self.assertRaisesRegex(SecurityError, "non-public"):
            pinned_urlopen(self.policy, "http://public.example")
        self.assertEqual(resolve.call_count, 2)

    @mock.patch("hub.security.policy.socket.getaddrinfo")
    def test_dns_rebinding_boundary_rejects_if_any_answer_is_private(self, resolve):
        resolve.return_value = [addr("93.184.216.34"), addr("10.0.0.1")]
        with self.assertRaisesRegex(SecurityError, "non-public"):
            self.policy.validate_url("https://example.com")

    @mock.patch("hub.security.policy.socket.getaddrinfo")
    def test_validated_addresses_are_preserved_for_connection_pinning(self, resolve):
        resolve.return_value = [addr("93.184.216.34")]
        target = self.policy.validate_url("https://example.com/path")
        resolve.return_value = [addr("93.184.216.35")]
        self.assertEqual(target.addresses, ("93.184.216.34",))

    def test_bounded_output_and_secret_redaction(self):
        result = bounded_run(
            [sys.executable, "-c", "print('token=supersecret');print('x'*1000)"],
            timeout=2, max_output=80, secrets=("supersecret",),
        )
        self.assertTrue(result["truncated"])
        self.assertNotIn("supersecret", result["stdout"])
        self.assertLessEqual(len(result["stdout"].encode()), 80)

    def test_timeout(self):
        with self.assertRaisesRegex(SecurityError, "timed out"):
            bounded_run([sys.executable, "-c", "import time;time.sleep(2)"], 1, 100)

    def test_structured_redaction(self):
        self.assertEqual(redact("Authorization: bearer-secret"), "Authorization: ***")


class ExecutionPolicyTests(unittest.TestCase):
    def config(self):
        return {"security": {
            "approvals": ["ticket-123"],
            "plugins": {"ops_ssh": {
                "capabilities": ["local_exec"],
                "destructive_actions": ["echo"],
                "local_actions": {"echo": {
                    "executable": "/bin/echo", "arg_pattern": r"^[A-Za-z0-9_-]+$"
                }},
            }},
        }}

    def test_execution_needs_explicit_approval(self):
        connector = OpsSshConnector(self.config())
        with self.assertRaisesRegex(ConnectorError, "explicit policy and approval"):
            connector.call("run_local", action_id="echo", args=["safe"])

    def test_shell_metacharacters_are_rejected(self):
        connector = OpsSshConnector(self.config())
        for argument in ("hello;id", "$(id)", "hello && id", "`id`"):
            with self.assertRaisesRegex(ConnectorError, "disallowed"):
                connector.call("run_local", action_id="echo", args=[argument],
                               approval="ticket-123")

    def test_allowlisted_argv_executes_without_shell(self):
        result = OpsSshConnector(self.config()).call(
            "run_local", action_id="echo", args=["safe"], approval="ticket-123"
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "safe\n")


if __name__ == "__main__":
    unittest.main()
