"""Web browse / retrieve / extract tools for CINTEXA BI.

Fetches public URLs, extracts readable text, and returns source metadata.
Never fabricates page content — failures are returned explicitly.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 1_500_000
MAX_TEXT_CHARS = 24_000
TIMEOUT = 25.0
USER_AGENT = (
    "CINTEXA-BI/1.0 (+https://cintexa.com; business-intelligence research bot)"
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []
        self._skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg", "iframe"):
            self._skip += 1
        if t == "title":
            self._in_title = True
        if t in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("script", "style", "noscript", "svg", "iframe") and self._skip:
            self._skip -= 1
        if t == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text[:300]
        self._chunks.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _is_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    found = re.findall(r"https?://[^\s\]\)\"'<>]+", text)
    cleaned = []
    for u in found:
        u = u.rstrip(".,;:)")
        if _is_http_url(u) and u not in cleaned:
            cleaned.append(u)
    return cleaned[:12]


async def fetch_url(url: str) -> Dict[str, Any]:
    """Fetch a URL and return extracted text + metadata."""
    if not _is_http_url(url):
        return {
            "ok": False,
            "url": url,
            "error": "Only http/https URLs are allowed",
        }
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8"},
        ) as client:
            resp = await client.get(url)
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            raw = resp.content[:MAX_BYTES]
            if resp.status_code >= 400:
                return {
                    "ok": False,
                    "url": str(resp.url),
                    "status": resp.status_code,
                    "error": f"HTTP {resp.status_code}",
                }
            if "application/json" in content_type:
                text = raw.decode("utf-8", errors="replace")[:MAX_TEXT_CHARS]
                return {
                    "ok": True,
                    "url": str(resp.url),
                    "status": resp.status_code,
                    "content_type": content_type,
                    "title": "JSON document",
                    "text": text,
                    "chars": len(text),
                }
            html = raw.decode("utf-8", errors="replace")
            parser = _TextExtractor()
            try:
                parser.feed(html)
            except Exception:
                pass
            text = parser.text()[:MAX_TEXT_CHARS]
            return {
                "ok": True,
                "url": str(resp.url),
                "status": resp.status_code,
                "content_type": content_type or "text/html",
                "title": parser.title or urlparse(str(resp.url)).path or "Page",
                "text": text,
                "chars": len(text),
            }
    except Exception as e:
        return {
            "ok": False,
            "url": url,
            "error": str(e)[:400],
        }


async def browse_urls(urls: List[str]) -> List[Dict[str, Any]]:
    results = []
    for u in urls[:8]:
        results.append(await fetch_url(u))
    return results


def format_browse_context(pages: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, p in enumerate(pages, 1):
        if not p.get("ok"):
            blocks.append(f"[Source {i}] FAILED {p.get('url')}: {p.get('error', 'unknown')}")
            continue
        snippet = (p.get("text") or "")[:8000]
        blocks.append(
            f"[Source {i}] title={p.get('title')}\nurl={p.get('url')}\n"
            f"status={p.get('status')} chars={p.get('chars')}\n---\n{snippet}\n---"
        )
    return "\n\n".join(blocks)
