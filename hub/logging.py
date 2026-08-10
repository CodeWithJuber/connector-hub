"""Structured JSON logging and schema-aware redaction."""

import sys
from typing import Any

import structlog

SENSITIVE_HEADERS = {"authorization", "proxy-authorization", "cookie", "set-cookie", "x-api-key"}

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)
log = structlog.get_logger("connector_hub")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: "[REDACTED]" if k.lower() in SENSITIVE_HEADERS else v for k, v in headers.items()}


def redact_fields(data: dict[str, Any], secret_fields: set[str]) -> dict[str, Any]:
    return {k: "[REDACTED]" if k in secret_fields else v for k, v in data.items()}
