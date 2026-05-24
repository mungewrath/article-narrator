from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ormsgpack
import requests
from prefect import flow, get_run_logger, task

from article_audio.extractor import Article, fetch_article
from article_audio.podcast import EpisodeResult, PodcastConfig, place_episode


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _fish_tts_url() -> str:
    return os.getenv("FISH_TTS_URL", "http://host.docker.internal:8888/v1/tts")


def _fish_health_url() -> str:
    return _fish_tts_url().removesuffix("/v1/tts") + "/v1/health"


def _fish_output_dir() -> Path:
    return Path(os.getenv("FISH_TTS_OUTPUT_DIR", "/data/jobs/prefect-demo")).resolve()


def _fish_request_headers() -> dict[str, str]:
    headers = {
        "content-type": "application/msgpack",
    }
    api_key = os.getenv("FISH_TTS_API_KEY", "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    return headers


def _max_new_tokens() -> int:
    return int(os.getenv("FISH_TTS_MAX_NEW_TOKENS", "4096"))


def _fish_request_payload(text: str, audio_format: str) -> bytes:
    payload: dict[str, Any] = {
        "text": text,
        "references": [],
        "reference_id": None,
        "format": audio_format,
        "latency": "normal",
        "max_new_tokens": _max_new_tokens(),
        "chunk_length": 200,
        "top_p": 0.8,
        "repetition_penalty": 1.1,
        "temperature": 0.8,
        "streaming": False,
        "use_memory_cache": "off",
        "seed": None,
    }
    return ormsgpack.packb(payload)


@task
def check_fish_tts_health() -> str:
    health_url = _fish_health_url()
    response = requests.get(health_url, timeout=10)
    response.raise_for_status()
    return response.text


@task
def synthesize_audio(text: str, title: str, audio_format: str = "mp3") -> str:
    output_dir = _fish_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in title.lower()).strip(
        "-"
    )[:80]
    output_path = output_dir / f"{slug}-{_utc_timestamp()}.{audio_format}"
    response = requests.post(
        _fish_tts_url(),
        params={"format": "msgpack"},
        data=_fish_request_payload(text, audio_format),
        headers=_fish_request_headers(),
        timeout=600,
    )
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return str(output_path)


@task
def synthesize_hello_world(text: str, audio_format: str = "mp3") -> str:
    output_dir = _fish_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"hello-world-{_utc_timestamp()}.{audio_format}"
    response = requests.post(
        _fish_tts_url(),
        params={"format": "msgpack"},
        data=_fish_request_payload(text, audio_format),
        headers=_fish_request_headers(),
        timeout=600,
    )
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return str(output_path)


@flow(name="hello-world-tts", log_prints=True)
def hello_world_tts(text: str = "Hello from Prefect and Fish Speech") -> dict[str, str]:
    logger = get_run_logger()
    logger.info("Checking fish TTS server at %s", _fish_health_url())
    health = check_fish_tts_health()
    logger.info("Fish TTS health response: %s", health)
    output_path = synthesize_hello_world(text)
    logger.info("Wrote synthesized audio to %s", output_path)
    return {
        "health": health,
        "output_path": output_path,
        "text": text,
    }


@flow(name="article-to-podcast", log_prints=True)
def article_to_podcast(
    text: str,
    title: str = "Untitled Article",
    description: str = "",
) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info("Starting article-to-podcast for: %s", title)

    health = check_fish_tts_health()
    logger.info("Fish TTS health: %s", health)

    audio_path = synthesize_audio(text, title)
    logger.info("Synthesized audio: %s", audio_path)

    result = place_episode(
        audio_source=Path(audio_path),
        title=title,
        description=description,
    )
    logger.info(
        "Placed episode in podcast: %s (title=%s)",
        result.audio_path,
        result.episode_title,
    )

    return {
        "status": "ok",
        "audio_path": audio_path,
        "episode_path": result.audio_path,
        "episode_title": result.episode_title,
        "podcast": os.getenv("ABS_PODCAST_NAME", "articles"),
    }


@task
def extract_article(url: str) -> Article:
    return fetch_article(url)


@flow(name="url-to-podcast", log_prints=True)
def url_to_podcast(url: str) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info("Fetching article from: %s", url)

    article = extract_article(url)
    logger.info("Extracted: %s (%d chars)", article.title, len(article.text or ""))

    return article_to_podcast(
        text=article.text or "",
        title=article.title or "Untitled Article",
        description=article.description,
    )


def deploy_hello_world_tts() -> None:
    hello_world_tts.from_source(
        source=str(Path("/app")),
        entrypoint="src/article_audio/prefect_flows.py:hello_world_tts",
    ).deploy(
        name="hello-world-tts",
        work_pool_name=os.getenv("PREFECT_WORK_POOL_NAME", "article-audio"),
        build=False,
        push=False,
    )


def deploy_article_to_podcast() -> None:
    article_to_podcast.from_source(
        source=str(Path("/app")),
        entrypoint="src/article_audio/prefect_flows.py:article_to_podcast",
    ).deploy(
        name="article-to-podcast",
        work_pool_name=os.getenv("PREFECT_WORK_POOL_NAME", "article-audio"),
        build=False,
        push=False,
    )


def deploy_url_to_podcast() -> None:
    url_to_podcast.from_source(
        source=str(Path("/app")),
        entrypoint="src/article_audio/prefect_flows.py:url_to_podcast",
    ).deploy(
        name="url-to-podcast",
        work_pool_name=os.getenv("PREFECT_WORK_POOL_NAME", "article-audio"),
        build=False,
        push=False,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prefect flow helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser("deploy-hello")
    deploy_parser.set_defaults(handler=lambda _args: deploy_hello_world_tts())

    deploy_article_parser = subparsers.add_parser("deploy-article")
    deploy_article_parser.set_defaults(
        handler=lambda _args: deploy_article_to_podcast()
    )

    deploy_url_parser = subparsers.add_parser("deploy-url")
    deploy_url_parser.set_defaults(handler=lambda _args: deploy_url_to_podcast())

    run_parser = subparsers.add_parser("run-hello")
    run_parser.add_argument(
        "--text",
        default=os.getenv("PREFECT_HELLO_TEXT", "Hello from Prefect and Fish Speech"),
    )
    run_parser.set_defaults(handler=lambda args: hello_world_tts(text=args.text))

    run_article_parser = subparsers.add_parser("run-article")
    run_article_parser.add_argument("--text", required=True)
    run_article_parser.add_argument("--title", default="Untitled Article")
    run_article_parser.add_argument("--description", default="")
    run_article_parser.set_defaults(
        handler=lambda args: article_to_podcast(
            text=args.text, title=args.title, description=args.description
        )
    )

    run_url_parser = subparsers.add_parser("run-url")
    run_url_parser.add_argument("--url", required=True)
    run_url_parser.set_defaults(handler=lambda args: url_to_podcast(url=args.url))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
