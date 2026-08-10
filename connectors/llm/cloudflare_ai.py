"""Cloudflare Workers AI connector.

Env: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN (both required),
CLOUDFLARE_AI_MODEL (optional, default @cf/meta/llama-3.1-8b-instruct).

Actions: chat(messages), run_model(model, input).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from hub.base import BaseConnector, register, ConnectorError


@register
class CloudflareAIConnector(BaseConnector):
    name = "cloudflare"
    required_env = ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"]
    description = "Cloudflare Workers AI — run any model, chat helper"

    DEFAULT_MODEL = "@cf/meta/llama-3.1-8b-instruct"

    def _url(self, model):
        account = self.env("CLOUDFLARE_ACCOUNT_ID")
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{account}/ai/run/{model}"
        )

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('CLOUDFLARE_API_TOKEN')}"}

    read_only_actions = frozenset([])
    mutating_actions = frozenset(['chat', 'run_model'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['chat', 'run_model'])

    def actions(self):
        return ["chat", "run_model"]

    def _live(self, action, **params):
        if action == "chat":
            messages = params.get("messages")
            if not messages:
                raise ConnectorError("cloudflare: chat requires 'messages'")
            model = params.get("model") or self.env(
                "CLOUDFLARE_AI_MODEL", self.DEFAULT_MODEL
            )
            payload = {"messages": messages}
            for key in ("max_tokens", "temperature", "stream"):
                if params.get(key) is not None:
                    payload[key] = params[key]
            resp = self.http_json(
                "POST", self._url(model), headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        if action == "run_model":
            model = params.get("model")
            if not model:
                raise ConnectorError("cloudflare: run_model requires 'model'")
            model_input = params.get("input")
            if model_input is None:
                raise ConnectorError("cloudflare: run_model requires 'input'")
            # input may be a dict payload (passed through) or a plain prompt.
            payload = model_input if isinstance(model_input, dict) else {"prompt": model_input}
            resp = self.http_json(
                "POST", self._url(model), headers=self._headers(), payload=payload,
            )
            return {"ok": True, "connector": self.name, "action": action,
                    "data": resp["data"]}

        raise ConnectorError(f"cloudflare: unhandled action '{action}'")


if __name__ == "__main__":
    c = CloudflareAIConnector()
    print(json.dumps(c.status(), indent=2))
    print(json.dumps(c.call("chat", messages=[{"role": "user", "content": "hi"}]), indent=2))
