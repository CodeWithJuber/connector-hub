from connectors.cloud.hetzner import HetznerConnector


def test_hetzner_constructs_documented_read_url(monkeypatch) -> None:
    monkeypatch.setenv("HETZNER_API_TOKEN", "test-process-only")
    connector = HetznerConnector()
    captured = {}

    def http_json(method, url, headers=None, payload=None, **kwargs):
        captured.update(method=method, url=url, headers=headers, payload=payload)
        return {"ok": True}

    monkeypatch.setattr(connector, "http_json", http_json)
    connector.call("list_locations")
    assert captured["method"] == "GET"
    assert captured["url"] == "https://api.hetzner.cloud/v1/locations"
    assert captured["headers"]["Authorization"] == "Bearer test-process-only"
