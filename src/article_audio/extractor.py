from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

import requests
import trafilatura


@dataclasses.dataclass(frozen=True)
class Article:
    url: str
    title: str | None = None
    text: str | None = None
    author: str | None = None
    date: str | None = None

    @property
    def description(self) -> str:
        return f"Article from {self.url}"


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


def fetch_article(url: str, timeout: int = 30) -> Article:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    html = resp.text

    title = _extract_title_from_html(html)

    text = trafilatura.extract(
        html,
        include_formatting=False,
        include_images=False,
        include_links=False,
        output_format="txt",
    )

    if not text:
        text = trafilatura.extract(
            resp.content,
            include_formatting=False,
            include_images=False,
            include_links=False,
            output_format="txt",
        )

    if not title and text:
        first_line = text.split("\n")[0].strip()
        if first_line:
            title = first_line

    return Article(url=url, title=title, text=text)
