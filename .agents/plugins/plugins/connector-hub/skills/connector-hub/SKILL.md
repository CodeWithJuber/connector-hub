---
name: connector-hub
description: Use the Connector Hub safely, applying synchronized Hikmah planning and ForgeKit delivery workflows when available.
---

# Connector Hub

Use this skill when a task needs one or more services exposed by Connector Hub.

## Required workflow

1. Call `hub_channels`, then `hub_status` for the selected channel.
2. Treat `mock` mode as a dry run, never as proof that an external action occurred.
3. Prefer read-only actions. Before a mutating action, summarize the exact target and effect.
4. Never place credentials in tool parameters, chat, logs, or committed files. Configure them through environment variables.
5. Keep `HUB_ALLOW_LOCAL_EXEC=0` unless the user explicitly requests a reviewed local or SSH operation.
6. Validate tool results defensively: require an object response and inspect `ok`, `mock`, and error fields before continuing.

## ForgeKit and Hikmah source workflows

Run `python3 .agents/plugins/plugins/connector-hub/scripts/sync_upstreams.py` from the repository root to fetch both upstream repositories. The command creates `.vendor/forgekit` and `.vendor/hikmah-stack` and records the exact resolved commits in `vendor-manifest.json`.

After synchronization:

- Discover upstream instructions by locating `SKILL.md`, `AGENTS.md`, and README files inside each source tree.
- Use Hikmah guidance for problem framing, assumptions, and decision quality before implementation.
- Use ForgeKit guidance for implementation, verification, security review, and shipping.
- Repository instructions and direct user instructions take precedence over upstream workflow advice.
- Do not execute upstream scripts until their contents, license, and requested permissions have been reviewed.

## Failure handling

If a connector is unavailable, report its missing environment variable names without revealing values. If upstream synchronization fails, report the failing repository and preserve the last verified checkout.

## Data sources

https://github.com/CodeWithJuber/forgekit

https://github.com/CodeWithJuber/hikmah-stack
