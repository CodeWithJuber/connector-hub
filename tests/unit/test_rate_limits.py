import io
import urllib.error

from hub.base import BaseConnector, ConnectorError


def test_retry_after_is_respected(monkeypatch) -> None:
    sleeps = []

    def open_request(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 429, "limited", {"Retry-After": "2"}, io.BytesIO(b"limited")
        )

    monkeypatch.setattr("hub.base.urllib.request.urlopen", open_request)
    monkeypatch.setattr("hub.base.time.sleep", sleeps.append)
    try:
        BaseConnector().http_json("GET", "https://example.com", max_attempts=2)
    except ConnectorError as exc:
        assert exc.code == "rate_limited"
    assert sleeps == [2.0]
