"""Anthropic Claude connector.

Env: ANTHROPIC_API_KEY (required), ANTHROPIC_MODEL (optional, default
claude-sonnet-4-5).

Actions: chat(messages, system?, max_tokens?), list_models (static known list).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hub.base import BaseConnector, register, ConnectorError

ANTHROPIC_VERSION = "2023-06-01"
API_URL = "https://api.anthropic.com/v1/messages"

KNOWN_MODELS = [
    "claude-opus-4-1",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-3-7-sonnet-latest",
    "claude-3-5-haiku-latest",
]


@register
class AnthropicConnector(BaseConnector):
    name = "claude"
    required_env = ["ANTHROPIC_API_KEY"]
    description = "Anthropic Claude — messages API, static model list"

    DEFAULT_MODEL = "claude-sonnet-4-5"

    def _headers(self):
        return {
            "x-api-key": self.env("ANTHROPIC_API_KEY"),
            "anthropic-version": ANTHROPIC_VERSION,
        }

    read_only_actions = frozenset(['list_models'])
    mutating_actions = frozenset(['chat'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['chat'])

    def actions(self):
        return ["chat", "list_models"]

    def _live(self, action, **params):
        if action == "chat":
            messages = params.get("messages")
            if not messages:
                raise ConnectorError("claude: chat requires 'messages'")
            payload = {
                "model": params.get("model")
                or self.env("ANTHROPIC_MODEL", self.DEFAULT_MODEL),
                "messages": messages,
                "max_tokens": int(params.get("max_tokens") or 1024),
            }
            if params.get("system"):
                payload["system"] = params["system"]
            if params.get("temperature") is not None:
                payload["temperature"] = params["temperature"]
            resp = self.http_json(
                "POST", API_URL, headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        if action == "list_models":
            return {"ok": True, "connector": self.name, "action": action,
                    "data": {"models": KNOWN_MODELS}}

        raise ConnectorError(f"claude: unhandled action '{action}'")


if __name__ == "__main__":
    c = AnthropicConnector()
    print(json.dumps(c.status(), indent=2))
    print(json.dumps(c.call("chat", messages=[{"role": "user", "content": "hi"}]), indent=2))
