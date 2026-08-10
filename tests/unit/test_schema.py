import pytest
from pydantic import ValidationError

from hub.schema import ConnectorRequest, JsonRpcRequest


def test_connector_request_rejects_unknown_and_malformed_fields() -> None:
    with pytest.raises(ValidationError):
        ConnectorRequest.model_validate({"channel": "../bad", "action": "read", "extra": True})


def test_json_rpc_requires_supported_version() -> None:
    with pytest.raises(ValidationError):
        JsonRpcRequest.model_validate({"jsonrpc": "1.0", "method": "ping"})
