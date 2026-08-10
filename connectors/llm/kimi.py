"""Kimi (Moonshot AI) connector — OpenAI-compatible API.

Env: MOONSHOT_API_KEY (required; KIMI_API_KEY accepted as fallback),
MOONSHOT_BASE_URL (optional, default https://api.moonshot.cn/v1 — set to
https://api.moonshot.ai/v1 for the international endpoint),
MOONSHOT_MODEL (optional, default kimi-k2-0711-preview).

Actions: chat(messages), list_models.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hub.base import BaseConnector, register, ConnectorError


@register
class KimiConnector(BaseConnector):
    name = "kimi"
    required_env = []  # resolved dynamically: MOONSHOT_API_KEY or KIMI_API_KEY
    description = "Kimi / Moonshot AI — OpenAI-compatible chat completions"

    DEFAULT_MODEL = "kimi-k2-0711-preview"

    def __init__(self, config=None):
        # Accept either MOONSHOT_API_KEY or KIMI_API_KEY.
        if not os.environ.get("MOONSHOT_API_KEY") and os.environ.get("KIMI_API_KEY"):
            os.environ["MOONSHOT_API_KEY"] = os.environ["KIMI_API_KEY"]
        self.required_env = ["MOONSHOT_API_KEY"]
        super().__init__(config=config)

    def _base(self):
        return self.env("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1").rstrip("/")

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('MOONSHOT_API_KEY')}"}

    def actions(self):
        return ["chat", "list_models"]

    def _live(self, action, **params):
        if action == "chat":
            messages = params.get("messages")
            if not messages:
                raise ConnectorError("kimi: chat requires 'messages'")
            payload = {
                "model": params.get("model")
                or self.env("MOONSHOT_MODEL", self.DEFAULT_MODEL),
                "messages": messages,
            }
            for key in ("temperature", "max_tokens", "top_p", "stream"):
                if params.get(key) is not None:
                    payload[key] = params[key]
            resp = self.http_json(
                "POST", f"{self._base()}/chat/completions",
                headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        if action == "list_models":
            resp = self.http_json(
                "GET", f"{self._base()}/models", headers=self._headers(),
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        raise ConnectorError(f"kimi: unhandled action '{action}'")


if __name__ == "__main__":
    c = KimiConnector()
    print(json.dumps(c.status(), indent=2))
    print(json.dumps(c.call("chat", messages=[{"role": "user", "content": "hi"}]), indent=2))
