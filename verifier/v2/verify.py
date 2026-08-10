"""Verifier v2 — Omni Connector Hub acceptance checks.

Differs from v1: smoke-calling an action now supplies sample params for
always-live connectors (ops_*), and accepts a clean ConnectorError about
missing params as a PASS for live-mode connectors (contract only guarantees
no-arg mock calls when mock=True). v1 wrongly flagged correct behavior.

Checks:
 1. hub package imports; every connector module imports without error.
 2. Every registered connector returns a valid status() (name, mode, actions list).
 3. Mock-mode call() works with env stripped (no credentials) for every connector.
 4. mcp/mcp.json is valid JSON with an mcpServers object.
 5. .env.template covers every env var any connector declares in required_env.
 6. No hard-coded secrets: grep for sk-/ghp_/AKIA-style literals outside .env*.
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

SAMPLES = {
    "ops_browser": {"fetch": {"url": "https://example.com"}},
    "ops_network": {"dns_lookup": {"domain": "example.com"}},
    "ops_security": {"generate_secret": {}},
}

all_env_needed = set()
for name in sorted(channels):
    try:
        conn = get_connector(name)
        st = conn.status()
        ok = st["name"] == name and isinstance(st["actions"], list) and st["actions"]
        check(f"status() {name}", ok)
        all_env_needed.update(getattr(conn, "required_env", []))
        if conn.actions():
            sample = SAMPLES.get(name, {})
            action = next(iter(sample), conn.actions()[0])
            try:
                r = conn.call(action, **sample.get(action, {}))
                check(f"smoke call {name}.{action}", r.get("ok") is True)
            except Exception as e:
                # live-mode connectors may legitimately demand params/network
                check(f"smoke call {name}.{action}", not conn.mock and "required" in str(e),
                      str(e)[:100])
    except Exception as e:
        check(f"connector {name}", False, str(e)[:120])

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
