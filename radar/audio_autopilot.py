from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .analysis_review import load_review_bundle
from .elevenlabs_audio_client import (
    choose_voice,
    generate_sound_effect,
    generate_tts,
)
from .full_video_analyzer import BASE
from .voice_profiler import profile_voice

RECREATION_DIR = BASE / "outputs" / "recreation_intelligence"
OUTPUT_DIR = BASE / "outputs" / "audio_autopilot"

SFX_PROMPTS = {
    "click_or_ui_tick": "A crisp short video game UI click, clean and modern",
    "pop_or_snap": "A short playful cartoon pop with a sharp attack",
    "bass_hit_or_vine_boom": "A deep dramatic bass impact for a viral short reveal",
    "riser_or_build_up": "A short energetic cinematic riser building suspense",
    "whoosh_or_swipe": "A fast clean whoosh transition for a vertical short",
    "impact_or_explosion": "A short punchy impact with a controlled explosion texture",
    "scream_noise_or_glitch": "A very short funny panic scream blended with a digital glitch",
    "unknown_effect": "A short high-energy viral video transition sound effect",
}


def _safe_name(value: str) -> str:
    return "".join(
        c if c.isalnum() or c in "-_" else "_"
        for c in Path(value).stem
    ).strip("_") or "reference"


def _bundle_path(source_name: str) -> Path:
    safe = _safe_name(source_name)
    exact = RECREATION_DIR / f"{safe}.recreation_bundle.json"
    if exact.exists():
        return exact

    candidates = list(
        RECREATION_DIR.glob(f"{safe}*.recreation_bundle.json")
    )
    if not candidates:
        raise FileNotFoundError(
            f"No Recreation Lab bundle found for {source_name}."
        )
    return candidates[0]


def _resolve_source_file(source_name: str) -> Path:
    bundle = load_review_bundle(source_name)
    analysis = bundle.get("analysis") or {}
    source_value = str(analysis.get("source_file") or "")
    path = Path(source_value)
    if not path.is_absolute():
        path = BASE / path

    if path.exists():
        return path

    # After analysis, the file is normally moved to analyzed/.
    candidate = (
        BASE
        / "assets"
        / "reference_videos"
        / "analyzed"
        / Path(source_name).name
    )
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Could not locate the analyzed reference video: {source_name}"
    )


def run_audio_autopilot(
    source_name: str,
    narration_text: str,
    preferred_voice_id: str | None = None,
) -> dict[str, Any]:
    bundle_path = _bundle_path(source_name)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    source_file = _resolve_source_file(source_name)

    profile = profile_voice(source_file)
    voice_choice = choose_voice(
        profile.to_dict(),
        preferred_voice_id=preferred_voice_id,
    )

    tts_path = None
    missing: list[str] = []
    if profile.speech_present:
        if not str(narration_text or "").strip():
            missing.append("original narration script")
        else:
            tts_path = generate_tts(
                narration_text,
                f"{_safe_name(source_name)}_autopilot_voice",
                voice_choice,
                profile.to_dict(),
            )

    generated_effects = []
    events = (
        (bundle.get("decomposition") or {}).get("sound_effects")
        or []
    )

    for index, event in enumerate(events):
        family = str(
            event.get("family")
            or event.get("effect_type")
            or "unknown_effect"
        )
        prompt = SFX_PROMPTS.get(
            family,
            SFX_PROMPTS["unknown_effect"],
        )
        duration = max(
            0.5,
            min(
                3.0,
                float(event.get("end") or 0)
                - float(event.get("start") or 0),
            ),
        )
        output = generate_sound_effect(
            prompt=prompt,
            output_name=(
                f"{_safe_name(source_name)}"
                f"_sfx_{index + 1}_{family}"
            ),
            duration_seconds=duration,
            prompt_influence=0.62,
        )
        generated_effects.append(
            {
                "event_index": index,
                "start": float(event.get("start") or 0),
                "end": float(event.get("end") or 0),
                "family": family,
                "prompt": prompt,
                "audio_file": str(
                    output.relative_to(BASE)
                ).replace("\\", "/"),
            }
        )

    result = {
        "source_name": source_name,
        "source_file": str(source_file),
        "voice_profile": profile.to_dict(),
        "voice_choice": asdict(voice_choice),
        "voiceover_file": (
            str(tts_path.relative_to(BASE)).replace("\\", "/")
            if tts_path
            else ""
        ),
        "generated_sound_effects": generated_effects,
        "missing": missing,
        "ready_for_mix": not missing,
        "source_recreation_bundle": str(
            bundle_path.relative_to(BASE)
        ).replace("\\", "/"),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (
        OUTPUT_DIR / f"{_safe_name(source_name)}.audio_autopilot.json"
    )
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result["output_path"] = str(
        output_path.relative_to(BASE)
    ).replace("\\", "/")
    return result
