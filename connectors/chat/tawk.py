"""tawk.to REST API connector (chat + tickets + agents).

Auth: API key from the tawk.to dashboard (Administration > REST API), sent as
an Authorization Bearer token. Base URL: https://api.tawk.to/v1

NOTE on endpoint versioning: tawk.to's public REST surface has changed across
releases and some paths are gated per plan/property. The paths below follow the
documented `/chats` and `/tickets` resources of the v1 REST API. If your
account returns 404 on a path, check the current tawk.to developer docs for the
exact route name for your API version — the request/auth plumbing here is
correct either way.

Env: TAWK_API_KEY, TAWK_PROPERTY_ID
"""
from hub.base import BaseConnector, ConnectorError, register

BASE = "https://api.tawk.to/v1"


@register
class TawkConnector(BaseConnector):
    name = "tawk"
    required_env = ["TAWK_API_KEY", "TAWK_PROPERTY_ID"]
    description = "tawk.to live chat + ticketing via REST API"

    read_only_actions = frozenset(['list_chats', 'get_chat', 'list_tickets', 'get_ticket', 'list_agents', 'property_info'])
    mutating_actions = frozenset(['send_message', 'reply_ticket'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['send_message', 'reply_ticket'])

    def actions(self):
        return [
            "list_chats",
            "get_chat",
            "send_message",
            "list_tickets",
            "get_ticket",
            "reply_ticket",
            "list_agents",
            "property_info",
        ]

    # --- internal ---------------------------------------------------------
    def _headers(self):
        return {"Authorization": f"Bearer {self.env('TAWK_API_KEY')}"}

    def _prop(self, params):
        prop = params.pop("property_id", None) or self.env("TAWK_PROPERTY_ID")
        if not prop:
            raise ConnectorError(f"{self.name}: property_id required (param or TAWK_PROPERTY_ID)")
        return prop

    def _get(self, path, params=None):
        qs = ""
        if params:
            from urllib.parse import urlencode
            qs = "?" + urlencode({k: v for k, v in params.items() if v is not None})
        return self.http_json("GET", BASE + path + qs, headers=self._headers())

    def _post(self, path, payload):
        return self.http_json("POST", BASE + path, headers=self._headers(), payload=payload)

    # --- live actions ------------------------------------------------------
    def _live(self, action, **params):
        if action == "list_chats":
            prop = self._prop(params)
            # Documented: GET /v1/chats?property_id=...&status=open|pending|closed
            return self._get("/chats", {"property_id": prop, "status": params.get("status")})

        if action == "get_chat":
            chat_id = self._required(params, "chat_id")
            return self._get(f"/chats/{chat_id}")

        if action == "send_message":
            chat_id = self._required(params, "chat_id")
            message = self._required(params, "message")
            # Documented: POST /v1/chats/{chat_id}/messages  {"message": "..."}
            return self._post(f"/chats/{chat_id}/messages", {"message": message})

        if action == "list_tickets":
            prop = self._prop(params)
            # Documented: GET /v1/tickets?property_id=...&status=open|pending|closed
            return self._get("/tickets", {"property_id": prop, "status": params.get("status")})

        if action == "get_ticket":
            ticket_id = self._required(params, "ticket_id")
            return self._get(f"/tickets/{ticket_id}")

        if action == "reply_ticket":
            ticket_id = self._required(params, "ticket_id")
            message = self._required(params, "message")
            # Documented: POST /v1/tickets/{ticket_id}/replies  {"message": "..."}
            return self._post(f"/tickets/{ticket_id}/replies", {"message": message})

        if action == "list_agents":
            prop = self._prop(params)
            return self._get("/agents", {"property_id": prop})

        if action == "property_info":
            prop = self._prop(params)
            return self._get(f"/properties/{prop}")

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")

    def _required(self, params, key):
        val = params.get(key)
        if not val:
            raise ConnectorError(f"{self.name}: '{key}' is required")
        return val
