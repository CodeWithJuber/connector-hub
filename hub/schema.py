"""Strict schemas at the untrusted CLI/MCP boundary."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectorRequest(BaseModel):
    """Validated request routed to a connector."""

    model_config = ConfigDict(extra="forbid", strict=True)

    channel: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    action: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    params: dict[str, Any] = Field(default_factory=dict)


class JsonRpcRequest(BaseModel):
    """Supported JSON-RPC request envelope."""

    model_config = ConfigDict(extra="allow", strict=True)

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = None
    method: str = Field(min_length=1, max_length=128)
    params: dict[str, Any] = Field(default_factory=dict)
