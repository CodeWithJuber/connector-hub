# Contributing

## Development workflow

1. Create a focused branch from `main` and never commit credentials or `.env` files.
2. Install the reproducible environment with `uv sync --frozen --all-groups`.
3. Add or update tests with each behavior change. Keep real-network tests marked `integration` and gated by `RUN_INTEGRATION=1`.
4. Run the local pull-request checks:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m 'not integration'
uv build
uv run pip-audit
```

5. Open a pull request using the repository template. Describe operational impact, data sources, deployment, and rollback when applicable.

## Engineering expectations

Validate untrusted inputs at system boundaries. Network requests must use bounded timeouts, retries with exponential backoff and jitter where safe, respectful concurrency, and defensive response parsing. Do not log secrets or sensitive request bodies. Use conventional, imperative commit subjects and keep generated artifacts out of commits.
