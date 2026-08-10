"""Contabo connector.

API: https://api.contabo.com/v1, Bearer token obtained via OAuth2
resource-owner password grant from
  POST https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token
The access token is cached in-memory (per connector instance) and refreshed
shortly before expiry. The token is never logged or written to disk.

Env: CONTABO_CLIENT_ID, CONTABO_CLIENT_SECRET, CONTABO_API_USER,
     CONTABO_API_PASSWORD
"""
import time
import urllib.parse
import urllib.request
import urllib.error
import json

from hub.base import BaseConnector, ConnectorError, register

BASE = "https://api.contabo.com/v1"
TOKEN_URL = ("https://auth.contabo.com/auth/realms/contabo/"
             "protocol/openid-connect/token")


@register
class ContaboConnector(BaseConnector):
    name = "contabo"
    required_env = ["CONTABO_CLIENT_ID", "CONTABO_CLIENT_SECRET",
                    "CONTABO_API_USER", "CONTABO_API_PASSWORD"]
    description = "Contabo: VPS instances, images, snapshots (OAuth2)"

    def __init__(self, config=None):
        super().__init__(config=config)
        self._token = None
        self._token_expires_at = 0.0

    def actions(self):
        return [
            "list_instances", "get_instance", "create_instance", "start",
            "stop", "restart", "list_images", "list_snapshots",
        ]

    # --- OAuth2 ----------------------------------------------------------
    def _get_token(self):
        # Refresh 60s before expiry to avoid races.
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        form = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": self.env("CONTABO_CLIENT_ID"),
            "client_secret": self.env("CONTABO_CLIENT_SECRET"),
            "username": self.env("CONTABO_API_USER"),
            "password": self.env("CONTABO_API_PASSWORD"),
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=form, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            raise ConnectorError(
                f"contabo OAuth2 token request failed HTTP {e.code}")
        except urllib.error.URLError as e:
            raise ConnectorError(f"contabo OAuth2 connection failed: {e.reason}")
        token = data.get("access_token")
        if not token:
            raise ConnectorError("contabo OAuth2 response missing access_token")
        self._token = token
        self._token_expires_at = time.time() + int(data.get("expires_in", 300))
        return token

    def _req(self, method, path, payload=None):
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "x-request-id": f"hub-contabo-{int(time.time() * 1000)}",
        }
        return self.http_json(method, BASE + path, headers=headers,
                              payload=payload)

    def _live(self, action, **params):
        if action == "list_instances":
            return self._req("GET", "/compute/instances")
        if action == "get_instance":
            iid = params.get("id")
            if not iid:
                raise ConnectorError("contabo: get_instance requires id")
            return self._req("GET", f"/compute/instances/{iid}")
        if action == "create_instance":
            image_id = (params.get("image_id") or params.get("imageId")
                        or params.get("image"))
            product_id = (params.get("product_id") or params.get("productId")
                          or params.get("product"))
            if not (image_id and product_id):
                raise ConnectorError(
                    "contabo: create_instance requires image_id and product_id "
                    "(e.g. product_id='V1')")
            payload = {"imageId": image_id, "productId": product_id}
            # Optional fields per Contabo Compute API.
            for opt in ("region", "period", "displayName", "rootPassword",
                        "sshKeys", "userData", "license", "defaultUser",
                        "addOns"):
                if params.get(opt) is not None:
                    payload[opt] = params[opt]
            return self._req("POST", "/compute/instances", payload=payload)
        if action in ("start", "stop", "restart"):
            iid = params.get("id")
            if not iid:
                raise ConnectorError(f"contabo: {action} requires id")
            return self._req("POST",
                             f"/compute/instances/{iid}/actions/{action}")
        if action == "list_images":
            return self._req("GET", "/compute/images")
        if action == "list_snapshots":
            iid = params.get("instance_id") or params.get("id")
            if not iid:
                raise ConnectorError(
                    "contabo: list_snapshots requires instance_id")
            return self._req("GET", f"/compute/instances/{iid}/snapshots")
        raise ConnectorError(f"contabo: unhandled action '{action}'")
