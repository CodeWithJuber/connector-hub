import json

import httpx

from hub.http_client import SharedHttpClient, UpstreamError


def test_conditional_get_and_bounded_cache():
    seen = []
    def handler(request):
        seen.append(request)
        if request.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, headers={"etag": '"v1"'}, json={"current": True})
    client = SharedHttpClient(cache_ttl=60)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    assert client.request_json("public", "GET", "https://example.com/data")["data"] == {"current": True}
    assert client.request_json("public", "GET", "https://example.com/data")["cached"] is True
    assert len(seen) == 2


def test_credentials_disable_cache_and_body_is_bounded():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"12345")
    client = SharedHttpClient(max_body_bytes=4)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(UpstreamError, match="response_too_large"):
        client.request_json("private", "GET", "https://example.com", headers={"Authorization": "secret"})


import pytest
