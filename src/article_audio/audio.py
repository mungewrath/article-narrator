from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import ormsgpack
import requests


def _fish_tts_url() -> str:
    return os.getenv("FISH_TTS_URL", "http://host.docker.internal:8888/v1/tts")


def _fish_request_headers() -> dict[str, str]:
    headers = {"content-type": "application/msgpack"}
    api_key = os.getenv("FISH_TTS_API_KEY", "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    return headers


def _fish_request_payload(text: str) -> bytes:
    payload: dict[str, Any] = {
        "text": text,
        "references": [],
        "reference_id": None,
        "format": "wav",
        "latency": "normal",
        "max_new_tokens": int(os.getenv("FISH_TTS_MAX_NEW_TOKENS", "4096")),
        "chunk_length": 200,
        "top_p": 0.8,
        "repetition_penalty": 1.1,
        "temperature": 0.8,
        "streaming": False,
        "use_memory_cache": "off",
        "seed": None,
    }
    return ormsgpack.packb(payload)


def _chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    # Split on double newlines first; fall back to single newlines; then sentences
    raw_paras = text.split("\n\n")
    if len(raw_paras) == 1:
        raw_paras = text.split("\n")
    if len(raw_paras) == 1:
        import re

        raw_paras = re.split(r"(?<=[.!?])\s+", text)

    paragraphs = [p.strip() for p in raw_paras if p.strip()]
    if not paragraphs:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def _generate_chunk_wav(text: str, timeout: int = 300) -> bytes:
    resp = requests.post(
        _fish_tts_url(),
        params={"format": "msgpack"},
        data=_fish_request_payload(text),
        headers=_fish_request_headers(),
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.content


def _merge_to_mp3(wav_chunks: list[bytes], output_path: Path) -> None:
    if len(wav_chunks) == 1:
        _wav_to_mp3(wav_chunks[0], output_path)
        return

    tmp_files: list[Path] = []
    try:
        for i, wav_data in enumerate(wav_chunks):
            tmp = Path(tempfile.mktemp(suffix=".wav"))
            tmp.write_bytes(wav_data)
            tmp_files.append(tmp)

        concat_file = Path(tempfile.mktemp(suffix=".txt"))
        concat_file.write_text("\n".join(f"file '{f}'" for f in tmp_files))

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-acodec",
                "libmp3lame",
                "-b:a",
                "128k",
                str(output_path),
            ],
            capture_output=True,
            check=True,
            timeout=600,
        )
        concat_file.unlink()
    finally:
        for f in tmp_files:
            f.unlink(missing_ok=True)


def _wav_to_mp3(wav_data: bytes, output_path: Path) -> None:
    tmp_wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        tmp_wav.write_bytes(wav_data)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(tmp_wav),
                "-acodec",
                "libmp3lame",
                "-b:a",
                "128k",
                str(output_path),
            ],
            capture_output=True,
            check=True,
            timeout=300,
        )
    finally:
        tmp_wav.unlink(missing_ok=True)


def synthesize_text(text: str, output_path: Path, timeout: int = 300) -> Path:
    chunks = _chunk_text(text)

    wav_chunks: list[bytes] = []
    for i, chunk in enumerate(chunks):
        print(f"Synthesizing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)...")
        wav = _generate_chunk_wav(chunk, timeout=timeout)
        wav_chunks.append(wav)

    if output_path.suffix.lower() == ".wav":
        if len(wav_chunks) == 1:
            output_path.write_bytes(wav_chunks[0])
        else:
            _merge_wav(wav_chunks, output_path)
    else:
        _merge_to_mp3(wav_chunks, output_path)

    return output_path


def _merge_wav(wav_chunks: list[bytes], output_path: Path) -> None:
    tmp_files: list[Path] = []
    try:
        for wav_data in wav_chunks:
            tmp = Path(tempfile.mktemp(suffix=".wav"))
            tmp.write_bytes(wav_data)
            tmp_files.append(tmp)

        concat_file = Path(tempfile.mktemp(suffix=".txt"))
        concat_file.write_text("\n".join(f"file '{f}'" for f in tmp_files))

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                str(output_path),
            ],
            capture_output=True,
            check=True,
            timeout=600,
        )
        concat_file.unlink()
    finally:
        for f in tmp_files:
            f.unlink(missing_ok=True)
