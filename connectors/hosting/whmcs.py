"""WHMCS billing panel connector.

Live mode: POST form-encoded requests to {WHMCS_URL}/includes/api.php
with identifier/secret credentials and responsetype=json.

WHMCS API reference: https://developers.whmcs.com/api/api-index/
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from hub.base import BaseConnector, ConnectorError, register


@register
class WHMCSConnector(BaseConnector):
    """WHMCS billing automation: clients, invoices, tickets, services."""

    name = "whmcs"
    required_env = ["WHMCS_URL", "WHMCS_API_IDENTIFIER", "WHMCS_API_SECRET"]
    description = "WHMCS billing: clients, invoices, tickets, products, module actions"

    def actions(self):
        return [
            "get_clients",
            "get_client",
            "get_invoices",
            "get_tickets",
            "reply_ticket",
            "add_client",
            "create_invoice",
            "get_products",
            "module_action",
        ]

    # --- live plumbing ----------------------------------------------------
    def _api(self, whmcs_action, **fields):
        """POST one form-encoded WHMCS API request, return parsed dict."""
        base = (self.env("WHMCS_URL") or "").rstrip("/")
        if not base:
            raise ConnectorError("whmcs: WHMCS_URL is not set")
        url = f"{base}/includes/api.php"
        body = urllib.parse.urlencode(
            {
                "identifier": self.env("WHMCS_API_IDENTIFIER"),
                "secret": self.env("WHMCS_API_SECRET"),
                "action": whmcs_action,
                "responsetype": "json",
                **{k: v for k, v in fields.items() if v is not None},
            }
        ).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise ConnectorError(f"whmcs HTTP {e.code} {url}: {detail}")
        except urllib.error.URLError as e:
            raise ConnectorError(f"whmcs connection failed {url}: {e.reason}")

        if isinstance(data, dict) and data.get("result") == "error":
            # WHMCS returns HTTP 200 with result=error; message may exist.
            raise ConnectorError(
                f"whmcs API error ({whmcs_action}): {data.get('message', data)}"
            )
        return {"ok": True, "data": data}

    # --- actions ----------------------------------------------------------
    def _live(self, action, **params):
        if action == "get_clients":
            limit = int(params.get("limit", 25) or 25)
            return self._api("GetClients", limitstart=0, limitnum=limit)

        if action == "get_client":
            client_id = params.get("client_id")
            if not client_id:
                raise ConnectorError("whmcs get_client requires client_id")
            return self._api("GetClientsDetails", clientid=client_id, stats="true")

        if action == "get_invoices":
            fields = {"limitnum": int(params.get("limit", 25) or 25)}
            if params.get("status"):
                fields["status"] = params["status"]
            if params.get("client_id"):
                fields["userid"] = params["client_id"]
            return self._api("GetInvoices", **fields)

        if action == "get_tickets":
            fields = {"limitnum": int(params.get("limit", 25) or 25)}
            if params.get("status"):
                fields["status"] = params["status"]
            if params.get("client_id"):
                fields["clientid"] = params["client_id"]
            return self._api("GetTickets", **fields)

        if action == "reply_ticket":
            ticket_id = params.get("ticket_id")
            message = params.get("message")
            if not ticket_id or not message:
                raise ConnectorError(
                    "whmcs reply_ticket requires ticket_id and message"
                )
            return self._api("AddTicketReply", ticketid=ticket_id, message=message)

        if action == "add_client":
            required = ["firstname", "lastname", "email", "password"]
            missing = [k for k in required if not params.get(k)]
            if missing:
                raise ConnectorError(
                    f"whmcs add_client missing required: {', '.join(missing)}"
                )
            fields = {k: params[k] for k in required}
            for opt in ("companyname", "address1", "city", "state", "postcode",
                        "country", "phonenumber"):
                if params.get(opt):
                    fields[opt] = params[opt]
            return self._api("AddClient", **fields)

        if action == "create_invoice":
            client_id = params.get("client_id")
            items = params.get("items")
            if not client_id or not items:
                raise ConnectorError(
                    "whmcs create_invoice requires client_id and items "
                    "(list of {description, amount})"
                )
            if isinstance(items, str):
                items = json.loads(items)
            if not isinstance(items, (list, tuple)) or not items:
                raise ConnectorError("whmcs create_invoice: items must be a non-empty list")
            fields = {"userid": client_id, "sendinvoice": "true"}
            for i, item in enumerate(items, 1):
                fields[f"itemdescription{i}"] = item.get("description", f"Item {i}")
                fields[f"itemamount{i}"] = item.get("amount", 0)
                fields[f"itemtaxed{i}"] = 1 if item.get("taxed") else 0
            return self._api("CreateInvoice", **fields)

        if action == "get_products":
            fields = {}
            if params.get("product_id"):
                fields["pid"] = params["product_id"]
            if params.get("group_id"):
                fields["gid"] = params["group_id"]
            return self._api("GetProducts", **fields)

        if action == "module_action":
            service_id = params.get("service_id")
            mod_action = (params.get("action") or "").lower()
            mapping = {
                "suspend": "ModuleSuspend",
                "unsuspend": "ModuleUnsuspend",
                "terminate": "ModuleTerminate",
                "create": "ModuleCreate",
            }
            if not service_id or mod_action not in mapping:
                raise ConnectorError(
                    "whmcs module_action requires service_id and action in "
                    "(suspend, unsuspend, terminate, create)"
                )
            return self._api(mapping[mod_action], accountid=service_id)

        raise ConnectorError(f"whmcs: unhandled action '{action}'")
