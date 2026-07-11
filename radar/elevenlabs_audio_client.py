from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

VOICE_DIR = BASE / "outputs" / "generated_voiceovers"
SFX_DIR = BASE / "outputs" / "generated_sound_effects"
from dotenv import load_dotenv

load_dotenv()

@dataclass
class VoiceChoice:
    voice_id: str
    name: str
    category: str
    labels: dict[str, str]
    score: int
    reasons: list[str]


def _api_key() -> str:
    key = str(os.getenv("ELEVENLABS_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is missing.")
    return key


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "xi-api-key": _api_key(),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ElevenLabs request failed ({exc.code}): {details}"
        ) from exc


def list_voices(page_size: int = 100) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "page_size": max(1, min(100, int(page_size))),
            "include_total_count": "false",
        }
    )
    data = _request_json(
        f"https://api.elevenlabs.io/v2/voices?{query}"
    )
    return list(data.get("voices") or [])


def choose_voice(
    profile: dict[str, Any],
    preferred_voice_id: str | None = None,
) -> VoiceChoice:
    preferred = str(preferred_voice_id or "").strip()
    voices = list_voices()

    if preferred:
        for voice in voices:
            if str(voice.get("voice_id") or "") == preferred:
                return VoiceChoice(
                    voice_id=preferred,
                    name=str(voice.get("name") or preferred),
                    category=str(voice.get("category") or ""),
                    labels=dict(voice.get("labels") or {}),
                    score=100,
                    reasons=["configured preferred voice"],
                )

    target_terms = {
        str(profile.get("delivery") or "").lower(),
        str(profile.get("pacing") or "").lower(),
        str(profile.get("pitch_band") or "").lower(),
        str(profile.get("energy") or "").lower(),
    }
    target_terms.discard("")
    target_terms.discard("unknown")

    ranked: list[VoiceChoice] = []

    for voice in voices:
        labels = {
            str(key).lower(): str(value).lower()
            for key, value in dict(voice.get("labels") or {}).items()
        }
        searchable = " ".join(
            [
                str(voice.get("name") or ""),
                str(voice.get("description") or ""),
                str(voice.get("category") or ""),
                *labels.keys(),
                *labels.values(),
            ]
        ).lower()

        matches = [term for term in target_terms if term in searchable]
        score = 45 + len(matches) * 12

        category = str(voice.get("category") or "").lower()
        if category in {"premade", "generated", "professional"}:
            score += 6

        ranked.append(
            VoiceChoice(
                voice_id=str(voice.get("voice_id") or ""),
                name=str(voice.get("name") or "Unnamed voice"),
                category=str(voice.get("category") or ""),
                labels=dict(voice.get("labels") or {}),
                score=min(99, score),
                reasons=(
                    [f"matched {term}" for term in matches]
                    or ["best available general narration voice"]
                ),
            )
        )

    if not ranked:
        fallback = str(os.getenv("ELEVENLABS_VOICE_ID") or "").strip()
        if not fallback:
            raise RuntimeError(
                "No ElevenLabs voices were returned and no fallback voice is set."
            )
        return VoiceChoice(
            voice_id=fallback,
            name="Configured fallback",
            category="configured",
            labels={},
            score=60,
            reasons=["fallback environment voice"],
        )

    return max(ranked, key=lambda item: item.score)


def generate_tts(
    text: str,
    output_name: str,
    voice_choice: VoiceChoice,
    profile: dict[str, Any],
    model_id: str = "eleven_multilingual_v2",
) -> Path:
    clean_text = str(text or "").strip()
    if not clean_text:
        raise ValueError("Narration text is empty.")

    safe = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in output_name
    ).strip("_") or "voiceover"

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    output = VOICE_DIR / f"{safe}.mp3"

    payload = {
        "text": clean_text,
        "model_id": model_id,
        "voice_settings": {
            "stability": float(profile.get("tts_stability") or 0.45),
            "similarity_boost": float(
                profile.get("tts_similarity_boost") or 0.78
            ),
            "style": float(profile.get("tts_style") or 0.25),
            "use_speaker_boost": True,
        },
    }
    request = urllib.request.Request(
        (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{voice_choice.voice_id}?output_format=mp3_44100_128"
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            output.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ElevenLabs TTS failed ({exc.code}): {details}"
        ) from exc

    return output


def generate_sound_effect(
    prompt: str,
    output_name: str,
    duration_seconds: float | None = None,
    prompt_influence: float = 0.55,
) -> Path:
    clean_prompt = str(prompt or "").strip()
    if not clean_prompt:
        raise ValueError("Sound-effect prompt is empty.")

    safe = "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in output_name
    ).strip("_") or "sound_effect"

    SFX_DIR.mkdir(parents=True, exist_ok=True)
    output = SFX_DIR / f"{safe}.mp3"

    payload: dict[str, Any] = {
        "text": clean_prompt,
        "loop": False,
        "prompt_influence": max(
            0.0,
            min(1.0, float(prompt_influence)),
        ),
        "model_id": "eleven_text_to_sound_v2",
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = max(
            0.5,
            min(30.0, float(duration_seconds)),
        )

    request = urllib.request.Request(
        (
            "https://api.elevenlabs.io/v1/sound-generation"
            "?output_format=mp3_44100_128"
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            output.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"ElevenLabs sound generation failed ({exc.code}): {details}"
        ) from exc

    return output
