from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

OUTPUT_DIR = BASE / "outputs" / "generated_voiceovers"


@dataclass
class TTSResult:
    provider: str
    voice_id: str
    model_id: str
    audio_file: str
    text_file: str
    character_count: int


def _safe_name(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_"
        else "_"
        for character in value
    ).strip("_") or "voiceover"


def generate_elevenlabs_tts(
    text: str,
    output_name: str,
    voice_id: str | None = None,
    model_id: str | None = None,
    stability: float = 0.42,
    similarity_boost: float = 0.78,
    style: float = 0.22,
    use_speaker_boost: bool = True,
) -> TTSResult:
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("Narration text is empty.")

    api_key = str(os.getenv("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is missing from .env/environment."
        )

    resolved_voice_id = str(
        voice_id
        or os.getenv("ELEVENLABS_VOICE_ID")
        or ""
    ).strip()
    if not resolved_voice_id:
        raise RuntimeError(
            "No ElevenLabs voice selected. Set ELEVENLABS_VOICE_ID or enter one "
            "on the Audio Production page."
        )

    resolved_model_id = str(
        model_id
        or os.getenv("ELEVENLABS_MODEL_ID")
        or "eleven_multilingual_v2"
    ).strip()

    safe_name = _safe_name(output_name)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = OUTPUT_DIR / f"{safe_name}.mp3"
    text_path = OUTPUT_DIR / f"{safe_name}.txt"

    endpoint = (
        "https://api.elevenlabs.io/v1/text-to-speech/"
        f"{resolved_voice_id}?output_format=mp3_44100_128"
    )
    payload = {
        "text": clean_text,
        "model_id": resolved_model_id,
        "voice_settings": {
            "stability": max(0.0, min(1.0, float(stability))),
            "similarity_boost": max(
                0.0,
                min(1.0, float(similarity_boost)),
            ),
            "style": max(0.0, min(1.0, float(style))),
            "use_speaker_boost": bool(use_speaker_boost),
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            audio_bytes = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ElevenLabs TTS failed ({exc.code}): {details}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach ElevenLabs: {exc}"
        ) from exc

    if not audio_bytes:
        raise RuntimeError("ElevenLabs returned an empty audio file.")

    audio_path.write_bytes(audio_bytes)
    text_path.write_text(clean_text, encoding="utf-8")

    return TTSResult(
        provider="elevenlabs",
        voice_id=resolved_voice_id,
        model_id=resolved_model_id,
        audio_file=str(audio_path.relative_to(BASE)).replace("\\", "/"),
        text_file=str(text_path.relative_to(BASE)).replace("\\", "/"),
        character_count=len(clean_text),
    )
