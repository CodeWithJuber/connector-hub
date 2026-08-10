import pytest
from pydantic import ValidationError

from hub import get_connector, load_connectors
from hub.mcp_server import _tools
from hub.schemas import validate_action


@pytest.fixture(scope="module", autouse=True)
def connectors():
    load_connectors()


def test_every_action_has_strict_mcp_schema():
    tools = _tools()
    action_tools = {t["name"]: t for t in tools if "__" in t["name"]}
    for channel in ("hetzner", "github", "ops_network"):
        conn = get_connector(channel)
        for action in conn.actions():
            assert action_tools[f"{channel}__{action}"]["inputSchema"]["additionalProperties"] is False


def test_required_and_unknown_fields_rejected_before_mock_operation():
    conn = get_connector("hetzner")
    with pytest.raises(ValidationError):
        validate_action(conn, "create_server", {"name": "n"})
    with pytest.raises(ValidationError):
        validate_action(conn, "list_servers", {"surprise": True})


def test_ranges_and_formats():
    with pytest.raises(ValidationError):
        validate_action(get_connector("ops_network"), "port_check", {"host": "example.com", "ports": "invalid"})
    with pytest.raises(ValidationError):
        validate_action(get_connector("ops_browser"), "fetch", {"url": "not a URL"})


def test_schema_secret_is_redactable():
    conn = get_connector("email")
    schema = next(t for t in _tools() if t["name"] == "email__send_email")["inputSchema"]
    assert schema["properties"]["body"]["format"] == "password"
