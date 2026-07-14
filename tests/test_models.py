from __future__ import annotations

import pytest

from article_audio.models import ArticleJob


def _base_payload(**overrides) -> dict:
    payload = {
        "job_id": "00000000-0000-0000-0000-000000000001",
        "url": "https://example.com/article",
        "submitted_at": "2026-07-13T12:00:00Z",
        "voice": "tiernan",
    }
    payload.update(overrides)
    return payload


class TestArticleJobUrlMode:
    def test_url_mode_basic(self):
        job = ArticleJob.from_payload(_base_payload())
        assert job.url == "https://example.com/article"
        assert job.text is None
        assert job.title is None

    def test_empty_url_rejected(self):
        with pytest.raises(ValueError, match="url or text is required"):
            ArticleJob.from_payload(_base_payload(url=""))

    def test_invalid_url_rejected(self):
        with pytest.raises(ValueError, match="url must be an absolute"):
            ArticleJob.from_payload(_base_payload(url="not-a-url"))

    def test_both_url_and_text_rejected(self):
        with pytest.raises(ValueError, match="not both"):
            ArticleJob.from_payload(
                _base_payload(url="https://example.com", text="some text", title="T")
            )


class TestArticleJobTextMode:
    def test_text_mode_basic(self):
        job = ArticleJob.from_payload(
            _base_payload(url=None, text="Article body", title="My Title")
        )
        assert job.url is None
        assert job.text == "Article body"
        assert job.title == "My Title"

    def test_text_without_title_rejected(self):
        with pytest.raises(ValueError, match="title is required"):
            ArticleJob.from_payload(_base_payload(url=None, text="body"))

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError, match="url or text is required"):
            ArticleJob.from_payload(_base_payload(url=None, text="", title="T"))

    def test_whitespace_text_treated_as_empty(self):
        with pytest.raises(ValueError, match="url or text is required"):
            ArticleJob.from_payload(_base_payload(url=None, text="   ", title="T"))

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError, match="title is required"):
            ArticleJob.from_payload(_base_payload(url=None, text="body", title="  "))


class TestArticleJobInputDocument:
    def test_url_mode_includes_none_for_text_fields(self):
        job = ArticleJob.from_payload(_base_payload())
        doc = job.input_document()
        assert doc["url"] == "https://example.com/article"
        assert doc["text"] is None
        assert doc["title"] is None

    def test_text_mode_includes_none_for_url(self):
        job = ArticleJob.from_payload(_base_payload(url=None, text="body", title="T"))
        doc = job.input_document()
        assert doc["url"] is None
        assert doc["text"] == "body"
        assert doc["title"] == "T"
