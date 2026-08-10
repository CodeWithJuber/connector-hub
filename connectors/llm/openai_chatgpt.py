"""OpenAI ChatGPT connector.

Env: OPENAI_API_KEY (required), OPENAI_BASE_URL (optional, default
https://api.openai.com), OPENAI_MODEL (optional, default gpt-4o-mini).

Actions: chat(messages, model?), list_models, embeddings(input).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hub.base import BaseConnector, register, ConnectorError


@register
class OpenAIConnector(BaseConnector):
    name = "openai"
    required_env = ["OPENAI_API_KEY"]
    description = "OpenAI ChatGPT — chat completions, model list, embeddings"

    DEFAULT_MODEL = "gpt-4o-mini"

    def _base(self):
        return self.env("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('OPENAI_API_KEY')}"}

    def actions(self):
        return ["chat", "list_models", "embeddings"]

    def _live(self, action, **params):
        if action == "chat":
            messages = params.get("messages")
            if not messages:
                raise ConnectorError("openai: chat requires 'messages'")
            payload = {
                "model": params.get("model")
                or self.env("OPENAI_MODEL", self.DEFAULT_MODEL),
                "messages": messages,
            }
            for key in ("temperature", "max_tokens", "top_p", "stream"):
                if params.get(key) is not None:
                    payload[key] = params[key]
            resp = self.http_json(
                "POST", f"{self._base()}/v1/chat/completions",
                headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        if action == "list_models":
            resp = self.http_json(
                "GET", f"{self._base()}/v1/models", headers=self._headers(),
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        if action == "embeddings":
            text = params.get("input")
            if text is None:
                raise ConnectorError("openai: embeddings requires 'input'")
            payload = {
                "model": params.get("model", "text-embedding-3-small"),
                "input": text,
            }
            resp = self.http_json(
                "POST", f"{self._base()}/v1/embeddings",
                headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        raise ConnectorError(f"openai: unhandled action '{action}'")


if __name__ == "__main__":
    c = OpenAIConnector()
    print(json.dumps(c.status(), indent=2))
    print(json.dumps(c.call("chat", messages=[{"role": "user", "content": "hi"}]), indent=2))
