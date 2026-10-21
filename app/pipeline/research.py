"""Fetch complete accepted source articles, with provenance, within resource bounds.

A fetched page is supporting material, not proof that a claim is true. External
text stays untrusted input for the scriptwriter; failed retrieval is recorded.
"""

import ipaddress
import json
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from urllib.parse import urljoin, urlsplit

import httpx

from app.db.models import TelegramPost
from app.config.settings import settings
from app.llm.context_budget import estimate_tokens


class _ArticleText(HTMLParser):
    """Read one semantic article, preserving its text instead of nearby cards."""

    void_tags = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    hidden_tags = {"script", "style", "noscript", "svg", "template"}
    block_tags = {
        "p",
        "div",
        "section",
        "article",
        "main",
        "header",
        "footer",
        "aside",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "ul",
        "ol",
        "blockquote",
        "table",
        "caption",
        "tr",
        "td",
        "th",
        "dl",
        "dt",
        "dd",
        "br",
        "hr",
        "title",
    }

    def __init__(self) -> None:
        super().__init__()
        self.root = ET.Element("document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = ET.SubElement(self.stack[-1], tag, {key: value or "" for key, value in attrs})
        if tag not in self.void_tags:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        node = self.stack[-1]
        if len(node):
            node[-1].tail = (node[-1].tail or "") + data
        else:
            node.text = (node.text or "") + data

    @property
    def title(self) -> str:
        node = self.root.find(".//title")
        return " ".join("".join(node.itertext()).split()) if node is not None else ""

    def _visible_nodes(self, root):
        pending = [root]
        while pending:
            node = pending.pop()
            if node.tag in self.hidden_tags or "hidden" in node.attrib:
                continue
            yield node
            pending.extend(reversed(node))

    @property
    def paragraphs(self) -> list[str]:
        nodes = list(self._visible_nodes(self.root))
        bodies = [node for node in nodes if "articleBody" in node.get("itemprop", "").split()]
        articles = [node for node in nodes if node.tag == "article"]
        headed = [
            node
            for node in articles
            if any(child.tag == "h1" for child in self._visible_nodes(node))
        ]
        mains = [node for node in nodes if node.tag == "main" or node.get("role") == "main"]
        visible_bodies = [node for node in bodies if node.tag != "meta"]
        candidates = visible_bodies or bodies or headed or articles or mains
        if len(candidates) != 1:
            return []  # Unknown scope or independent articles: do not mix sources.
        node = candidates[0]
        if node.tag == "meta":
            return node.get("content", "").splitlines()
        return self._render(node, root=True).strip("\n").splitlines()

    def _render(self, node, *, pre: bool = False, root: bool = False) -> str:
        if (
            node.tag in self.hidden_tags
            or "hidden" in node.attrib
            or (node.tag == "article" and not root)
        ):
            return ""
        preserve = pre or node.tag == "pre"

        def whitespace(text):
            return (text or "") if preserve else re.sub(r"\s+", " ", text or "")

        parts = [whitespace(node.text)]
        for child in node:
            parts.append(self._render(child, pre=preserve))
            parts.append(whitespace(child.tail))
        text = "".join(parts)
        block = node.tag == "pre" or (not preserve and node.tag in self.block_tags)
        return "\n" + text + "\n" if block else text


def post_article_urls(post: TelegramPost) -> list[str]:
    urls = re.findall(r"https?://[^\s<>]+", post.text)
    try:
        payload = json.loads(post.raw_json or "{}")
        urls.extend(
            entity["url"]
            for entity in payload.get("entities", [])
            if isinstance(entity, dict) and isinstance(entity.get("url"), str)
        )
    except (ValueError, TypeError, AttributeError):
        pass
    article_urls = []
    for url in urls:
        try:
            parsed = urlsplit(url)
            if parsed.username is not None or parsed.password is not None:
                continue
            if parsed.hostname not in {"t.me", "telegram.me", "www.t.me"}:
                article_urls.append(url.rstrip(".,;!?)\"'"))
        except ValueError:
            continue
    return list(dict.fromkeys(article_urls))


def _public_address(url: str) -> str | None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 80, 443}
    ):
        return None
    try:
        addresses = [ipaddress.ip_address(parsed.hostname)]
    except ValueError:
        addresses = [
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(
                parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM
            )
        ]
    if not addresses or not all(
        address.is_global and not address.is_multicast for address in addresses
    ):
        return None
    return str(sorted(addresses, key=lambda address: address.version)[0])


def fetch_article(url: str, *, client: httpx.Client) -> dict[str, str]:
    try:
        for _ in range(4):
            address = _public_address(url)
            if not address:
                return {"status": "blocked", "url": "blocked URL"}
            original = httpx.URL(url)
            # Connect to the checked IP, retaining certificate validation for the
            # original hostname. A second DNS lookup must not bypass the guard.
            with client.stream(
                "GET",
                original.copy_with(host=address),
                follow_redirects=False,
                timeout=8,
                headers={
                    "User-Agent": "ITPodcastBot/1.0",
                    "Accept": "text/html",
                    "Host": original.netloc.decode("ascii"),
                    "Connection": "close",
                },
                extensions={"sni_hostname": original.host},
            ) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                if "html" not in response.headers.get("content-type", ""):
                    return {"status": "unavailable", "url": url, "error": "not_html"}
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > 512_000:
                        return {"status": "unavailable", "url": url, "error": "page_too_large"}
                parser = _ArticleText()
                parser.feed(body.decode(response.encoding or "utf-8", errors="replace"))
                parser.close()
                paragraphs = parser.paragraphs
                text = "\n".join(paragraphs)
                if len(text) < 80:
                    return {"status": "unavailable", "url": url, "error": "no_article_text"}
                return {
                    "status": "fetched",
                    "url": url,
                    "title": parser.title
                    or next((line.strip() for line in paragraphs if line.strip()), ""),
                    "excerpt": text,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                }
        return {"status": "unavailable", "url": url, "error": "too_many_redirects"}
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        return {"status": "unavailable", "url": "unavailable URL", "error": type(exc).__name__}


def research_posts(
    posts: list[TelegramPost],
    output_path: Path,
    *,
    max_sources: int = 6,
) -> dict[int, list[dict[str, str]]]:
    sources: dict[int, list[dict[str, str]]] = {}
    cache: dict[str, dict[str, str]] = {}
    for post in posts:
        primary_loaded = False
        for url in post_article_urls(post):
            if primary_loaded or (url not in cache and len(cache) >= max_sources):
                sources.setdefault(post.id, []).append(
                    {
                        "status": "not_fetched",
                        "url": url,
                        "error": "primary_source_loaded"
                        if primary_loaded
                        else "research_request_budget_exhausted",
                    }
                )
                continue
            if url not in cache:
                # ponytail: isolated worker gives a hard deadline including DNS
                # and slow response headers; pool workers only if volume grows.
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "app.pipeline.research", url],
                        cwd=Path(__file__).resolve().parents[2],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=20,
                    )
                    cache[url] = json.loads(result.stdout)
                except (subprocess.SubprocessError, OSError, ValueError) as exc:
                    cache[url] = {"status": "unavailable", "error": type(exc).__name__}
            record = {"url": url, **cache[url], "requested_url": url}
            if (
                record.get("status") == "fetched"
                and estimate_tokens(post.text + record["excerpt"])
                > settings.ollama_context_length // 2
            ):
                record = {
                    "status": "unavailable",
                    "url": record["url"],
                    "error": "complete_source_exceeds_context",
                }
            sources.setdefault(post.id, []).append(record)
            if record["status"] == "fetched":
                primary_loaded = True
    output_path.write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding="utf-8")
    return sources


if __name__ == "__main__":
    with httpx.Client(trust_env=False) as client:
        print(json.dumps(fetch_article(sys.argv[1], client=client), ensure_ascii=False))
