"""Full-permission GitHub connector (user's own account, PAT with full scopes).

Env:
  GITHUB_TOKEN      classic PAT or fine-grained token (repo + workflow + admin scopes)
  GITHUB_API_BASE   optional, default https://api.github.com (set for GitHub Enterprise)

Stdlib only. Token is never logged or included in returned payloads.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from hub.base import BaseConnector, ConnectorError, register  # noqa: E402

_API_VERSION = "2022-11-28"


@register
class GitHubConnector(BaseConnector):
    """Full-scope GitHub REST connector driven by a personal access token."""

    name = "github"
    required_env = ["GITHUB_TOKEN"]
    description = "GitHub REST API, full scope (repos, files, issues, PRs, actions, secrets meta, webhooks, search)"

    def __init__(self, config=None):
        super().__init__(config)
        self.api_base = (self.config.get("api_base") or self.env(
            "GITHUB_API_BASE", "https://api.github.com")).rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {self.env('GITHUB_TOKEN', '')}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }

    # --- contract --------------------------------------------------------
    def actions(self):
        return [
            "get_me",
            "list_repos", "get_repo", "create_repo", "delete_repo",
            "list_branches", "create_branch",
            "get_file", "put_file", "delete_file",
            "list_issues", "create_issue", "comment_issue", "close_issue",
            "list_prs", "create_pr", "merge_pr", "review_pr",
            "list_workflows", "dispatch_workflow", "list_workflow_runs",
            "list_secrets_meta", "create_webhook",
            "search_code", "search_repos",
        ]

    def _live(self, action, **params):
        handler = getattr(self, f"_do_{action}")
        return handler(**params)

    # --- HTTP helpers ----------------------------------------------------
    def _gh(self, method, path, payload=None, query=None):
        """Call the GitHub API via self.http_json."""
        url = f"{self.api_base}{path}"
        if query:
            q = urllib.parse.urlencode(
                {k: v for k, v in query.items() if v is not None})
            if q:
                url = f"{url}?{q}"
        res = self.http_json(method, url, headers=self._headers, payload=payload)
        return {"ok": True, "status": res["status"], "data": res["data"]}

    def _gh_delete_with_body(self, path, payload):
        """DELETE requests that require a JSON body (urllib does not send a
        body for DELETE via http_json unless forced)."""
        url = f"{self.api_base}{path}"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="DELETE")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Content-Type", "application/json")
        for k, v in self._headers.items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode() or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"raw": raw}
                return {"ok": True, "status": resp.status, "data": data}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise ConnectorError(f"{self.name} HTTP {e.code} {url}: {detail}")
        except urllib.error.URLError as e:
            raise ConnectorError(f"{self.name} connection failed {url}: {e.reason}")

    # --- account ---------------------------------------------------------
    def _do_get_me(self):
        return self._gh("GET", "/user")

    # --- repos -----------------------------------------------------------
    def _do_list_repos(self, visibility=None, per_page=None):
        return self._gh("GET", "/user/repos", query={
            "visibility": visibility,
            "per_page": per_page or 30,
        })

    def _do_get_repo(self, owner, repo):
        return self._gh("GET", f"/repos/{owner}/{repo}")

    def _do_create_repo(self, name, private=None, description=None):
        payload = {"name": name}
        if private is not None:
            payload["private"] = bool(private)
        if description is not None:
            payload["description"] = description
        return self._gh("POST", "/user/repos", payload=payload)

    def _do_delete_repo(self, owner, repo):
        return self._gh("DELETE", f"/repos/{owner}/{repo}")

    # --- branches --------------------------------------------------------
    def _do_list_branches(self, owner, repo):
        return self._gh("GET", f"/repos/{owner}/{repo}/branches")

    def _do_create_branch(self, owner, repo, branch, from_branch=None):
        if from_branch:
            ref_path = f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        else:
            # default branch of the repo
            ref_path = f"/repos/{owner}/{repo}/git/ref/HEAD"
        res = self._gh("GET", ref_path)
        sha = res["data"]["object"]["sha"]
        return self._gh("POST", f"/repos/{owner}/{repo}/git/refs",
                        payload={"ref": f"refs/heads/{branch}", "sha": sha})

    # --- files -----------------------------------------------------------
    def _do_get_file(self, owner, repo, path, ref=None):
        qpath = urllib.parse.quote(path, safe="/")
        res = self._gh("GET", f"/repos/{owner}/{repo}/contents/{qpath}",
                       query={"ref": ref})
        data = res["data"]
        if isinstance(data, dict) and data.get("encoding") == "base64" and "content" in data:
            try:
                decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            except (ValueError, TypeError) as e:
                raise ConnectorError(f"{self.name}: failed to decode content for {path}: {e}")
            data = dict(data)
            data["decoded_content"] = decoded
        res["data"] = data
        return res

    def _do_put_file(self, owner, repo, path, content, message, branch=None, sha=None):
        qpath = urllib.parse.quote(path, safe="/")
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        }
        if branch:
            payload["branch"] = branch
        if sha:
            payload["sha"] = sha
        return self._gh("PUT", f"/repos/{owner}/{repo}/contents/{qpath}",
                        payload=payload)

    def _do_delete_file(self, owner, repo, path, message, sha):
        qpath = urllib.parse.quote(path, safe="/")
        return self._gh_delete_with_body(
            f"/repos/{owner}/{repo}/contents/{qpath}",
            {"message": message, "sha": sha})

    # --- issues ----------------------------------------------------------
    def _do_list_issues(self, owner, repo, state=None):
        return self._gh("GET", f"/repos/{owner}/{repo}/issues",
                        query={"state": state or "open"})

    def _do_create_issue(self, owner, repo, title, body=None, labels=None):
        payload = {"title": title}
        if body is not None:
            payload["body"] = body
        if labels:
            payload["labels"] = labels
        return self._gh("POST", f"/repos/{owner}/{repo}/issues", payload=payload)

    def _do_comment_issue(self, owner, repo, number, body):
        return self._gh("POST", f"/repos/{owner}/{repo}/issues/{number}/comments",
                        payload={"body": body})

    def _do_close_issue(self, owner, repo, number):
        return self._gh("PATCH", f"/repos/{owner}/{repo}/issues/{number}",
                        payload={"state": "closed"})

    # --- pull requests ---------------------------------------------------
    def _do_list_prs(self, owner, repo, state=None):
        return self._gh("GET", f"/repos/{owner}/{repo}/pulls",
                        query={"state": state or "open"})

    def _do_create_pr(self, owner, repo, title, head, base, body=None):
        payload = {"title": title, "head": head, "base": base}
        if body is not None:
            payload["body"] = body
        return self._gh("POST", f"/repos/{owner}/{repo}/pulls", payload=payload)

    def _do_merge_pr(self, owner, repo, number, method="merge"):
        return self._gh("PUT", f"/repos/{owner}/{repo}/pulls/{number}/merge",
                        payload={"merge_method": method})

    def _do_review_pr(self, owner, repo, number, event="APPROVE", body=None):
        payload = {"event": event}
        if body is not None:
            payload["body"] = body
        return self._gh("POST", f"/repos/{owner}/{repo}/pulls/{number}/reviews",
                        payload=payload)

    # --- actions / workflows ---------------------------------------------
    def _do_list_workflows(self, owner, repo):
        return self._gh("GET", f"/repos/{owner}/{repo}/actions/workflows")

    def _do_dispatch_workflow(self, owner, repo, workflow_id, ref="main", inputs=None):
        payload = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        return self._gh("POST",
                        f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches",
                        payload=payload)

    def _do_list_workflow_runs(self, owner, repo):
        return self._gh("GET", f"/repos/{owner}/{repo}/actions/runs")

    # --- secrets meta / webhooks ------------------------------------------
    def _do_list_secrets_meta(self, owner, repo):
        """List secret names only — never values."""
        res = self._gh("GET", f"/repos/{owner}/{repo}/actions/secrets")
        secrets = res["data"].get("secrets", []) if isinstance(res["data"], dict) else []
        return {
            "ok": True,
            "status": res["status"],
            "data": {
                "total_count": res["data"].get("total_count", len(secrets)),
                "secrets": [
                    {"name": s.get("name"),
                     "created_at": s.get("created_at"),
                     "updated_at": s.get("updated_at")}
                    for s in secrets
                ],
            },
        }

    def _do_create_webhook(self, owner, repo, url, events=None):
        return self._gh("POST", f"/repos/{owner}/{repo}/hooks", payload={
            "name": "web",
            "active": True,
            "events": events or ["push"],
            "config": {"url": url, "content_type": "json"},
        })

    # --- search ------------------------------------------------------------
    def _do_search_code(self, query):
        return self._gh("GET", "/search/code", query={"q": query})

    def _do_search_repos(self, query):
        return self._gh("GET", "/search/repositories", query={"q": query})
