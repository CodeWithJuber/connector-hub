"""Generic multi-account IMAP/SMTP email connector.

Accounts are configured via the EMAIL_ACCOUNTS env var as JSON, e.g.:

    EMAIL_ACCOUNTS='[
      {"id": "work", "host": "imap.gmail.com", "smtp_host": "smtp.gmail.com",
       "user": "a@gmail.com", "pass": "apppassword"},
      {"id": "personal", "host": "imap.example.com", "smtp_host": "smtp.example.com",
       "user": "b@example.com", "pass": "secret", "port": 993, "smtp_port": 465}
    ]'

Stdlib only (imaplib / smtplib / email.message). Passwords are never printed
or logged; list_accounts redacts all secret fields.
"""
import imaplib
import json
import smtplib
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.parser import Parser

from hub.base import BaseConnector, ConnectorError, register

DEFAULT_IMAP_PORT = 993
DEFAULT_SMTP_PORT = 465


@register
class ImapSmtpConnector(BaseConnector):
    name = "email"
    required_env = ["EMAIL_ACCOUNTS"]
    description = "Generic multi-account email via IMAP (read/search) and SMTP_SSL (send)."

    read_only_actions = frozenset(['list_accounts', 'check_inbox', 'search'])
    mutating_actions = frozenset(['send_email'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['send_email'])

    def actions(self):
        return ["list_accounts", "check_inbox", "send_email", "search"]

    # --- account config --------------------------------------------------
    def _accounts(self):
        raw = self.env("EMAIL_ACCOUNTS")
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as e:
            raise ConnectorError(f"{self.name}: EMAIL_ACCOUNTS is not valid JSON: {e}")
        if not isinstance(data, list):
            raise ConnectorError(f"{self.name}: EMAIL_ACCOUNTS must be a JSON list of accounts")
        for i, acct in enumerate(data):
            if not isinstance(acct, dict) or not acct.get("id"):
                raise ConnectorError(f"{self.name}: account #{i} missing required 'id'")
        return data

    def _account(self, account_id):
        for acct in self._accounts():
            if acct.get("id") == account_id:
                return acct
        known = ", ".join(a["id"] for a in self._accounts())
        raise ConnectorError(f"{self.name}: unknown account '{account_id}'. Known: {known}")

    # --- dispatch --------------------------------------------------------
    def _live(self, action, **params):
        if action == "list_accounts":
            return self._list_accounts()
        if action == "check_inbox":
            return self._check_inbox(
                params.get("account_id"), limit=int(params.get("limit", 10))
            )
        if action == "send_email":
            return self._send_email(
                params.get("account_id"),
                params.get("to"),
                params.get("subject", ""),
                params.get("body", ""),
                html=params.get("html"),
            )
        if action == "search":
            return self._search(params.get("account_id"), params.get("query", ""))
        raise ConnectorError(f"{self.name}: unhandled action '{action}'")

    # --- actions ---------------------------------------------------------
    def _list_accounts(self):
        accounts = []
        for acct in self._accounts():
            accounts.append({
                "id": acct.get("id"),
                "user": acct.get("user"),
                "host": acct.get("host"),
                "port": int(acct.get("port", DEFAULT_IMAP_PORT)),
                "smtp_host": acct.get("smtp_host"),
                "smtp_port": int(acct.get("smtp_port", DEFAULT_SMTP_PORT)),
                # never expose 'pass' or any other secret field
            })
        return {"ok": True, "accounts": accounts, "count": len(accounts)}

    def _imap(self, acct):
        host = acct.get("host")
        if not host or not acct.get("user") or not acct.get("pass"):
            raise ConnectorError(
                f"{self.name}: account '{acct.get('id')}' needs host, user and pass"
            )
        try:
            conn = imaplib.IMAP4_SSL(host, int(acct.get("port", DEFAULT_IMAP_PORT)))
            conn.login(acct["user"], acct["pass"])
            return conn
        except imaplib.IMAP4.error as e:
            raise ConnectorError(f"{self.name}: IMAP auth/connect failed for '{acct.get('id')}': {e}")
        except OSError as e:
            raise ConnectorError(f"{self.name}: IMAP connection to {host} failed: {e}")

    def _fetch_headers(self, conn, ids):
        messages = []
        for mid in ids:
            typ, data = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                continue
            hdrs = Parser().parsestr(data[0][1].decode(errors="replace"))
            messages.append({
                "id": mid.decode() if isinstance(mid, bytes) else str(mid),
                "subject": self._decode_hdr(hdrs.get("Subject", "")),
                "from": self._decode_hdr(hdrs.get("From", "")),
                "date": hdrs.get("Date", ""),
            })
        return messages

    @staticmethod
    def _decode_hdr(value):
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return value

    def _check_inbox(self, account_id, limit=10):
        acct = self._account(account_id)
        conn = self._imap(acct)
        try:
            typ, _ = conn.select("INBOX", readonly=True)
            if typ != "OK":
                raise ConnectorError(f"{self.name}: cannot open INBOX for '{account_id}'")
            typ, data = conn.search(None, "ALL")
            if typ != "OK":
                raise ConnectorError(f"{self.name}: IMAP search failed for '{account_id}'")
            ids = data[0].split()
            latest = ids[-limit:] if limit > 0 else ids
            messages = self._fetch_headers(conn, list(reversed(latest)))
            return {
                "ok": True,
                "account": account_id,
                "total": len(ids),
                "count": len(messages),
                "messages": messages,
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def _search(self, account_id, query):
        if not query:
            raise ConnectorError(f"{self.name}: search requires 'query'")
        acct = self._account(account_id)
        conn = self._imap(acct)
        try:
            typ, _ = conn.select("INBOX", readonly=True)
            if typ != "OK":
                raise ConnectorError(f"{self.name}: cannot open INBOX for '{account_id}'")
            criteria = f'(TEXT "{query}")'
            try:
                typ, data = conn.search("UTF-8", criteria) if any(ord(c) > 127 for c in query) \
                    else conn.search(None, criteria)
            except imaplib.IMAP4.error:
                typ, data = conn.search(None, criteria)
            if typ != "OK":
                raise ConnectorError(f"{self.name}: IMAP search failed for '{account_id}'")
            ids = data[0].split()
            messages = self._fetch_headers(conn, list(reversed(ids[-50:])))
            return {
                "ok": True,
                "account": account_id,
                "query": query,
                "count": len(ids),
                "messages": messages,
            }
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    def _send_email(self, account_id, to, subject, body, html=None):
        if not to:
            raise ConnectorError(f"{self.name}: send_email requires 'to'")
        acct = self._account(account_id)
        smtp_host = acct.get("smtp_host") or acct.get("host")
        smtp_port = int(acct.get("smtp_port", DEFAULT_SMTP_PORT))
        if not smtp_host or not acct.get("user") or not acct.get("pass"):
            raise ConnectorError(
                f"{self.name}: account '{account_id}' needs smtp_host, user and pass"
            )

        msg = EmailMessage()
        msg["From"] = acct["user"]
        msg["To"] = to
        msg["Subject"] = subject or ""
        msg.set_content(body or "")
        if html:
            msg.add_alternative(html, subtype="html")

        recipients = [r.strip() for r in str(to).split(",") if r.strip()]
        try:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as smtp:
                smtp.login(acct["user"], acct["pass"])
                refused = smtp.send_message(msg, to_addrs=recipients)
        except smtplib.SMTPAuthenticationError as e:
            raise ConnectorError(f"{self.name}: SMTP auth failed for '{account_id}' ({e.smtp_code})")
        except (smtplib.SMTPException, OSError) as e:
            raise ConnectorError(f"{self.name}: SMTP send via {smtp_host} failed: {e}")
        if refused:
            raise ConnectorError(f"{self.name}: recipients refused: {list(refused)}")
        return {
            "ok": True,
            "account": account_id,
            "to": recipients,
            "subject": subject or "",
            "message": "sent",
        }
