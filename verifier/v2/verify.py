"""Verifier v2 — Omni Connector Hub acceptance checks.

Differs from v1: smoke-calling an action now supplies sample params for
always-live connectors (ops_*), and accepts a clean ConnectorError about
missing params as a PASS for live-mode connectors (contract only guarantees
no-arg mock calls when mock=True). v1 wrongly flagged correct behavior.

Checks:
 1. hub package imports; every connector module imports without error.
 2. Every registered connector returns a valid status() (name, mode, actions list).
 3. Missing configuration returns a typed non-executed failure without parameter echo.
 4. Every action has a complete safety classification and dry-run metadata.
 5. mcp/mcp.json is valid JSON with an mcpServers object.
 6. .env.template covers every env var any connector declares in required_env.
 7. No hard-coded secrets: grep for sk-/ghp_/AKIA-style literals outside .env*.
Exit 0 only if all pass.
"""
import importlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

fails = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(name)


# strip all hub-related env to force mock
for k in list(os.environ):
    if re.match(r"(OPENAI|ANTHROPIC|MOONSHOT|KIMI|CLOUDFLARE|EMAIL_|GOOGLE_|GMAIL_|WHMCS|WHM_|CPANEL_|HETZNER|LINODE|CONTABO|OVH_|ONEPROVIDER|ULTRAHOST|TAWK_|GITHUB_|SSH_HOSTS)", k):
        del os.environ[k]
os.environ["HUB_ALLOW_LOCAL_EXEC"] = "0"

from hub import get_connector, list_connectors, load_connectors  # noqa: E402

load_connectors()
channels = list_connectors()
check("connectors discovered", len(channels) >= 20, f"{len(channels)} registered")

REQUIRED = {
    "openai", "claude", "kimi", "cloudflare", "email", "gmail", "whmcs", "whm",
    "cpanel", "hetzner", "linode", "contabo", "ovh", "oneprovider", "ultrahost",
    "tawk", "github", "ops_ssh", "ops_browser", "ops_network", "ops_security",
}
missing = REQUIRED - set(channels)
check("all required channels present", not missing, f"missing: {sorted(missing)}")

all_env_needed = set()
for name in sorted(channels):
    try:
        conn = get_connector(name)
        st = conn.status()
        policies = st.get("action_policies", {})
        ok = (st["name"] == name and isinstance(st["actions"], list) and
              st["actions"] and set(policies) == set(st["actions"]))
        check(f"status and policies {name}", ok)
        all_env_needed.update(getattr(conn, "required_env", []))
        if conn.mock:
            marker = "sensitive-value-not-for-response"
            r = conn.call(conn.actions()[0], customer_details=marker)
            valid = (r.get("ok") is False and r.get("executed") is False and
                     r.get("state") == "configuration_required" and
                     r.get("error", {}).get("type") == "configuration_required" and
                     marker not in json.dumps(r))
            check(f"configuration failure {name}", valid)
        else:
            dry_actions = [a for a, policy in policies.items()
                           if policy["dry_run_capable"]]
            if dry_actions:
                r = conn.call(dry_actions[0], dry_run=True,
                              customer_details="must-not-be-echoed")
                check(f"dry run {name}.{dry_actions[0]}",
                      r.get("ok") is False and r.get("executed") is False and
                      r.get("state") == "dry_run" and
                      "must-not-be-echoed" not in json.dumps(r))
            else:
                action = conn.actions()[0]
                r = conn.call(action, dry_run=True)
                check(f"dry run rejected {name}.{action}",
                      r.get("state") == "dry_run_not_supported")
    except Exception as e:
        check(f"connector {name}", False, str(e)[:120])

# Exercise destructive authorization without contacting an upstream service.
os.environ["HETZNER_API_TOKEN"] = "verifier-non-secret"
hetzner = get_connector("hetzner")
blocked = hetzner.call("delete_server", id=1)
check("destructive action requires confirmation",
      blocked.get("state") == "confirmation_required" and
      blocked.get("executed") is False and blocked.get("ok") is False)
preview = hetzner.call("delete_server", id=1, dry_run=True)
check("destructive dry run does not require confirmation or execute",
      preview.get("state") == "dry_run" and preview.get("executed") is False and
      preview.get("ok") is False)
del os.environ["HETZNER_API_TOKEN"]

try:
    with open(os.path.join(ROOT, "mcp/mcp.json")) as f:
        cfg = json.load(f)
    check("mcp.json valid", isinstance(cfg.get("mcpServers"), dict) and cfg["mcpServers"])
except Exception as e:
    check("mcp.json valid", False, str(e))

with open(os.path.join(ROOT, ".env.template")) as f:
    template = f.read()
uncovered = {v for v in all_env_needed if v not in template}
check(".env.template covers required_env", not uncovered, f"missing: {sorted(uncovered)}")

secret_pat = re.compile(r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})")
leaks = []
for dirpath, _d, files in os.walk(ROOT):
    if ".env" in dirpath or "verifier/runs" in dirpath:
        continue
    for fn in files:
        if fn.endswith((".py", ".md", ".json", ".txt")) and fn != ".env":
            p = os.path.join(dirpath, fn)
            try:
                if secret_pat.search(open(p, errors="ignore").read()):
                    leaks.append(p)
            except OSError:
                pass
check("no hard-coded secrets", not leaks, str(leaks))

print(f"\nRESULT: {'FAIL' if fails else 'PASS'} ({len(fails)} failed checks)")
if fails:
    for f in fails:
        print(f"  - {f}")
sys.exit(1 if fails else 0)
