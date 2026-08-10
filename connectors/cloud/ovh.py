"""OVHcloud connector (VPS, dedicated servers, account).

Auth: OVH application-key signature scheme.
Each request is signed as:
    "$1$" + sha1(app_secret + "+" + consumer_key + "+" + METHOD + "+"
                 + url + "+" + body + "+" + timestamp)
where timestamp is the server time fetched from https://{endpoint}/1.0/auth/time
(never the local clock — signatures fail on clock skew).

Env:
  OVH_ENDPOINT      regional endpoint shorthand (default "ovh-eu") or a full
                    API host such as "api.ovh.com"
  OVH_APP_KEY       application key (AK)
  OVH_APP_SECRET    application secret (AS)
  OVH_CONSUMER_KEY  consumer key (CK)

Known endpoint shorthands:
  ovh-eu -> api.ovh.com          ovh-us -> api.us.ovhcloud.com
  ovh-ca -> api.ca.ovh.com       kimsufi-eu -> eu.api.kimsufi.com
  kimsufi-ca -> ca.api.kimsufi.com
  soyoustart-eu -> eu.api.soyoustart.com
  soyoustart-ca -> ca.api.soyoustart.com
"""
import hashlib
import json
import time

from hub.base import BaseConnector, ConnectorError, register

ENDPOINTS = {
    "ovh-eu": "api.ovh.com",
    "ovh-us": "api.us.ovhcloud.com",
    "ovh-ca": "api.ca.ovh.com",
    "kimsufi-eu": "eu.api.kimsufi.com",
    "kimsufi-ca": "ca.api.kimsufi.com",
    "soyoustart-eu": "eu.api.soyoustart.com",
    "soyoustart-ca": "ca.api.soyoustart.com",
}


def build_signature(app_secret, consumer_key, method, url, body, timestamp):
    """Return the OVH request signature: "$1$" + sha1(AS+CK+METHOD+url+body+ts)."""
    raw = "+".join([
        app_secret, consumer_key, method.upper(), url, body or "",
        str(int(timestamp)),
    ])
    return "$1$" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


@register
class OvhConnector(BaseConnector):
    name = "ovh"
    required_env = ["OVH_APP_KEY", "OVH_APP_SECRET", "OVH_CONSUMER_KEY"]
    description = "OVHcloud: VPS, dedicated servers, IPs, account info"

    def __init__(self, config=None):
        super().__init__(config=config)
        self._server_time_offset = None  # server_ts - local_ts

    read_only_actions = frozenset(['list_vps', 'get_vps', 'list_dedicated', 'get_dedicated', 'get_me', 'list_ips'])
    mutating_actions = frozenset(['reboot_vps'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['reboot_vps'])

    def actions(self):
        return [
            "list_vps", "get_vps", "reboot_vps", "list_dedicated",
            "get_dedicated", "get_me", "list_ips",
        ]

    # --- endpoint / signing ----------------------------------------------
    def _api_host(self):
        ep = self.env("OVH_ENDPOINT", "ovh-eu") or "ovh-eu"
        ep = ep.strip()
        if ep in ENDPOINTS:
            return ENDPOINTS[ep]
        if ep.startswith("http://") or ep.startswith("https://"):
            ep = ep.split("://", 1)[1]
        return ep.rstrip("/")

    def _timestamp(self):
        """OVH server time (cached offset), falling back to local time."""
        if self._server_time_offset is None:
            url = f"https://{self._api_host()}/1.0/auth/time"
            # Unauthenticated plain-text endpoint returning epoch seconds.
            resp = self.http_json("GET", url)
            data = resp.get("data")
            raw = data.get("raw") if isinstance(data, dict) else data
            try:
                server_ts = int(str(raw).strip())
            except (TypeError, ValueError):
                raise ConnectorError(
                    "ovh: could not parse server time from /auth/time")
            self._server_time_offset = server_ts - time.time()
        return int(time.time() + self._server_time_offset)

    def _req(self, method, path, payload=None):
        url = f"https://{self._api_host()}/1.0{path}"
        body = json.dumps(payload) if payload is not None else ""
        ts = self._timestamp()
        headers = {
            "X-Ovh-Application": self.env("OVH_APP_KEY"),
            "X-Ovh-Consumer": self.env("OVH_CONSUMER_KEY"),
            "X-Ovh-Timestamp": str(ts),
            "X-Ovh-Signature": build_signature(
                self.env("OVH_APP_SECRET"), self.env("OVH_CONSUMER_KEY"),
                method, url, body, ts),
        }
        return self.http_json(method, url, headers=headers, payload=payload)

    def _live(self, action, **params):
        if action == "list_vps":
            return self._req("GET", "/vps")
        if action == "get_vps":
            name = params.get("name") or params.get("id")
            if not name:
                raise ConnectorError("ovh: get_vps requires name")
            return self._req("GET", f"/vps/{name}")
        if action == "reboot_vps":
            name = params.get("name") or params.get("id")
            if not name:
                raise ConnectorError("ovh: reboot_vps requires name")
            return self._req("POST", f"/vps/{name}/reboot")
        if action == "list_dedicated":
            return self._req("GET", "/dedicated/server")
        if action == "get_dedicated":
            name = params.get("name") or params.get("id")
            if not name:
                raise ConnectorError("ovh: get_dedicated requires name")
            return self._req("GET", f"/dedicated/server/{name}")
        if action == "get_me":
            return self._req("GET", "/me")
        if action == "list_ips":
            return self._req("GET", "/ip")
        raise ConnectorError(f"ovh: unhandled action '{action}'")
