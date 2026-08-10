from hub.base import ConnectorError


def test_error_normalization_is_stable() -> None:
    error = ConnectorError("try later", code="rate_limited", retryable=True, status=429)
    assert error.as_dict() == {
        "ok": False,
        "error": {"code": "rate_limited", "message": "try later", "retryable": True, "status": 429},
    }
