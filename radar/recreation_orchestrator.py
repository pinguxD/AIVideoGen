from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .analysis_review import load_review_bundle
from .full_video_analyzer import BASE
from .recreation_feasibility import assess
from .roblox_lua_generator import generate_lua
from .roblox_scene_spec import build_scene_spec
from .scene_decomposer import decompose_video

OUT = BASE / "outputs" / "recreation_intelligence"
AUDIO_AUTOPILOT_DIR = BASE / "outputs" / "audio_autopilot"

COMPONENT_WEIGHTS = {
    "environment_and_scene": 0.18,
    "avatar_and_character": 0.13,
    "camera": 0.10,
    "gameplay_mechanic": 0.22,
    "ui_and_overlays": 0.10,
    "editing_and_transitions": 0.10,
    "sound_design": 0.10,
    "voiceover": 0.07,
}


def _safe_name(value: str | Path) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in Path(str(value)).stem
    ).strip("_") or "reference"


def load_plan(source_name: str | None) -> dict[str, Any]:
    if not source_name:
        return {}

    bundle = load_review_bundle(source_name)
    corrected = (
        BASE
        / "outputs"
        / "corrected_reference_analysis"
        / f"{bundle['source_key']}.corrected.plan.json"
    )

    if corrected.exists():
        try:
            return json.loads(corrected.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    return bundle.get("plan") or {}


def load_audio_autopilot(source_name: str | None) -> dict[str, Any]:
    if not source_name:
        return {}

    safe = _safe_name(source_name)
    exact = AUDIO_AUTOPILOT_DIR / f"{safe}.audio_autopilot.json"

    candidates = [exact]
    if AUDIO_AUTOPILOT_DIR.exists():
        candidates.extend(
            sorted(
                AUDIO_AUTOPILOT_DIR.glob(
                    f"{safe}*.audio_autopilot.json"
                ),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )

    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_manifest_path"] = str(path)
            return data
        except (OSError, json.JSONDecodeError):
            continue

    return {}


def _append_evidence(component: Any, message: str) -> None:
    evidence = list(getattr(component, "evidence", []) or [])
    if message not in evidence:
        evidence.append(message)
    component.evidence = evidence


def _remove_audio_requirements(items: list[str]) -> list[str]:
    audio_terms = (
        "sound",
        "voice",
        "tts",
        "narration",
        "audio",
    )
    return [
        item
        for item in items
        if not any(term in str(item).lower() for term in audio_terms)
    ]


def _recalculate_feasibility(feasibility: Any) -> None:
    components = list(feasibility.components or [])

    total_weight = 0.0
    weighted_score = 0.0

    for component in components:
        weight = COMPONENT_WEIGHTS.get(component.component, 0.0)
        total_weight += weight
        weighted_score += float(component.score) * weight

    if total_weight > 0:
        feasibility.overall_score = int(
            round(weighted_score / total_weight)
        )

    scores = [int(component.score) for component in components]
    lowest_score = min(scores) if scores else 0
    missing = list(feasibility.exact_inputs_needed or [])

    if (
        feasibility.overall_score >= 82
        and lowest_score >= 60
        and not missing
    ):
        feasibility.verdict = "SELF_GENERATE"
        feasibility.recommended_engine = "roblox_studio_procedural"
        feasibility.prerecorded_footage_required = False
        feasibility.safe_to_generate_scene_spec = True
    elif feasibility.overall_score >= 68 and lowest_score >= 42:
        feasibility.verdict = "SELF_GENERATE_WITH_ASSETS"
        feasibility.recommended_engine = "roblox_studio_hybrid"
        feasibility.prerecorded_footage_required = any(
            "footage" in str(item).lower() for item in missing
        )
        feasibility.safe_to_generate_scene_spec = True
    elif feasibility.overall_score >= 52:
        feasibility.verdict = "NEEDS_USER_INPUT"
        feasibility.recommended_engine = "hybrid_existing_assets"
        feasibility.prerecorded_footage_required = any(
            "footage" in str(item).lower() for item in missing
        )
        feasibility.safe_to_generate_scene_spec = False
    else:
        feasibility.verdict = "CANNOT_RECREATE_RELIABLY"
        feasibility.recommended_engine = "manual_or_permitted_footage"
        feasibility.prerecorded_footage_required = True
        feasibility.safe_to_generate_scene_spec = False


def apply_audio_autopilot(
    feasibility: Any,
    audio_autopilot: dict[str, Any],
) -> None:
    if not audio_autopilot:
        return

    voiceover_file = str(
        audio_autopilot.get("voiceover_file") or ""
    ).strip()
    generated_sounds = list(
        audio_autopilot.get("generated_sound_effects") or []
    )
    audio_missing = list(audio_autopilot.get("missing") or [])

    voice_ready = bool(voiceover_file)
    sound_ready = bool(generated_sounds)

    for component in feasibility.components:
        if component.component == "voiceover" and voice_ready:
            component.score = 100
            component.method = "elevenlabs_autopilot"
            component.missing = []
            _append_evidence(
                component,
                f"Voice-over generated: {voiceover_file}",
            )

        if component.component == "sound_design" and sound_ready:
            component.score = 100
            component.method = "elevenlabs_sound_generation"
            component.missing = []
            _append_evidence(
                component,
                f"{len(generated_sounds)} sound effects generated.",
            )

    # Only clear previous audio requirements when Autopilot itself reports
    # no remaining audio problem.
    if not audio_missing:
        feasibility.exact_inputs_needed = _remove_audio_requirements(
            list(feasibility.exact_inputs_needed or [])
        )
    else:
        non_audio = _remove_audio_requirements(
            list(feasibility.exact_inputs_needed or [])
        )
        feasibility.exact_inputs_needed = list(
            dict.fromkeys([*non_audio, *audio_missing])
        )

    _recalculate_feasibility(feasibility)

    try:
        feasibility.save()
    except Exception:
        # The final recreation bundle still stores the updated status.
        pass


def run(
    source_file: str | Path,
    source_name: str | None = None,
    sample_interval: float = 0.2,
) -> dict[str, Any]:
    decomposition = decompose_video(
        source_file,
        sample_interval,
    )
    plan = load_plan(source_name)
    feasibility = assess(decomposition, plan)

    audio_autopilot = load_audio_autopilot(source_name)
    apply_audio_autopilot(feasibility, audio_autopilot)

    scene_spec = None
    lua_path = None
    manifest_path = None

    # Generate the scene only after completed audio stages have updated the
    # feasibility verdict and remaining requirements.
    if feasibility.safe_to_generate_scene_spec:
        scene_spec = build_scene_spec(
            decomposition,
            feasibility,
            plan,
        )
        lua_path, manifest_path = generate_lua(
            asdict(scene_spec)
        )

    result = {
        "decomposition": asdict(decomposition),
        "feasibility": asdict(feasibility),
        "scene_spec": (
            asdict(scene_spec)
            if scene_spec is not None
            else None
        ),
        "audio_autopilot": audio_autopilot,
        "lua_path": str(lua_path) if lua_path else "",
        "manifest_path": (
            str(manifest_path)
            if manifest_path
            else ""
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(source_file)
    output_path = OUT / f"{safe}.recreation_bundle.json"
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    result["summary_path"] = str(output_path)

    return result