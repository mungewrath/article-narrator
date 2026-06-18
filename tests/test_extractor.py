from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from article_audio.extractor import (
    Article,
    _consolidate_split_content,
    _extract_title_from_html,
    _parse_trafilatura_json,
    fetch_article,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(html: str, status: int = 200) -> MagicMock:
    """Build a requests.Response-like mock carrying the given HTML."""
    resp = MagicMock()
    resp.text = html
    resp.content = html.encode()
    resp.status_code = status
    resp.raise_for_status = lambda: None
    return resp


# ── Article dataclass ──────────────────────────────────────────────────


class TestArticle:
    def test_minimal(self):
        a = Article(url="http://example.com")
        assert a.url == "http://example.com"
        assert (
            a.title is None and a.text is None and a.author is None and a.date is None
        )

    def test_description_with_all_fields(self):
        a = Article(url="http://example.com", title="T", author="A", date="2024-01-01")
        assert "Author: A" in a.description and "Date: 2024-01-01" in a.description

    def test_description_source_only(self):
        assert (
            Article(url="http://example.com").description
            == "Source: http://example.com"
        )

    def test_frozen(self):
        a = Article(url="u", title="t")
        with pytest.raises(AttributeError):
            a.title = "x"  # type: ignore[misc]


# ── _extract_title_from_html ──────────────────────────────────────────


class TestExtractTitleFromHtml:
    def test_basic(self):
        assert _extract_title_from_html("<head><title>Hello</title></head>") == "Hello"

    def test_with_pipe_separator(self):
        assert (
            _extract_title_from_html("<title>My Article | Site</title>") == "My Article"
        )

    def test_with_em_dash(self):
        assert _extract_title_from_html("<title>Story \u2014 Site</title>") == "Story"

    def test_no_title_tag(self):
        assert _extract_title_from_html("<body><p>no title</p></body>") is None

    def test_whitespace_collapsed(self):
        assert (
            _extract_title_from_html("<title>  Lots   of   space  </title>")
            == "Lots of space"
        )

    def test_empty_title_tag(self):
        assert _extract_title_from_html("<title>   </title>") is None


# ── _parse_trafilatura_json ────────────────────────────────────────────


class TestParseTrafilaturaJson:
    def test_full(self):
        r = json.dumps({"title": "T", "text": "B", "author": "A", "date": "2025-01-01"})
        assert _parse_trafilatura_json(r, "<html></html>") == {
            "title": "T",
            "text": "B",
            "author": "A",
            "date": "2025-01-01",
        }

    def test_title_fallback_to_html(self):
        r = json.dumps({"title": None, "text": "", "author": None, "date": None})
        assert (
            _parse_trafilatura_json(r, "<head><title>HTML T</title></head>")["title"]
            == "HTML T"
        )

    def test_none_text_becomes_empty(self):
        r = json.dumps({"title": "T", "text": None, "author": None, "date": None})
        assert _parse_trafilatura_json(r, "<html></html>")["text"] == ""


# ── _consolidate_split_content ─────────────────────────────────────────


class TestConsolidateSplitContent:
    def test_no_post_content(self):
        html = "<html><body><p>Hello</p></body></html>"
        assert _consolidate_split_content(html) == html

    def test_single_post_content(self):
        html = '<html><body><div class="post-content"><p>Hello</p></div></body></html>'
        assert _consolidate_split_content(html) == html

    def test_merges_multiple_post_content_divs(self):
        html = (
            '<html><body><div class="wrapper">'
            '<div class="post-content"><p>A</p></div>'
            '<div class="post-content"><p>B</p></div>'
            '<div class="post-content"><p>C</p></div>'
            "</div></body></html>"
        )
        result = _consolidate_split_content(html)
        from lxml import html as lxml_html

        doc = lxml_html.fromstring(result)
        divs = doc.xpath('//div[contains(@class, "post-content")]')
        assert len(divs) == 1
        text = divs[0].text_content()
        assert "A" in text and "B" in text and "C" in text

    def test_invalid_html_returns_original(self):
        assert _consolidate_split_content("<<<not valid>>>") == "<<<not valid>>>"

    def test_matches_post_content_double_class(self):
        html = (
            "<html><body>"
            '<div class="post-content-double"><p>A</p></div>'
            '<div class="post-content-double"><p>B</p></div>'
            "</body></html>"
        )
        result = _consolidate_split_content(html)
        from lxml import html as lxml_html

        doc = lxml_html.fromstring(result)
        assert len(doc.xpath('//div[contains(@class, "post-content")]')) == 1

    def test_does_not_duplicate_content(self):
        html = (
            "<html><body>"
            '<div class="post-content"><p>Alpha</p></div>'
            '<div class="post-content"><p>Beta</p></div>'
            "</body></html>"
        )
        result = _consolidate_split_content(html)
        assert result.count("Alpha") == 1
        assert result.count("Beta") == 1


# ── Integration: fixture-based tests via mocked fetch_article ─────────


class TestArsTechnicaFixture:
    URL = (
        "https://arstechnica.com/gadgets/2026/06/"
        "20-years-of-intel-macs-why-apple-switched-and-why-it-switched-again/"
    )

    @pytest.fixture(autouse=True)
    def _mock_network(self):
        html = (FIXTURES / "arstechnica.html").read_text()
        with patch(
            "article_audio.extractor.requests.get", return_value=_mock_response(html)
        ):
            yield

    def test_article_via_public_api(self):
        article = fetch_article(self.URL)
        assert article.title and "Intel Macs" in article.title
        assert article.author == "Andrew Cunningham"
        assert article.date

    def test_text_is_substantial(self):
        article = fetch_article(self.URL)
        assert len(article.text or "") > 5000

    def test_consolidation_merged_later_sections(self):
        """Content from later post-content divs must be present."""
        article = fetch_article(self.URL)
        t = article.text or ""
        assert "Apple Silicon" in t
        assert "Rosetta" in t
        assert "Touch Bar" in t


class TestMempkoFixture:
    URL = "https://blog.mempko.com/the-open-closed-problem-in-ai/"

    @pytest.fixture(autouse=True)
    def _mock_network(self):
        html = (FIXTURES / "mempko.html").read_text()
        with patch(
            "article_audio.extractor.requests.get", return_value=_mock_response(html)
        ):
            yield

    def test_article_via_public_api(self):
        article = fetch_article(self.URL)
        assert article.title and "Open/Closed" in article.title
        assert article.author == "Maxim Khailo"
        assert article.date

    def test_text_is_substantial(self):
        article = fetch_article(self.URL)
        assert len(article.text or "") > 3000


# ── Integration: live URL tests (smoke, network-dependent) ────────────


@pytest.mark.network
class TestLiveUrls:
    @pytest.mark.slow
    def test_arstechnica_live(self):
        article = fetch_article(TestArsTechnicaFixture.URL, timeout=15)
        assert article.title and "Intel" in article.title
        assert len(article.text or "") > 5000
        assert "Andrew Cunningham" in (article.author or "")

    @pytest.mark.slow
    def test_mempko_live(self):
        article = fetch_article(TestMempkoFixture.URL, timeout=15)
        assert article.title and "Open/Closed" in article.title
        assert len(article.text or "") > 3000
        assert "Maxim" in (article.author or "")
