"""Hardened shared HTTP transport with conditional GET caching."""
from __future__ import annotations

import email.utils
import json
import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

import httpx

from .logging import log, redact_headers


class UpstreamError(RuntimeError):
    """Normalized, actionable upstream failure safe to display to callers."""

    def __init__(self, provider: str, category: str, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(f"{provider}: {category}: {message}")
        self.provider, self.category, self.status, self.retryable = provider, category, status, retryable


@dataclass
class CacheEntry:
    data: Any
    status: int
    etag: str | None
    last_modified: str | None
    expires: float


class SharedHttpClient:
    """Thread-safe transport. Cache keys intentionally exclude all headers."""

    RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
    IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}

    def __init__(self, *, max_body_bytes: int = 2_000_000, cache_entries: int = 128, cache_ttl: float = 300, concurrency: int = 8, attempts: int = 4):
        self.max_body_bytes, self.cache_entries, self.cache_ttl, self.attempts = max_body_bytes, cache_entries, cache_ttl, attempts
        self._client = httpx.Client(timeout=httpx.Timeout(connect=5, read=30, write=30, pool=5), limits=httpx.Limits(max_connections=100, max_keepalive_connections=20), follow_redirects=False)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._limits: dict[str, threading.BoundedSemaphore] = {}
        self._limit_lock = threading.Lock()
        self._concurrency = concurrency

    def _semaphore(self, provider: str) -> threading.BoundedSemaphore:
        with self._limit_lock:
            return self._limits.setdefault(provider, threading.BoundedSemaphore(self._concurrency))

    @staticmethod
    def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
        if response is not None and response.headers.get("Retry-After"):
            raw = response.headers["Retry-After"]
            try:
                return min(float(raw), 60)
            except ValueError:
                try:
                    return max(0, min((email.utils.parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds(), 60))
                except (TypeError, ValueError):
                    pass
        return min(0.25 * (2 ** (attempt - 1)) + random.uniform(0, 0.25), 8)

    def _cached(self, key: str) -> CacheEntry | None:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and entry.expires > time.monotonic():
                self._cache.move_to_end(key)
                return entry
            if entry:
                del self._cache[key]
        return None

    def request_json(self, provider: str, method: str, url: str, *, headers: dict[str, str] | None = None, payload: Any = None, request_id: str = "", cache_safe: bool = True, idempotency_key: str | None = None) -> dict[str, Any]:
        method, headers = method.upper(), dict(headers or {})
        safe_cache = method == "GET" and cache_safe and not payload
        cache_key = url
        cached = self._cached(cache_key) if safe_cache else None
        if cached:
            if cached.etag: headers["If-None-Match"] = cached.etag
            if cached.last_modified: headers["If-Modified-Since"] = cached.last_modified
        if idempotency_key: headers["Idempotency-Key"] = idempotency_key
        retryable_method = method in self.IDEMPOTENT or bool(idempotency_key)
        started = time.monotonic()
        with self._semaphore(provider):
            for attempt in range(1, self.attempts + 1):
                response = None
                try:
                    with self._client.stream(method, url, headers=headers, json=payload) as response:
                        if response.status_code == 304 and cached:
                            return {"ok": True, "status": cached.status, "data": cached.data, "cached": True, "attempts": attempt}
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > self.max_body_bytes:
                                raise UpstreamError(provider, "response_too_large", f"response exceeded {self.max_body_bytes} bytes", status=response.status_code)
                            chunks.append(chunk)
                        raw = b"".join(chunks)
                    if response.status_code in self.RETRYABLE_STATUS and retryable_method and attempt < self.attempts:
                        time.sleep(self._retry_delay(response, attempt)); continue
                    if response.is_error:
                        detail = raw.decode(errors="replace")[:500]
                        raise UpstreamError(provider, "http_error", f"HTTP {response.status_code}; {detail}", status=response.status_code, retryable=response.status_code in self.RETRYABLE_STATUS)
                    try: data = json.loads(raw) if raw else {}
                    except (ValueError, UnicodeDecodeError): data = {"raw": raw.decode(errors="replace")}
                    if safe_cache and not any(k.lower() in {"authorization", "cookie", "x-api-key"} for k in headers):
                        entry = CacheEntry(data, response.status_code, response.headers.get("etag"), response.headers.get("last-modified"), time.monotonic() + self.cache_ttl)
                        with self._cache_lock:
                            self._cache[cache_key] = entry; self._cache.move_to_end(cache_key)
                            while len(self._cache) > self.cache_entries: self._cache.popitem(last=False)
                    log.info("upstream_request", request_id=request_id, connector=provider, latency_ms=round((time.monotonic()-started)*1000, 2), attempt_count=attempt, upstream_status=response.status_code, headers=redact_headers(headers), upstream_host=urlsplit(url).hostname)
                    return {"ok": True, "status": response.status_code, "data": data, "attempts": attempt}
                except UpstreamError:
                    raise
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if retryable_method and attempt < self.attempts:
                        time.sleep(self._retry_delay(response, attempt)); continue
                    category = "timeout" if isinstance(exc, httpx.TimeoutException) else "network_error"
                    raise UpstreamError(provider, category, str(exc), retryable=retryable_method) from exc
        raise AssertionError("unreachable")


shared_http_client = SharedHttpClient()
