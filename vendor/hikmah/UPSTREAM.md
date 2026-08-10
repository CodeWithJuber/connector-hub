# Vendored upstream record

- Upstream: https://github.com/hikmahlabs/plugins
- Immutable revision: `f028fb87ecb64de0e284b3b233150da41d938ebf`
- Retrieved: 2026-08-10
- License: MIT (see `LICENSE`)
- Integrity: the files in this directory are a source snapshot of that Git
  revision, excluding only `.git/`; updates replace the snapshot after review.

This is instruction/documentation source, not executable Connector Hub code.
The Hub does not load it at runtime. Its native formats are Claude Code
marketplace `plugin.json`, skills (`SKILL.md` plus references), and commands.
Those formats are not accepted by `hub.plugins.PluginLoader`; a reviewed local
adapter and Connector Hub `plugin-manifest.json` would be required.
