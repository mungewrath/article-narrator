from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

import requests
import trafilatura
from lxml import html as lxml_html


@dataclasses.dataclass(frozen=True)
class Article:
    url: str
    title: str | None = None
    text: str | None = None
    author: str | None = None
    date: str | None = None

    @property
    def description(self) -> str:
        parts = [f"Source: {self.url}"]
        if self.author:
            parts.append(f"Author: {self.author}")
        if self.date:
            parts.append(f"Date: {self.date}")
        return " | ".join(parts)


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _consolidate_split_content(html_str: str) -> str:
    """Some sites (e.g. Ars Technica) split articles across multiple
    post-content divs. Move all content into the first one so trafilatura
    sees the full article."""
    try:
        doc = lxml_html.fromstring(html_str)
        content_divs = doc.xpath('//div[contains(@class, "post-content")]')
        if len(content_divs) <= 1:
            return html_str
        first = content_divs[0]
        for div in content_divs[1:]:
            for child in list(div):
                first.append(child)
            div.getparent().remove(div)
        return lxml_html.tostring(doc, encoding="unicode")
    except Exception:
        return html_str


def _extract_title_from_html(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.+?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()
        title = re.sub(r"\s+", " ", title)
        for sep in (" | ", " — ", " – ", " - ", " «"):
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        return title if title else None
    return None


def _parse_trafilatura_json(result: str, html: str) -> dict[str, Any]:
    data = json.loads(result)
    title = data.get("title") or _extract_title_from_html(html)
    text = data.get("text") or ""
    author = data.get("author")
    date = data.get("date")

    return {"title": title, "text": text, "author": author, "date": date}


def _extract_with_trafilatura(
    content: str | bytes,
    html: str,
) -> dict[str, Any] | None:
    result = trafilatura.extract(
        content,
        include_formatting=False,
        include_images=False,
        include_links=False,
        output_format="json",
        with_metadata=True,
    )
    if result:
        return _parse_trafilatura_json(result, html)
    return None


def fetch_article(url: str, timeout: int = 30) -> Article:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
    resp.raise_for_status()
    html = _consolidate_split_content(resp.text)

    extracted = _extract_with_trafilatura(html, html)

    if not extracted:
        extracted = _extract_with_trafilatura(resp.content, html)

    if extracted:
        title = extracted["title"]
        text = extracted["text"]
        author = extracted["author"]
        date = extracted["date"]
    else:
        title = _extract_title_from_html(html)
        text = ""
        author = None
        date = None

    if not title and text:
        first_line = text.split("\n")[0].strip()
        if first_line:
            title = first_line

    return Article(url=url, title=title, text=text, author=author, date=date)
