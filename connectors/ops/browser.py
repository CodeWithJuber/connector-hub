"""Headless browser-ish fetch connector (stdlib only core).

fetch / check_status work live with no credentials via urllib.
screenshot uses playwright (if importable) or wkhtmltoimage (if on PATH);
when neither is available it returns a structured "tooling missing" note
with ok=True so callers can degrade gracefully.

required_env=[] — nothing needed for fetch; mock is forced off.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

from hub.base import BaseConnector, ConnectorError, register
from hub.security import SecurityError, SecurityPolicy, pinned_urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 30


class _TextExtractor(HTMLParser):
    """Minimal HTML -> visible text stripper."""

    _SKIP = {"script", "style", "noscript", "head", "title"}

    def __init__(self):
        super().__init__()
        self._depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._depth += 1
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._depth > 0:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth == 0:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        lines = [ln.strip() for ln in raw.splitlines()]
        return "\n".join(ln for ln in lines if ln)


def _html_to_text(html):
    p = _TextExtractor()
    p.feed(html)
    return p.text()


@register
class OpsBrowserConnector(BaseConnector):
    name = "ops_browser"
    required_env = []
    description = "HTTP fetch / status checks / page screenshot (gated tooling)"

    def __init__(self, config=None):
        super().__init__(config)
        # fetch works with no credentials — always live.
        self.mock = False
        self.missing_env = []
        self.security = SecurityPolicy(self.config)

    def actions(self):
        return ["fetch", "check_status", "screenshot"]

    # --- helpers ------------------------------------------------------------
    def _open(self, url, method="GET", timeout=DEFAULT_TIMEOUT, max_bytes=2_000_000):
        return pinned_urlopen(self.security, url, method,
                              {"User-Agent": USER_AGENT, "Accept": "*/*"},
                              timeout, max_bytes)

    # --- live actions --------------------------------------------------------
    def _live(self, action, **params):
        if action == "fetch":
            url = params.get("url")
            if not url:
                raise ConnectorError(f"{self.name}: 'url' is required")
            try:
                resp = self._open(url, "GET")
                body = resp["body"]
                html = body.decode("utf-8", errors="replace")
                content_type = resp["headers"].get("Content-Type")
                out = {
                        "ok": resp["status"] < 400,
                        "url": resp["url"],
                        "status": resp["status"],
                        "content_type": content_type,
                        "bytes": len(body),
                    }
            except (OSError, SecurityError) as e:
                raise ConnectorError(f"{self.name}: fetch failed {url}: {e}")
            if params.get("extract_text"):
                out["text"] = _html_to_text(html)
            else:
                out["html"] = html
            return out

        if action == "check_status":
            urls = params.get("urls")
            if not urls or not isinstance(urls, (list, tuple)):
                raise ConnectorError(f"{self.name}: 'urls' (list) is required")

            def probe(u):
                for method in ("HEAD", "GET"):
                    try:
                        resp = self._open(u, method, timeout=15, max_bytes=1024)
                        if method == "HEAD" and resp["status"] in (400, 403, 405, 501):
                            continue
                        return {"url": resp["url"], "ok": resp["status"] < 400,
                                "status": resp["status"]}
                    except Exception as e:
                        return {"url": u, "ok": False, "status": None, "error": str(e)}
                return {"url": u, "ok": False, "status": None, "error": "probe failed"}

            with ThreadPoolExecutor(max_workers=min(8, max(1, len(urls)))) as pool:
                results = list(pool.map(probe, urls))
            return {"ok": True, "results": results}

        if action == "screenshot":
            url = params.get("url")
            if not url:
                raise ConnectorError(f"{self.name}: 'url' is required")
            out_path = params.get("out_path", "/tmp/ops_browser_screenshot.png")
            # Rendering engines cannot reliably pin DNS through redirects. Validate,
            # then require an explicit browser capability before using one.
            self.security.validate_url(url)
            try:
                self.security.require_capability(self.name, "browser_render")
            except SecurityError as e:
                raise ConnectorError(f"{self.name}: {e}")

            # A generic renderer cannot pin the policy-validated address. Keep
            # screenshots disabled until an isolated, policy-aware worker is used.
            return {
                "ok": False,
                "url": url,
                "note": "screenshot requires an isolated policy-aware renderer",
                "tool": None,
            }

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
