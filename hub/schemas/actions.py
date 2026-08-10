"""Strict request/response models for every public connector action.

Models are materialized per connector/action (and named accordingly), while the
compact field catalogue below keeps similar actions consistent.
"""
from __future__ import annotations

import inspect
from typing import Any, Annotated, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, create_model, model_validator

NonEmpty = Annotated[str, Field(min_length=1, max_length=65536)]
PositiveId = Annotated[int | str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def mutually_exclusive_options(self):
        groups = (("location", "datacenter"), ("id", "instance_id"),
                  ("image", "image_id", "imageId"), ("product", "product_id", "productId"))
        for group in groups:
            supplied = [name for name in group if hasattr(self, name) and getattr(self, name) is not None]
            if len(supplied) > 1:
                raise ValueError(f"options are mutually exclusive: {', '.join(group)}")
        return self


class ActionResponse(StrictModel):
    ok: bool
    status: int | None = Field(default=None, ge=100, le=599)
    data: Any = None
    request_id: str | None = None


# Explicit constraints override signature-derived fields. Secret metadata is
# consumed by logging redaction, so redaction is driven by schemas, not guesses.
SECRET_FIELDS = {"password", "root_pass", "body", "html", "message", "content", "input", "system"}
URL_FIELDS = {"url"}
INT_FIELDS = {"id", "client_id", "ticket_id", "service_id", "product_id", "group_id", "instance_id", "message_id", "number", "port", "config_id", "stackscript_id", "workflow_id"}
RANGED = {
    "limit": (1, 1000), "max_results": (1, 500), "per_page": (1, 100),
    "count": (1, 20), "length": (8, 4096), "quota": (1, 10_000_000),
    "temperature": (0, 2), "max_tokens": (1, 200_000), "port": (1, 65535),
}

ACTION_FIELDS: dict[str, dict[str, tuple[Any, Any]]] = {}


def _field(name: str, required: bool = False, default: Any = None) -> tuple[Any, Any]:
    marker = ... if required else default
    if name in RANGED:
        lo, hi = RANGED[name]
        typ = float if name == "temperature" else int
        return (Annotated[typ, Field(ge=lo, le=hi)], marker)
    if name in URL_FIELDS:
        return (AnyHttpUrl, marker)
    if name in SECRET_FIELDS:
        return (SecretStr, marker)
    if name in INT_FIELDS:
        return (Annotated[int, Field(gt=0)], marker)
    if name in {"private", "extract_text", "taxed", "keepdns", "automount", "start_after_create", "backups_enabled", "booted"}:
        return (bool, marker)
    if name in {"messages", "items", "labels", "events", "ports", "urls", "ssh_keys", "volumes", "networks", "firewalls", "authorized_keys", "authorized_users", "tags"}:
        return (list[Any], marker)
    if name in {"inputs", "metadata", "labels", "stackscript_data"}:
        return (dict[str, Any], marker)
    return (NonEmpty, marker)


def _required_from_handler(connector: Any, action: str) -> tuple[set[str], set[str]]:
    handler = getattr(connector, f"_do_{action}", None)
    if not handler:
        return set(), set()
    sig = inspect.signature(handler)
    names, required = set(), set()
    for name, p in sig.parameters.items():
        if name == "self":
            continue
        names.add(name)
        if p.default is inspect.Parameter.empty:
            required.add(name)
    return names, required


# Accepted fields for connectors implemented with a params mapping. Fields are
# deliberately action-specific: no action receives a permissive catch-all.
PARAMS: dict[str, dict[str, str]] = {
 "oneprovider": {"get_server reboot bandwidth":"id"},
 "hetzner": {"get_server power_on power_off reboot delete_server":"id", "create_server":"name! server_type! image! location ssh_keys volumes networks user_data labels automount start_after_create placement_group datacenter firewalls"},
 "linode": {"get_linode boot shutdown reboot delete_linode":"id! config_id", "create_linode":"region! type! image! root_pass! label authorized_keys authorized_users backups_enabled booted interfaces metadata placement_group stackscript_data stackscript_id tags group"},
 "ultrahost": {"get_service reboot start stop status":"id serviceid", "list_services":"limit"},
 "ovh": {"get_vps reboot_vps get_dedicated":"name id"},
 "contabo": {"get_instance start stop restart":"id instance_id", "create_instance":"image imageId image_id product productId product_id"},
 "whmcs": {"get_clients":"limit", "get_client":"client_id!", "get_invoices get_tickets":"limit status client_id", "reply_ticket":"ticket_id! message!", "add_client":"firstname! lastname! email! password! companyname address1 city state postcode country phonenumber", "create_invoice":"client_id! items!", "get_products":"product_id group_id", "module_action":"service_id! action!"},
 "whm": {"create_account":"domain! username! password! plan contactemail", "suspend_account":"user! reason", "unsuspend_account terminate_account":"user! keepdns"},
 "cpanel": {"add_subdomain":"subdomain! rootdomain! dir!", "add_email":"email! password! quota", "create_database":"name!", "create_db_user":"name! password!", "file_list":"dir", "cron_add":"command! minute hour day month weekday"},
 "openai": {"chat":"messages! model temperature max_tokens", "embeddings":"input! model"},
 "kimi": {"chat":"messages! model"}, "cloudflare_ai": {"chat":"messages! model", "run_model":"model! input!"},
 "claude": {"chat":"messages! model system max_tokens temperature"},
 "tawk": {"list_chats list_tickets":"property_id status", "get_chat":"chat_id!", "send_message":"chat_id! message!", "get_ticket":"ticket_id!", "reply_ticket":"ticket_id! message!", "list_agents property_info":"property_id"},
 "email": {"check_inbox":"account_id! limit", "send_email":"account_id! to! subject! body! html", "search":"account_id! query!"},
 "gmail": {"get_access_token":"label!", "send":"label! to! subject! body!", "list_messages":"label! query max_results", "get_message":"label! message_id!"},
 "ops_ssh": {"run_local":"command!", "run_ssh":"host_id! command!"},
 "ops_network": {"ping":"host! count", "dns_lookup":"domain!", "port_check":"host! ports", "traceroute":"host!", "http_headers":"url!"},
 "ops_security": {"audit_password_strength":"password!", "check_ssl":"host! port", "scan_common_exposure":"host!", "ssh_config_audit":"path", "generate_secret":"length"},
 "ops_browser": {"fetch":"url! extract_text", "check_status":"urls!", "screenshot":"url! out_path"},
}


def register_connector_models(connector: Any) -> None:
    for action in connector.actions():
        names, required = _required_from_handler(connector, action)
        for action_group, spec in PARAMS.get(connector.name, {}).items():
            if action in action_group.split():
                for token in spec.split():
                    name = token.rstrip("!")
                    names.add(name)
                    if token.endswith("!"):
                        required.add(name)
        fields = {name: _field(name, name in required) for name in names}
        model = create_model(f"{connector.name.title().replace('_','')}{action.title().replace('_','')}Request", __base__=StrictModel, **fields)
        ACTION_FIELDS[f"{connector.name}.{action}"] = {"model": model}  # type: ignore[assignment]


def validate_action(connector: Any, action: str, params: dict[str, Any]) -> dict[str, Any]:
    key = f"{connector.name}.{action}"
    if key not in ACTION_FIELDS:
        register_connector_models(connector)
    model = ACTION_FIELDS[key]["model"]
    value = model.model_validate(params)
    return value.model_dump(mode="python")


def action_json_schema(connector: Any, action: str) -> dict[str, Any]:
    key = f"{connector.name}.{action}"
    if key not in ACTION_FIELDS:
        register_connector_models(connector)
    return ACTION_FIELDS[key]["model"].model_json_schema()


def secret_field_names(connector: Any, action: str) -> set[str]:
    schema = action_json_schema(connector, action)
    return {k for k, v in schema.get("properties", {}).items()
            if v.get("format") == "password" or v.get("writeOnly") is True}
