from hub.base import BaseConnector


def test_nested_secret_values_are_redacted() -> None:
    value = {"api_token": "private", "nested": [{"password": "private"}], "safe": "visible"}
    redacted = BaseConnector()._redact(value)
    assert redacted == {"api_token": "***", "nested": [{"password": "***"}], "safe": "visible"}
