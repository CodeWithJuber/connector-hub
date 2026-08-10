import json

from hub.mcp_server import _call_tool, _text


def test_mcp_text_content_is_valid_json() -> None:
    message = _text({"ok": True})
    assert json.loads(message["content"][0]["text"]) == {"ok": True}


def test_mcp_rejects_unknown_tool() -> None:
    try:
        _call_tool("unknown", {})
    except ValueError as exc:
        assert "unknown tool" in str(exc)
