"""WHM (WebHost Manager) and cPanel connectors in one module.

WHM live mode:   GET/POST https://{WHM_HOST}:2087/json-api/<func>?api.version=1
                 Authorization: whm <user>:<token>
cPanel live mode: GET/POST https://{CPANEL_HOST}:2083/execute/<Module>/<func>
                 Authorization: cpanel <user>:<token>
"""
import urllib.parse

from hub.base import BaseConnector, ConnectorError, register


class _TokenPanelConnector(BaseConnector):
    """Shared plumbing for WHM/cPanel token-auth JSON APIs.

    Subclasses set env_prefix ("WHM"/"CPANEL"), default_port and auth_scheme.
    """

    env_prefix = ""
    default_port = 2087
    auth_scheme = "whm"

    def _base(self):
        host = (self.env(f"{self.env_prefix}_HOST") or "").strip()
        if not host:
            raise ConnectorError(f"{self.name}: {self.env_prefix}_HOST is not set")
        host = host.replace("https://", "").replace("http://", "").rstrip("/")
        return f"https://{host}:{self.default_port}"

    def _headers(self):
        user = self.env(f"{self.env_prefix}_USER")
        token = self.env(f"{self.env_prefix}_API_TOKEN")
        return {"Authorization": f"{self.auth_scheme} {user}:{token}"}

    def _request(self, path, params=None, method="GET"):
        """path is '/json-api/<func>' or '/execute/<Module>/<func>'."""
        params = {k: v for k, v in (params or {}).items() if v is not None}
        url = f"{self._base()}{path}"
        if method.upper() == "GET" or not params:
            if params:
                sep = "&" if "?" in url else "?"
                url += sep + urllib.parse.urlencode(params)
            result = self.http_json("GET", url, headers=self._headers())
        else:
            # WHM/cPanel accept URL-encoded POST bodies.
            encoded = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            result = self.http_json(
                "POST", f"{url}{sep}{encoded}", headers=self._headers()
            )
        data = result.get("data", {})
        # WHM JSON-API wraps results in metadata with result=0 on failure.
        meta = data.get("metadata") if isinstance(data, dict) else None
        if isinstance(meta, dict) and meta.get("result") == 0:
            raise ConnectorError(
                f"{self.name} API error: {meta.get('reason', 'unknown')}"
            )
        # UAPI (/execute/*) uses {"errors": [...], "status": 0} on failure.
        if isinstance(data, dict) and data.get("status") == 0 and data.get("errors"):
            raise ConnectorError(
                f"{self.name} UAPI error: {'; '.join(map(str, data['errors']))}"
            )
        return result


@register
class WHMConnector(_TokenPanelConnector):
    """WHM root/reseller server administration."""

    name = "whm"
    required_env = ["WHM_HOST", "WHM_USER", "WHM_API_TOKEN"]
    description = "WHM: accounts, packages, DNS zones, server status"
    env_prefix = "WHM"
    default_port = 2087
    auth_scheme = "whm"

    read_only_actions = frozenset(['list_accounts', 'list_packages', 'server_status', 'list_zones', 'version'])
    mutating_actions = frozenset(['create_account', 'suspend_account', 'unsuspend_account'])
    destructive_actions = frozenset(['terminate_account'])
    dry_run_actions = frozenset(['create_account', 'suspend_account', 'unsuspend_account', 'terminate_account'])

    def actions(self):
        return [
            "list_accounts",
            "create_account",
            "suspend_account",
            "unsuspend_account",
            "terminate_account",
            "list_packages",
            "server_status",
            "list_zones",
            "version",
        ]

    def _whm(self, func, params=None, method="GET"):
        base = f"/json-api/{func}?api.version=1"
        return self._request(base, params=params, method=method)

    def _live(self, action, **params):
        if action == "list_accounts":
            return self._whm("listaccts")

        if action == "create_account":
            required = ["domain", "username", "password"]
            missing = [k for k in required if not params.get(k)]
            if missing:
                raise ConnectorError(
                    f"whm create_account missing required: {', '.join(missing)}"
                )
            fields = {k: params[k] for k in required}
            if params.get("plan"):
                fields["plan"] = params["plan"]
            if params.get("contactemail"):
                fields["contactemail"] = params["contactemail"]
            return self._whm("createacct", fields, method="POST")

        if action == "suspend_account":
            user = params.get("user")
            if not user:
                raise ConnectorError("whm suspend_account requires user")
            fields = {"user": user}
            if params.get("reason"):
                fields["reason"] = params["reason"]
            return self._whm("suspendacct", fields, method="POST")

        if action == "unsuspend_account":
            user = params.get("user")
            if not user:
                raise ConnectorError("whm unsuspend_account requires user")
            return self._whm("unsuspendacct", {"user": user}, method="POST")

        if action == "terminate_account":
            user = params.get("user")
            if not user:
                raise ConnectorError("whm terminate_account requires user")
            fields = {"user": user}
            if params.get("keepdns"):
                fields["keepdns"] = 1
            return self._whm("removeacct", fields, method="POST")

        if action == "list_packages":
            return self._whm("listpkgs")

        if action == "server_status":
            return self._whm("servicestatus")

        if action == "list_zones":
            return self._whm("listzones")

        if action == "version":
            return self._whm("version")

        raise ConnectorError(f"whm: unhandled action '{action}'")


@register
class CPanelConnector(_TokenPanelConnector):
    """cPanel end-user account automation (UAPI)."""

    name = "cpanel"
    required_env = ["CPANEL_HOST", "CPANEL_USER", "CPANEL_API_TOKEN"]
    description = "cPanel UAPI: domains, email, databases, files, cron, disk"
    env_prefix = "CPANEL"
    default_port = 2083
    auth_scheme = "cpanel"

    read_only_actions = frozenset(['list_domains', 'list_email_accounts', 'list_databases', 'file_list', 'cron_list', 'disk_usage'])
    mutating_actions = frozenset(['add_subdomain', 'add_email', 'create_database', 'create_db_user', 'cron_add'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['add_subdomain', 'add_email', 'create_database', 'create_db_user', 'cron_add'])

    def actions(self):
        return [
            "list_domains",
            "add_subdomain",
            "list_email_accounts",
            "add_email",
            "list_databases",
            "create_database",
            "create_db_user",
            "file_list",
            "cron_list",
            "cron_add",
            "disk_usage",
        ]

    def _uapi(self, module, func, params=None, method="GET"):
        return self._request(f"/execute/{module}/{func}", params=params, method=method)

    def _live(self, action, **params):
        if action == "list_domains":
            return self._uapi("DomainInfo", "domains_data", {"format": "hash"})

        if action == "add_subdomain":
            required = ["subdomain", "rootdomain", "dir"]
            missing = [k for k in required if not params.get(k)]
            if missing:
                raise ConnectorError(
                    f"cpanel add_subdomain missing required: {', '.join(missing)}"
                )
            fields = {
                "domain": params["subdomain"],
                "rootdomain": params["rootdomain"],
                "dir": params["dir"],
            }
            return self._uapi("SubDomain", "addsubdomain", fields, method="POST")

        if action == "list_email_accounts":
            return self._uapi("Email", "list_pops")

        if action == "add_email":
            if not params.get("email") or not params.get("password"):
                raise ConnectorError("cpanel add_email requires email and password")
            fields = {
                "email": params["email"],
                "password": params["password"],
                "quota": params.get("quota", 250),
            }
            return self._uapi("Email", "add_pop", fields, method="POST")

        if action == "list_databases":
            return self._uapi("Mysql", "list_databases")

        if action == "create_database":
            name = params.get("name")
            if not name:
                raise ConnectorError("cpanel create_database requires name")
            return self._uapi("Mysql", "create_database", {"name": name},
                              method="POST")

        if action == "create_db_user":
            if not params.get("user") or not params.get("password"):
                raise ConnectorError(
                    "cpanel create_db_user requires user and password"
                )
            fields = {"name": params["user"], "password": params["password"]}
            return self._uapi("Mysql", "create_user", fields, method="POST")

        if action == "file_list":
            directory = params.get("dir", ".")
            return self._uapi("Fileman", "list_files",
                              {"dir": directory, "types": "file|dir"})

        if action == "cron_list":
            return self._uapi("Cron", "list_cron")

        if action == "cron_add":
            if not params.get("command"):
                raise ConnectorError("cpanel cron_add requires command")
            fields = {
                "command": params["command"],
                "minute": params.get("minute", "0"),
                "hour": params.get("hour", "0"),
                "day": params.get("day", "*"),
                "month": params.get("month", "*"),
                "weekday": params.get("weekday", "*"),
            }
            return self._uapi("Cron", "add_line", fields, method="POST")

        if action == "disk_usage":
            return self._uapi("Quota", "get_quota_info")

        raise ConnectorError(f"cpanel: unhandled action '{action}'")
