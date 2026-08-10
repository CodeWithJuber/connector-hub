# Digest verified from Docker Hub's registry manifest on 2026-08-10.
FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

RUN groupadd --system --gid 10001 hub && useradd --system --uid 10001 --gid hub hub
RUN pip install --no-cache-dir uv==0.8.4
COPY pyproject.toml uv.lock README.md ./
COPY hub ./hub
COPY connectors ./connectors
RUN uv sync --frozen --no-dev --no-editable && pip uninstall -y uv && chown -R hub:hub /app

USER 10001:10001
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["connector-hub", "health"]
ENTRYPOINT ["connector-hub"]
CMD ["mcp"]
