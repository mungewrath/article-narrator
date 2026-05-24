from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


@dataclass(frozen=True)
class PodcastConfig:
    api_base_url: str
    token: str
    library_id: str
    podcast_dir: Path
    podcast_name: str
    podcast_author: str = "Article Audio Pipeline"

    @classmethod
    def from_env(cls) -> "PodcastConfig":
        return cls(
            api_base_url=os.getenv("ABS_API_URL", "http://audiobookshelf:80"),
            token=os.getenv("ABS_TOKEN", "").strip(),
            library_id=os.getenv("ABS_LIBRARY_ID", "").strip(),
            podcast_dir=Path(os.getenv("ABS_PODCAST_DIR", "/podcasts")).resolve(),
            podcast_name=os.getenv("ABS_PODCAST_NAME", "articles"),
            podcast_author=os.getenv("ABS_PODCAST_AUTHOR", "Article Audio Pipeline"),
        )


def _headers(cfg: PodcastConfig) -> dict[str, str]:
    return {"Authorization": f"Bearer {cfg.token}"}


def _slugify(text: str, max_len: int = 120) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in text.lower())
    return safe.strip("-").strip(".")[:max_len]


def _podcast_path(cfg: PodcastConfig) -> Path:
    return cfg.podcast_dir / cfg.podcast_name


def _ensure_metadata_json(cfg: PodcastConfig, description: str = "") -> None:
    path = _podcast_path(cfg) / "metadata.json"
    if path.exists():
        return

    metadata = {
        "title": cfg.podcast_name,
        "author": cfg.podcast_author,
        "description": description or f"Auto-generated {cfg.podcast_name} podcast",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2) + "\n")


@dataclass
class EpisodeResult:
    audio_path: str
    episode_title: str
    episode_id: str | None = None


def place_episode(
    audio_source: Path,
    title: str,
    description: str = "",
    pub_date: str | None = None,
    cfg: PodcastConfig | None = None,
) -> EpisodeResult:
    if cfg is None:
        cfg = PodcastConfig.from_env()

    podcast_path = _podcast_path(cfg)
    podcast_path.mkdir(parents=True, exist_ok=True)

    _ensure_metadata_json(cfg, description=description)

    slug = _slugify(title)
    ext = audio_source.suffix.lower()
    dest = podcast_path / f"{slug}{ext}"

    if dest.exists():
        stem = dest.stem
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        dest = podcast_path / f"{stem}-{ts}{ext}"

    shutil.copy2(audio_source, dest)

    scan_library(cfg)

    return EpisodeResult(audio_path=str(dest), episode_title=title)


def scan_library(cfg: PodcastConfig | None = None) -> str:
    if cfg is None:
        cfg = PodcastConfig.from_env()

    url = f"{cfg.api_base_url}/api/libraries/{cfg.library_id}/scan"
    resp = requests.post(url, headers=_headers(cfg), timeout=30)
    resp.raise_for_status()
    return resp.text


def get_podcast_item(cfg: PodcastConfig) -> dict[str, Any] | None:
    url = f"{cfg.api_base_url}/api/libraries/{cfg.library_id}/items"
    resp = requests.get(url, headers=_headers(cfg), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    for item in data.get("results", []):
        if item.get("relPath") == cfg.podcast_name:
            return item
    return None


def update_episode_metadata(
    item_id: str,
    episode_id: str,
    title: str,
    description: str = "",
    pub_date: str | None = None,
    cfg: PodcastConfig | None = None,
) -> dict[str, Any]:
    if cfg is None:
        cfg = PodcastConfig.from_env()

    url = f"{cfg.api_base_url}/api/items/{item_id}"
    body: dict[str, Any] = {
        "episodeId": episode_id,
        "metadata": {"title": title, "description": description},
    }
    if pub_date:
        body["metadata"]["pubDate"] = pub_date

    resp = requests.patch(url, json=body, headers=_headers(cfg), timeout=30)
    resp.raise_for_status()
    return resp.json()
