"""Linode (Akamai Cloud) connector.

API: https://api.linode.com/v4, Bearer personal access token.
Set LINODE_API_TOKEN to go live (Linode Cloud Manager -> API Tokens).
"""
from hub.base import BaseConnector, ConnectorError, register

BASE = "https://api.linode.com/v4"


@register
class LinodeConnector(BaseConnector):
    name = "linode"
    required_env = ["LINODE_API_TOKEN"]
    description = "Linode: instances, regions, types"

    read_only_actions = frozenset(['list_linodes', 'get_linode', 'list_regions', 'list_types'])
    mutating_actions = frozenset(['create_linode', 'boot', 'reboot'])
    destructive_actions = frozenset(['shutdown', 'delete_linode'])
    dry_run_actions = frozenset(['create_linode', 'boot', 'reboot', 'shutdown', 'delete_linode'])

    def actions(self):
        return [
            "list_linodes", "get_linode", "create_linode", "boot",
            "shutdown", "reboot", "delete_linode", "list_regions",
            "list_types",
        ]

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('LINODE_API_TOKEN')}"}

    def _req(self, method, path, payload=None):
        return self.http_json(method, BASE + path, headers=self._headers(),
                              payload=payload)

    def _live(self, action, **params):
        if action == "list_linodes":
            return self._req("GET", "/linode/instances")
        if action == "get_linode":
            lid = params.get("id")
            if not lid:
                raise ConnectorError("linode: get_linode requires id")
            return self._req("GET", f"/linode/instances/{lid}")
        if action == "create_linode":
            region = params.get("region")
            ltype = params.get("type")
            image = params.get("image")
            root_pass = params.get("root_pass")
            if not (region and ltype and image and root_pass):
                raise ConnectorError(
                    "linode: create_linode requires region, type, image, "
                    "root_pass")
            payload = {
                "region": region,
                "type": ltype,
                "image": image,
                "root_pass": root_pass,
            }
            if params.get("label"):
                payload["label"] = params["label"]
            for opt in ("authorized_keys", "authorized_users", "backups_enabled",
                        "booted", "interfaces", "metadata", "placement_group",
                        "stackscript_data", "stackscript_id", "tags", "group"):
                if params.get(opt) is not None:
                    payload[opt] = params[opt]
            return self._req("POST", "/linode/instances", payload=payload)
        if action in ("boot", "shutdown", "reboot"):
            lid = params.get("id")
            if not lid:
                raise ConnectorError(f"linode: {action} requires id")
            payload = None
            if action == "boot" and params.get("config_id"):
                payload = {"config_id": params["config_id"]}
            return self._req("POST", f"/linode/instances/{lid}/{action}",
                             payload=payload)
        if action == "delete_linode":
            lid = params.get("id")
            if not lid:
                raise ConnectorError("linode: delete_linode requires id")
            return self._req("DELETE", f"/linode/instances/{lid}")
        if action == "list_regions":
            return self._req("GET", "/regions")
        if action == "list_types":
            return self._req("GET", "/linode/types")
        raise ConnectorError(f"linode: unhandled action '{action}'")
