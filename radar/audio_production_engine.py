from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .sfx_resolver import resolve_sound_events
from .tts_engine import generate_elevenlabs_tts

BUNDLE_DIR = BASE / "outputs" / "recreation_intelligence"
OUTPUT_DIR = BASE / "outputs" / "audio_production"


def _safe_name(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_"
        else "_"
        for character in Path(value).stem
    ).strip("_") or "reference"


def find_recreation_bundle(source_name: str) -> Path:
    safe = _safe_name(source_name)
    exact = BUNDLE_DIR / f"{safe}.recreation_bundle.json"
    if exact.exists():
        return exact

    candidates = list(BUNDLE_DIR.glob(f"{safe}*.recreation_bundle.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No recreation bundle found for {source_name}. "
            "Run Roblox Recreation Lab first."
        )
    return candidates[0]


def produce_audio_package(
    source_name: str,
    narration_text: str,
    voice_id: str | None = None,
    model_id: str | None = None,
    stability: float = 0.42,
    similarity_boost: float = 0.78,
    style: float = 0.22,
    find_sounds: bool = True,
) -> dict[str, Any]:
    bundle_path = find_recreation_bundle(source_name)
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

    decomposition = bundle.get("decomposition") or {}
    audio_layers = decomposition.get("audio_layers") or {}
    sound_events = decomposition.get("sound_effects") or []

    voiceover_result = None
    missing: list[str] = []

    voiceover_required = bool(
        audio_layers.get("probable_voiceover")
        or (
            bundle.get("scene_spec")
            and (bundle["scene_spec"].get("post_edit") or {}).get(
                "voiceover_required"
            )
        )
    )

    if voiceover_required:
        if not str(narration_text or "").strip():
            missing.append("narration script")
        else:
            voiceover_result = generate_elevenlabs_tts(
                text=narration_text,
                output_name=f"{_safe_name(source_name)}_voiceover",
                voice_id=voice_id,
                model_id=model_id,
                stability=stability,
                similarity_boost=similarity_boost,
                style=style,
            )

    resolved_sounds = []
    unresolved_sounds = []
    if find_sounds and sound_events:
        resolved_sounds, unresolved_sounds = resolve_sound_events(
            sound_events,
            source_name=source_name,
        )
        missing.extend(unresolved_sounds)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(source_name)
    package_path = OUTPUT_DIR / f"{safe}.audio_package.json"

    result = {
        "source_name": source_name,
        "source_bundle": str(
            bundle_path.relative_to(BASE)
        ).replace("\\", "/"),
        "voiceover_required": voiceover_required,
        "voiceover": (
            asdict(voiceover_result)
            if voiceover_result is not None
            else None
        ),
        "sound_effects": [
            asdict(item)
            for item in resolved_sounds
        ],
        "unresolved_sound_effects": unresolved_sounds,
        "missing": list(dict.fromkeys(missing)),
        "ready_for_audio_mix": (
            not missing
            and (
                not voiceover_required
                or voiceover_result is not None
            )
        ),
    }
    package_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result["package_path"] = str(
        package_path.relative_to(BASE)
    ).replace("\\", "/")
    return result
