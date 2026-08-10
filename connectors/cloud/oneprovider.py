"""OneProvider connector (dedicated/cloud servers).

OneProvider exposes an API ("OneProvider API v1") for its OnePortal customers,
authenticated with an API key sent as a Bearer token:

    Authorization: Bearer <ONEPROVIDER_API_KEY>
    Base URL:      https://api.oneprovider.com

NOTE: OneProvider's public API surface is limited and its documentation is
sparse; the paths below follow the documented "/servers"-style v1 resource
layout and are best-effort. If an endpoint differs on the live API, adjust the
path constants in `_live()` accordingly — auth, error handling and the mock
contract are unaffected.

Env: ONEPROVIDER_API_KEY
"""
from hub.base import BaseConnector, ConnectorError, register

BASE = "https://api.oneprovider.com"


@register
class OneProviderConnector(BaseConnector):
    name = "oneprovider"
    required_env = ["ONEPROVIDER_API_KEY"]
    description = "OneProvider: dedicated servers, locations, templates, bandwidth"

    def actions(self):
        return [
            "list_servers", "get_server", "reboot", "list_locations",
            "list_templates", "bandwidth",
        ]

    def _headers(self):
        return {"Authorization": f"Bearer {self.env('ONEPROVIDER_API_KEY')}"}

    def _req(self, method, path, payload=None):
        return self.http_json(method, BASE + path, headers=self._headers(),
                              payload=payload)

    def _live(self, action, **params):
        if action == "list_servers":
            # OneProvider API v1: GET /servers — list all servers on the account.
            return self._req("GET", "/servers")
        if action == "get_server":
            sid = params.get("id")
            if not sid:
                raise ConnectorError("oneprovider: get_server requires id")
            # GET /servers/{id} — details for one server.
            return self._req("GET", f"/servers/{sid}")
        if action == "reboot":
            sid = params.get("id")
            if not sid:
                raise ConnectorError("oneprovider: reboot requires id")
            # POST /servers/{id}/reboot — power-cycle the server.
            return self._req("POST", f"/servers/{sid}/reboot")
        if action == "list_locations":
            # GET /locations — available datacenter locations for ordering.
            return self._req("GET", "/locations")
        if action == "list_templates":
            # GET /templates — OS reinstall templates.
            return self._req("GET", "/templates")
        if action == "bandwidth":
            sid = params.get("id")
            if not sid:
                raise ConnectorError("oneprovider: bandwidth requires id")
            # GET /servers/{id}/bandwidth — traffic usage for one server.
            return self._req("GET", f"/servers/{sid}/bandwidth")
        raise ConnectorError(f"oneprovider: unhandled action '{action}'")
