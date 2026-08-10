"""UltaHost connector (WHMCS bridge).

UltaHost does NOT publish a fully public VPS management API. This connector
therefore works as a WHMCS bridge: UltaHost's billing/client area is a
WHMCS-style deployment, and service actions are performed through a configured
WHMCS-compatible billing API endpoint.

Modes:
  * ULTRAHOST_WHMCS_URL set  -> live bridge: WHMCS-style form POSTs
    (application/x-www-form-urlencoded) to that URL, e.g.
        POST {ULTRAHOST_WHMCS_URL}
        action=module_suspend / module_unsuspend / module_reboot / ...
        &accountid=<id>&serviceid=<id>
    authenticated with ULTRAHOST_API_USER + ULTRAHOST_API_KEY
    (WHMCS API identifier/secret style credentials).
  * ULTRAHOST_WHMCS_URL unset (but key+user present) -> mock bridge:
    returns {"ok": True, "mock": True, ...} so workflows can be developed
    before the billing bridge is provisioned.
  * No credentials at all -> standard hub mock mode.

Env:
  ULTRAHOST_API_KEY    WHMCS API secret / token
  ULTRAHOST_API_USER   WHMCS API identifier / admin user
  ULTRAHOST_WHMCS_URL  optional; e.g. https://billing.example.com/includes/api.php
"""
import json
import urllib.parse
import urllib.request
import urllib.error

from hub.base import BaseConnector, ConnectorError, register


@register
class UltaHostConnector(BaseConnector):
    name = "ultrahost"
    required_env = ["ULTRAHOST_API_KEY", "ULTRAHOST_API_USER"]
    description = ("UltaHost VPS via WHMCS-bridge billing API "
                   "(mock bridge when ULTRAHOST_WHMCS_URL unset)")

    def actions(self):
        return ["list_services", "get_service", "reboot", "start", "stop",
                "status"]

    # --- WHMCS bridge ------------------------------------------------------
    def _whmcs_url(self):
        url = self.env("ULTRAHOST_WHMCS_URL", "") or ""
        return url.strip()

    def _whmcs_post(self, form_fields):
        """WHMCS-style form POST; returns parsed JSON dict."""
        form = dict(form_fields)
        # WHMCS API credential fields; never logged (base redacts *KEY*/*PASS*).
        form.setdefault("identifier", self.env("ULTRAHOST_API_USER"))
        form.setdefault("secret", self.env("ULTRAHOST_API_KEY"))
        form.setdefault("username", self.env("ULTRAHOST_API_USER"))
        form.setdefault("accesskey", self.env("ULTRAHOST_API_KEY"))
        form.setdefault("responsetype", "json")
        body = urllib.parse.urlencode(form).encode()
        req = urllib.request.Request(self._whmcs_url(), data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw[:1000]}
        except urllib.error.HTTPError as e:
            raise ConnectorError(
                f"ultrahost WHMCS bridge HTTP {e.code}: "
                f"{e.read().decode(errors='replace')[:300]}")
        except urllib.error.URLError as e:
            raise ConnectorError(
                f"ultrahost WHMCS bridge connection failed: {e.reason}")
        if isinstance(data, dict) and data.get("result") == "error":
            raise ConnectorError(
                f"ultrahost WHMCS bridge error: {data.get('message', 'unknown')}")
        return {"ok": True, "bridge": "whmcs", "data": data}

    def _mock_bridge(self, action, params):
        return {
            "ok": True,
            "mock": True,
            "connector": self.name,
            "action": action,
            "echo": self._redact(params),
            "note": "set ULTRAHOST_WHMCS_URL to enable the live WHMCS bridge",
        }

    def _live(self, action, **params):
        if not self._whmcs_url():
            # No billing bridge configured: behave as a mock connector.
            return self._mock_bridge(action, params)

        if action == "list_services":
            return self._whmcs_post({"action": "GetClientsProducts",
                                     "limitnum": params.get("limit", 100)})
        if action == "get_service":
            sid = params.get("id") or params.get("serviceid")
            if not sid:
                raise ConnectorError("ultrahost: get_service requires id")
            return self._whmcs_post({"action": "GetClientsProducts",
                                     "serviceid": sid})
        if action in ("reboot", "start", "stop"):
            sid = params.get("id") or params.get("serviceid")
            if not sid:
                raise ConnectorError(f"ultrahost: {action} requires id")
            # WHMCS module custom command -> routed to the VPS module
            # (suspend/unsuspend used for stop/start; reboot as custom cmd).
            module_cmd = {"reboot": "reboot", "start": "unsuspend",
                          "stop": "suspend"}[action]
            if module_cmd in ("suspend", "unsuspend"):
                return self._whmcs_post({"action": f"Module{module_cmd.capitalize()}",
                                         "accountid": sid, "serviceid": sid})
            return self._whmcs_post({"action": "ModuleCustom",
                                     "accountid": sid, "serviceid": sid,
                                     "func_name": module_cmd})
        if action == "status":
            sid = params.get("id") or params.get("serviceid")
            if not sid:
                raise ConnectorError("ultrahost: status requires id")
            return self._whmcs_post({"action": "GetClientsProducts",
                                     "serviceid": sid, "stats": "true"})
        raise ConnectorError(f"ultrahost: unhandled action '{action}'")
