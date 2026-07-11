from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .analysis_review import load_review_bundle, write_corrected_bundle
from .clip_brain import choose_clips_for_project
from .creator_projects import BASE, CreatorProject
from .sound_library import ensure_unique_sounds, search_local_unique

CORRECTED_DIR = BASE / "outputs" / "corrected_reference_analysis"


def _safe_key(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(value).stem)
    return cleaned.strip("._-") or "reference_project"


def _load_corrected_plan(source_name: str) -> dict[str, Any]:
    source_key = _safe_key(source_name)
    corrected = CORRECTED_DIR / f"{source_key}.corrected.plan.json"

    if not corrected.exists():
        _, corrected = write_corrected_bundle(source_name)

    if not corrected.exists():
        raise FileNotFoundError(
            f"Corrected production plan was not created: {corrected}"
        )

    return json.loads(corrected.read_text(encoding="utf-8"))


def _creator_template(format_name: str) -> str:
    mapping = {
        "interactive_guess": "guess_voice",
        "sound_replacement": "sound_replacement",
        # The current renderer only has a basic fact-card renderer.
        # Narrated formats are therefore created as review projects, not falsely
        # marked ready for rendering.
        "narrated_fact_list": "fact_card",
        "narrated_story": "fact_card",
        "gameplay_caption": "fact_card",
        "meme_edit": "manual",
        "manual_complex_edit": "manual",
    }
    return mapping.get(format_name, "manual")


def _clip_requirements(format_name: str) -> tuple[int, str]:
    if format_name == "interactive_guess":
        return 1, "clear relevant character/gameplay shot with low UI"
    if format_name == "sound_replacement":
        return 1, "visual action matching the replacement sound"
    if format_name in {
        "narrated_fact_list",
        "narrated_story",
        "gameplay_caption",
    }:
        return 1, "continuous, clean, non-distracting gameplay"
    if format_name == "meme_edit":
        return 1, "background clip matching the meme context"
    return 1, "project-relevant source footage"


def _sound_queries(
    format_name: str,
    plan: dict[str, Any],
) -> tuple[list[str], int]:
    audio_plan = plan.get("audio_plan") or {}
    soundboard = audio_plan.get("soundboard")

    if format_name == "interactive_guess":
        return [
            "viral funny scream short",
            "goofy character voice short",
            "cartoon reaction sound short",
            "monster or creature voice short",
        ], 4

    if format_name == "sound_replacement":
        return ["funny meme sound matching action"], 1

    if format_name == "meme_edit" and soundboard:
        return ["short meme impact sound"], 1

    # Narrated facts/stories/caption videos must not receive random soundboards.
    return [], 0


def _project_text_lines(
    format_name: str,
    source_name: str,
    plan: dict[str, Any],
) -> list[str]:
    labels = plan.get("human_labels") or {}
    hook = str(labels.get("hook_type") or "").strip()

    if format_name == "interactive_guess":
        return [
            "GUESS THE REAL VOICE",
            "1",
            "2",
            "3",
            "4",
            "COMMENT BEFORE THE REVEAL",
        ]

    if format_name == "sound_replacement":
        return ["WAIT FOR THE SOUND", "COMMENT YOUR REACTION"]

    if format_name == "narrated_fact_list":
        return [
            hook.replace("_", " ").upper()
            if hook
            else "THESE FACTS COULD SAVE YOUR LIFE"
        ]

    if format_name == "narrated_story":
        return [
            hook.replace("_", " ").upper()
            if hook
            else "YOU WON'T BELIEVE WHAT HAPPENED"
        ]

    return [Path(source_name).stem]


def _missing_inputs(
    format_name: str,
    plan: dict[str, Any],
    source_files: list[str],
    sound_files: list[str],
    unresolved_sounds: list[str],
) -> list[str]:
    missing: list[str] = []

    if not source_files:
        missing.append("matching gameplay/source clip")

    if format_name == "narrated_fact_list":
        missing.extend(
            [
                "original verified fact/list script",
                "AI voice or human voice selection",
                "timed captions",
            ]
        )
        visual_plan = plan.get("visual_plan") or {}
        if visual_plan.get("visual_inserts"):
            missing.append("relevant images/meme inserts for each fact")

    elif format_name == "narrated_story":
        missing.extend(
            [
                "original story script",
                "AI voice or human voice selection",
                "timed narrative captions",
            ]
        )

    elif format_name == "gameplay_caption":
        missing.append("final caption/story text")

    elif format_name == "interactive_guess":
        if len(sound_files) < 4:
            missing.append(f"{4 - len(sound_files)} more approved unique sounds")

    elif format_name == "sound_replacement":
        if len(sound_files) < 1:
            missing.append("one approved replacement sound")

    elif format_name == "meme_edit":
        missing.append("approved meme template or reaction insert")
        if unresolved_sounds:
            missing.append("approved meme sound or confirmation that none is needed")

    elif format_name == "manual_complex_edit":
        missing.append("manual timeline approval")

    missing.extend(
        f"sound search unresolved: {query}"
        for query in unresolved_sounds
    )
    return list(dict.fromkeys(item for item in missing if item))


def create_project_from_analysis(
    source_name: str,
    fetch_sounds: bool = True,
) -> CreatorProject:
    bundle = load_review_bundle(source_name)
    plan = _load_corrected_plan(source_name)

    format_name = str(
        plan.get("detected_format")
        or bundle.get("plan", {}).get("detected_format")
        or "manual_complex_edit"
    )
    creator_template = _creator_template(format_name)

    labels = plan.get("human_labels") or {}
    title = Path(source_name).stem
    character_name = str(labels.get("character_name") or "")

    clip_count, clip_requirement = _clip_requirements(format_name)
    clips, clip_matches, clip_requirements, recording_task = (
        choose_clips_for_project(
            title=title,
            template_type=creator_template,
            character_name=character_name,
            count=clip_count,
        )
    )

    source_files = [
        str(path.relative_to(BASE)).replace("\\", "/")
        for path in clips
    ]

    queries, required_sound_count = _sound_queries(format_name, plan)
    if required_sound_count:
        if fetch_sounds:
            sound_assets, unresolved = ensure_unique_sounds(
                queries,
                required_total=required_sound_count,
            )
        else:
            sound_assets, unresolved = search_local_unique(
                queries,
                required_total=required_sound_count,
            )
    else:
        sound_assets, unresolved = [], []

    sound_files = [asset.file for asset in sound_assets]
    missing = _missing_inputs(
        format_name,
        plan,
        source_files,
        sound_files,
        unresolved,
    )

    supported_renderer = format_name in {
        "interactive_guess",
        "sound_replacement",
    }

    # Narrated formats deliberately remain review projects until the
    # voiceover/caption renderer exists.
    if supported_renderer and not missing:
        status = "AUTO_READY"
        confidence = min(99, int(plan.get("confidence") or 85))
    elif format_name == "manual_complex_edit":
        status = "MANUAL_ONLY"
        confidence = min(60, int(plan.get("confidence") or 40))
    else:
        status = "NEEDS_ASSETS"
        confidence = min(95, int(plan.get("confidence") or 70))

    clip_reasons: list[str] = []
    clip_warnings: list[str] = []

    for match in clip_matches:
        clip_reasons.extend(getattr(match, "reasons", []) or [])
        clip_warnings.extend(getattr(match, "warnings", []) or [])

    plan_path = (
        CORRECTED_DIR
        / f"{_safe_key(source_name)}.corrected.plan.json"
    )

    notes = [
        f"Created from full-video analysis: {source_name}",
        f"Detected production format: {format_name}",
        f"Corrected plan: {plan_path}",
        f"Clip requirement: {clip_requirement}",
        "Soundboard disabled by plan."
        if not queries
        else f"Sound queries: {', '.join(queries)}",
    ]

    project = CreatorProject(
        video_id=f"reference_{_safe_key(source_name)}",
        inspiration_title=title,
        inspiration_url="",
        template_type=creator_template,
        status=status,
        confidence=confidence,
        source_clip=source_files[0] if source_files else "",
        source_clips=source_files,
        sounds=sound_files,
        sound_queries=queries,
        text_lines=_project_text_lines(format_name, source_name, plan),
        missing=missing,
        notes=notes,
        character_name=character_name,
        correct_answer=1,
        approved=False,
        approval_notes="Created from corrected reference analysis.",
        clip_match_score=round(
            max(
                [
                    float(getattr(match, "score", 0) or 0)
                    for match in clip_matches
                ]
                or [0]
            ),
            2,
        ),
        clip_match_reasons=list(dict.fromkeys(clip_reasons)),
        clip_match_warnings=list(dict.fromkeys(clip_warnings)),
        recording_task=recording_task or (
            f"Record/provide: {clip_requirement}"
            if not source_files
            else ""
        ),
    )
    project.save()
    return project
