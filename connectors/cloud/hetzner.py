"""Hetzner Cloud connector.

API: https://api.hetzner.cloud/v1, Bearer token auth.
Set HETZNER_API_TOKEN to go live (Hetzner Cloud Console -> Security -> API tokens).
"""
from hub.base import BaseConnector, ConnectorError, register

BASE = "https://api.hetzner.cloud/v1"


@register
class HetznerConnector(BaseConnector):
    name = "hetzner"
    required_env = ["HETZNER_API_TOKEN"]
    description = "Hetzner Cloud: servers, images, locations, ssh keys"

    def actions(self):
        return [
            "list_servers", "get_server", "create_server", "power_on",
            "power_off", "reboot", "delete_server", "list_images",
            "list_locations", "list_ssh_keys",
        ]

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('HETZNER_API_TOKEN')}"}

    def _req(self, method, path, payload=None):
        return self.http_json(method, BASE + path, headers=self._headers(),
                              payload=payload)

    def _live(self, action, **params):
        if action == "list_servers":
            return self._req("GET", "/servers")
        if action == "get_server":
            sid = params.get("id")
            if not sid:
                raise ConnectorError("hetzner: get_server requires id")
            return self._req("GET", f"/servers/{sid}")
        if action == "create_server":
            name = params.get("name")
            server_type = params.get("server_type")
            image = params.get("image")
            if not (name and server_type and image):
                raise ConnectorError(
                    "hetzner: create_server requires name, server_type, image")
            payload = {"name": name, "server_type": server_type, "image": image}
            if params.get("location"):
                payload["location"] = params["location"]
            for opt in ("ssh_keys", "volumes", "networks", "user_data",
                        "labels", "automount", "start_after_create",
                        "placement_group", "datacenter", "firewalls"):
                if params.get(opt) is not None:
                    payload[opt] = params[opt]
            return self._req("POST", "/servers", payload=payload)
        if action in ("power_on", "power_off", "reboot"):
            sid = params.get("id")
            if not sid:
                raise ConnectorError(f"hetzner: {action} requires id")
            return self._req("POST", f"/servers/{sid}/actions/{action}")
        if action == "delete_server":
            sid = params.get("id")
            if not sid:
                raise ConnectorError("hetzner: delete_server requires id")
            return self._req("DELETE", f"/servers/{sid}")
        if action == "list_images":
            return self._req("GET", "/images")
        if action == "list_locations":
            return self._req("GET", "/locations")
        if action == "list_ssh_keys":
            return self._req("GET", "/ssh_keys")
        raise ConnectorError(f"hetzner: unhandled action '{action}'")
