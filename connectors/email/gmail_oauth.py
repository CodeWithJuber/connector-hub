"""Gmail OAuth2 multi-account connector.

Env configuration:

    GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
    GOOGLE_CLIENT_SECRET=xxx
    GMAIL_ACCOUNTS=work:a@gmail.com,personal:b@gmail.com   # label:email pairs
    GMAIL_REFRESH_TOKEN_WORK=1//...                        # per-label refresh token
    GMAIL_REFRESH_TOKEN_PERSONAL=1//...

Create refresh tokens with scripts/setup_oauth.py. Stdlib only: Gmail REST API
via self.http_json, token refresh via urllib with a urlencoded form.
Refresh tokens are never printed or logged.
"""
import base64
import json
import urllib.parse
import urllib.request
import urllib.error
from email.message import EmailMessage

from hub.base import BaseConnector, ConnectorError, register

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


@register
class GmailOAuthConnector(BaseConnector):
    name = "gmail"
    required_env = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]
    description = "Gmail multi-account via OAuth2 refresh tokens (REST API, stdlib only)."

    def actions(self):
        return ["list_accounts", "get_access_token", "send", "list_messages", "get_message"]

    # --- account config --------------------------------------------------
    def _accounts(self):
        """Return {label: email} parsed from GMAIL_ACCOUNTS."""
        raw = self.env("GMAIL_ACCOUNTS", "") or ""
        accounts = {}
        for pair in raw.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" not in pair:
                raise ConnectorError(
                    f"{self.name}: GMAIL_ACCOUNTS entry '{pair}' must be 'label:email'"
                )
            label, email = pair.split(":", 1)
            accounts[label.strip()] = email.strip()
        return accounts

    def _require_label(self, label):
        if not label:
            raise ConnectorError(f"{self.name}: action requires 'label'")
        accounts = self._accounts()
        if accounts and label not in accounts:
            raise ConnectorError(
                f"{self.name}: unknown label '{label}'. Known: {', '.join(accounts)}"
            )
        return label

    def _refresh_token(self, label):
        token = self.env(f"GMAIL_REFRESH_TOKEN_{label.upper()}")
        if not token:
            raise ConnectorError(
                f"{self.name}: missing GMAIL_REFRESH_TOKEN_{label.upper()} — "
                "run scripts/setup_oauth.py to create one"
            )
        return token

    # --- OAuth token refresh (urlencoded form; http_json sends JSON) -----
    def _refresh_access_token(self, label):
        form = urllib.parse.urlencode({
            "client_id": self.env("GOOGLE_CLIENT_ID"),
            "client_secret": self.env("GOOGLE_CLIENT_SECRET"),
            "refresh_token": self._refresh_token(label),
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request(TOKEN_URL, data=form, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            # do not include request data (secrets) in the error
            raise ConnectorError(
                f"{self.name}: token refresh for '{label}' failed HTTP {e.code}: "
                f"{e.read().decode(errors='replace')[:300]}"
            )
        except urllib.error.URLError as e:
            raise ConnectorError(f"{self.name}: token endpoint unreachable: {e.reason}")
        access = data.get("access_token")
        if not access:
            raise ConnectorError(f"{self.name}: token refresh for '{label}' returned no access_token")
        return access

    def _headers(self, label):
        return {"Authorization": f"Bearer {self._refresh_access_token(label)}"}

    # --- dispatch --------------------------------------------------------
    def _live(self, action, **params):
        if action == "list_accounts":
            return {"ok": True, "accounts": [
                {"label": label, "email": email,
                 "has_refresh_token": bool(self.env(f"GMAIL_REFRESH_TOKEN_{label.upper()}"))}
                for label, email in self._accounts().items()
            ]}
        if action == "get_access_token":
            label = self._require_label(params.get("label"))
            token = self._refresh_access_token(label)
            return {"ok": True, "label": label, "access_token": token,
                    "token_type": "Bearer"}
        if action == "send":
            return self._send(
                self._require_label(params.get("label")),
                params.get("to"),
                params.get("subject", ""),
                params.get("body", ""),
            )
        if action == "list_messages":
            return self._list_messages(
                self._require_label(params.get("label")),
                query=params.get("query"),
                max_results=params.get("max_results"),
            )
        if action == "get_message":
            return self._get_message(
                self._require_label(params.get("label")),
                params.get("message_id"),
            )
        raise ConnectorError(f"{self.name}: unhandled action '{action}'")

    # --- Gmail API actions ------------------------------------------------
    def _send(self, label, to, subject, body):
        if not to:
            raise ConnectorError(f"{self.name}: send requires 'to'")
        msg = EmailMessage()
        msg["From"] = self._accounts().get(label, "me")
        msg["To"] = to
        msg["Subject"] = subject or ""
        msg.set_content(body or "")
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        resp = self.http_json(
            "POST", f"{API_BASE}/messages/send",
            headers=self._headers(label), payload={"raw": raw},
        )
        data = resp["data"]
        return {"ok": True, "label": label, "id": data.get("id"),
                "threadId": data.get("threadId"), "message": "sent"}

    def _list_messages(self, label, query=None, max_results=None):
        qs = {}
        if query:
            qs["q"] = query
        if max_results:
            qs["maxResults"] = int(max_results)
        url = f"{API_BASE}/messages"
        if qs:
            url += "?" + urllib.parse.urlencode(qs)
        resp = self.http_json("GET", url, headers=self._headers(label))
        data = resp["data"]
        return {
            "ok": True,
            "label": label,
            "messages": data.get("messages", []),
            "resultSizeEstimate": data.get("resultSizeEstimate", 0),
            "nextPageToken": data.get("nextPageToken"),
        }

    def _get_message(self, label, message_id):
        if not message_id:
            raise ConnectorError(f"{self.name}: get_message requires 'message_id'")
        resp = self.http_json(
            "GET",
            f"{API_BASE}/messages/{urllib.parse.quote(str(message_id))}?format=full",
            headers=self._headers(label),
        )
        data = resp["data"]
        headers = {h["name"]: h["value"]
                   for h in data.get("payload", {}).get("headers", [])}
        return {
            "ok": True,
            "label": label,
            "id": data.get("id"),
            "threadId": data.get("threadId"),
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": data.get("snippet", ""),
            "labelIds": data.get("labelIds", []),
        }
