"""Headless browser-ish fetch connector (stdlib only core).

fetch / check_status work live with no credentials via urllib.
screenshot uses playwright (if importable) or wkhtmltoimage (if on PATH);
when neither is available it returns a structured "tooling missing" note
with ok=True so callers can degrade gracefully.

required_env=[] — nothing needed for fetch; mock is forced off.
"""
import shutil
import socket
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

from hub.base import BaseConnector, ConnectorError, register

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

    read_only_actions = frozenset(['fetch', 'check_status'])
    mutating_actions = frozenset(['screenshot'])
    destructive_actions = frozenset([])
    dry_run_actions = frozenset(['screenshot'])

    def actions(self):
        return ["fetch", "check_status", "screenshot"]

    # --- helpers ------------------------------------------------------------
    def _open(self, url, method="GET", timeout=DEFAULT_TIMEOUT):
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Accept", "*/*")
        return urllib.request.urlopen(req, timeout=timeout)

    # --- live actions --------------------------------------------------------
    def _live(self, action, **params):
        if action == "fetch":
            url = params.get("url")
            if not url:
                raise ConnectorError(f"{self.name}: 'url' is required")
            try:
                with self._open(url, "GET") as resp:
                    body = resp.read(2_000_000)
                    charset = resp.headers.get_content_charset() or "utf-8"
                    html = body.decode(charset, errors="replace")
                    out = {
                        "ok": True,
                        "url": url,
                        "status": resp.status,
                        "content_type": resp.headers.get("Content-Type"),
                        "bytes": len(body),
                    }
            except urllib.error.HTTPError as e:
                return {"ok": False, "url": url, "status": e.code, "error": str(e)}
            except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
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
                        with self._open(u, method, timeout=15) as resp:
                            return {"url": u, "ok": True, "status": resp.status}
                    except urllib.error.HTTPError as e:
                        # Some servers reject HEAD; retry once with GET.
                        if method == "HEAD" and e.code in (400, 403, 405, 501):
                            continue
                        return {"url": u, "ok": e.code < 400, "status": e.code,
                                "error": str(e)}
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

            # Preferred: playwright (lazy import, optional dependency).
            try:
                from playwright.sync_api import sync_playwright  # noqa: F401
                with sync_playwright() as p:
                    browser = p.chromium.launch()
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(url, timeout=DEFAULT_TIMEOUT * 1000)
                    page.screenshot(path=out_path, full_page=True)
                    browser.close()
                return {"ok": True, "url": url, "path": out_path, "tool": "playwright"}
            except ImportError:
                pass
            except Exception as e:
                raise ConnectorError(f"{self.name}: playwright screenshot failed: {e}")

            # Fallback: wkhtmltoimage binary if present.
            if shutil.which("wkhtmltoimage"):
                import subprocess
                proc = subprocess.run(
                    ["wkhtmltoimage", "--quiet", url, out_path],
                    capture_output=True, text=True, timeout=60,
                )
                if proc.returncode == 0:
                    return {"ok": True, "url": url, "path": out_path,
                            "tool": "wkhtmltoimage"}
                raise ConnectorError(
                    f"{self.name}: wkhtmltoimage failed: {proc.stderr[:300]}"
                )

            # No rendering tool available: explicitly report non-execution.
            return {
                "ok": False,
                "executed": False,
                "state": "dependency_required",
                "url": url,
                "note": "screenshot tooling missing: install 'playwright' "
                        "(+ playwright install chromium) or 'wkhtmltoimage'",
                "tool": None,
            }

        raise ConnectorError(f"{self.name}: unhandled action '{action}'")
