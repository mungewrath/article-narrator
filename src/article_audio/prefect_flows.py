from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ormsgpack
import requests
from prefect import flow, get_run_logger, task


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


def _fish_request_payload(text: str, audio_format: str) -> bytes:
    payload: dict[str, Any] = {
        "text": text,
        "references": [],
        "reference_id": None,
        "format": audio_format,
        "latency": "normal",
        "max_new_tokens": 1024,
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
def synthesize_hello_world(text: str, audio_format: str = "wav") -> str:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prefect flow helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser("deploy-hello")
    deploy_parser.set_defaults(handler=lambda _args: deploy_hello_world_tts())

    run_parser = subparsers.add_parser("run-hello")
    run_parser.add_argument(
        "--text",
        default=os.getenv("PREFECT_HELLO_TEXT", "Hello from Prefect and Fish Speech"),
    )
    run_parser.set_defaults(handler=lambda args: hello_world_tts(text=args.text))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
