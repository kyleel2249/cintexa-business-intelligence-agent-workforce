"""Mock browser/social/video platforms for safe testing."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List
from urllib.parse import urlparse


class MockBrowserProvider:
    name = "mock"

    def __init__(self):
        self.pages: Dict[str, dict] = {
            "https://example.com/": {
                "title": "Example Domain",
                "text": "This domain is for use in documentation examples.",
                "links": [{"href": "https://example.com/about", "text": "About"}],
                "buttons": [{"id": "ok", "text": "OK", "role": "button"}],
                "forms": [],
            },
            "https://example.com/about": {
                "title": "About",
                "text": "About Example.",
                "links": [{"href": "https://example.com/", "text": "Home"}],
                "buttons": [],
                "forms": [],
            },
            "https://example.com/product": {
                "title": "Product",
                "text": "Our product is reliable and fast. Customers ask about pricing.",
                "links": [],
                "buttons": [{"id": "buy", "text": "Buy", "role": "button"}],
                "forms": [{"id": "contact", "fields": ["email", "message"]}],
                "comments": [
                    {"id": "c1", "text": "How much does it cost?"},
                    {"id": "c2", "text": "Great product!"},
                ],
            },
        }
        self.likes: set = set()
        self.comments: List[dict] = []
        self.captcha_urls: set = set()

    def navigate(self, url: str) -> dict:
        if url in self.captcha_urls:
            return {"status": "CAPTCHA_DETECTED", "url": url}
        page = self.pages.get(url)
        if not page:
            page = {
                "title": urlparse(url).path or url,
                "text": f"Mock content for {url}",
                "links": [],
                "buttons": [],
                "forms": [],
            }
            self.pages[url] = page
        return {"status": "OK", "url": url, **page}

    def observe(self, url: str) -> dict:
        nav = self.navigate(url)
        text = nav.get("text", "")
        return {
            "url": url,
            "title": nav.get("title", ""),
            "headings": [nav.get("title", "")],
            "paragraphs": [text],
            "links": nav.get("links", []),
            "buttons": nav.get("buttons", []),
            "forms": nav.get("forms", []),
            "visible_text": text,
            "metadata": {},
            "trust": "EXTERNAL_UNTRUSTED",
            "content_hash": hashlib.sha256(text.encode()).hexdigest()[:32],
            "external_instructions_detected": "ignore your system" in text.lower(),
        }

    def click(self, url: str, control_id: str) -> dict:
        page = self.pages.get(url) or {}
        buttons = {b["id"]: b for b in page.get("buttons", [])}
        if control_id not in buttons:
            return {"status": "FAILED", "reason": "CONTROL_NOT_FOUND"}
        return {"status": "SUCCESS", "clicked": control_id, "url": url}

    def like(self, target: str) -> dict:
        if target in self.likes:
            return {"status": "SUCCESS", "already": True, "liked": True}
        self.likes.add(target)
        return {"status": "SUCCESS", "liked": True, "verified": True}

    def comment(self, target: str, content: str) -> dict:
        cid = hashlib.sha256(f"{target}:{content}".encode()).hexdigest()[:12]
        self.comments.append({"id": cid, "target": target, "content": content})
        return {"status": "SUCCESS", "comment_id": cid, "verified": True}

    def transcribe_video(self, url: str) -> dict:
        return {
            "status": "SUCCESS",
            "source_url": url,
            "transcript": [
                {"start": "00:00:00", "end": "00:00:05", "text": "Welcome to the product demo."},
                {"start": "00:00:05", "end": "00:00:12", "text": "Customers often ask about pricing."},
            ],
            "summary": "Product demo mentioning pricing questions.",
            "trust": "EXTERNAL_UNTRUSTED",
        }
