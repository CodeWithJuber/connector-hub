# plan.md — Omni Connector Hub (MCP + API channel)

## Objective
Create a unified "connector hub" the user can drop into their agent setup:
1. **MCP config pack** — ready-to-use MCP server definitions (GitHub, email, browser, filesystem, ssh, etc.)
2. **API connector library** — typed Python clients for: LLM providers (OpenAI/ChatGPT, Anthropic/Claude, Kimi, Cloudflare Workers AI), Email (multi-Gmail OAuth + IMAP/SMTP), WHMCS, WHM/cPanel, Contabo, OVH, Linode, Hetzner, OneProvider, UltaHost, tawk.to REST.
3. **Channel gateway** — one CLI/module that routes a task to the right connector ("channel").
4. **Security layer** — env-based secret management, OAuth flow scaffolding, permission scoping.

## Skills referenced (user) — read at Stage 0
- /app/.user/skills/agent-playbook, principles-playbook, cognitive-kernel, ship-guard, decision-forge
- /app/.user/skills/hikmah-problem-solver (default framework per standing instruction)

## Stages
- **Stage 0 — Load skills**: read user SKILL.md files; extract workflow rules to apply.
- **Stage 1 — Architecture**: Orchestrator designs hub layout, auth model, connector interface contract. Output: ARCHITECTURE.md + repo skeleton.
- **Stage 2 — Connectors (parallel subagents, coder type)**:
  - A: LLM providers (openai, anthropic, kimi/moonshot, cloudflare)
  - B: Email multi-account (Gmail OAuth2 + generic IMAP/SMTP), contacts/send/read
  - C: Hosting panels (WHMCS API, WHM/cPanel UAPI/API2)
  - D: Cloud VPS providers (contabo, ovh, linode, hetzner, oneprovider, ultrahost)
  - E: tawk.to REST + ops connectors (ssh/bash, browser, network, security audit)
  - F: GitHub full-permission connector (REST + gh CLI passthrough)
- **Stage 3 — Gateway + MCP pack**: channel router CLI, `mcp.json`/`claude_desktop_config` pack, .env.template, setup docs.
- **Stage 4 — Verify + package**: verifier/ folder, smoke tests (import + mock-mode), README, zip deliverable.

## Verifier criteria (v1)
- Every connector module imports cleanly (`python -c "import ..."`).
- Every connector works in MOCK mode without credentials (dry-run returns structured stub).
- `.env.template` lists every secret the hub references; no real secrets in repo.
- mcp.json is valid JSON.
- README covers install + per-service credential setup.
