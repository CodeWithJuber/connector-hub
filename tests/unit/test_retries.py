import io
import urllib.error

import pytest

from hub.base import BaseConnector, ConnectorError


class Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return b'{"result":"public"}'


def test_get_retries_transient_failure(monkeypatch) -> None:
    calls = 0

    def open_request(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.URLError("temporary")
        return Response()

    monkeypatch.setattr("hub.base.urllib.request.urlopen", open_request)
    monkeypatch.setattr("hub.base.time.sleep", lambda _: None)
    result = BaseConnector().http_json("GET", "https://example.com/public", base_delay=0)
    assert calls == 2
    assert result["data"]["result"] == "public"


def test_post_does_not_retry_server_error(monkeypatch) -> None:
    calls = 0

    def open_request(request, timeout):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, io.BytesIO(b"busy"))

    monkeypatch.setattr("hub.base.urllib.request.urlopen", open_request)
    with pytest.raises(ConnectorError):
        BaseConnector().http_json("POST", "https://example.com", payload={})
    assert calls == 1
