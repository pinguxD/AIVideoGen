from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .full_video_analyzer import (
    ANALYSIS_DIR,
    BASE,
    MEME_TEMPLATE_DIR,
    SOUND_DIR,
    VideoAnalysis,
)

PLAN_DIR = BASE / "outputs" / "production_plans"
MINED_DIR = BASE / "assets" / "source" / "mined"


@dataclass
class ProductionPlan:
    source_analysis: str
    detected_format: str
    confidence: int
    can_auto_recreate: bool
    recreation_mode: str
    required_assets: list[str] = field(default_factory=list)
    available_assets: list[str] = field(default_factory=list)
    missing_assets: list[str] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    audio_plan: dict[str, Any] = field(default_factory=dict)
    visual_plan: dict[str, Any] = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def save(self) -> Path:
        PLAN_DIR.mkdir(parents=True, exist_ok=True)
        source_name = Path(self.source_analysis).stem.replace(".analysis", "")
        path = PLAN_DIR / f"{source_name}.plan.json"
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def _count_files(directory: Path, extensions: set[str]) -> int:
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    )


def _classify_format(analysis: VideoAnalysis) -> tuple[str, int, list[str]]:
    visual = analysis.visual_structure
    scene_count = int(visual.get("scene_count") or 0)
    cuts_per_10 = float(visual.get("cuts_per_10_seconds") or 0.0)
    insert_ratio = float(visual.get("visual_insert_ratio") or 0.0)
    text_density = float(visual.get("average_text_density") or 0.0)
    audio_event_count = len(analysis.audio_events)
    title = analysis.title_hint.lower()

    scores = {
        "narrated_fact_list": 0.0,
        "narrated_story": 0.0,
        "interactive_guess": 0.0,
        "sound_replacement": 0.0,
        "meme_edit": 0.0,
        "gameplay_caption": 0.0,
        "manual_complex_edit": 0.0,
    }
    evidence: list[str] = []

    if analysis.probable_voiceover:
        scores["narrated_fact_list"] += 2.0
        scores["narrated_story"] += 1.6
        evidence.append("continuous speech/narration detected")

    if any(word in title for word in ("fact", "did you know", "save your life", "things you")):
        scores["narrated_fact_list"] += 3.0
        evidence.append("title indicates a fact/list format")

    if any(word in title for word in ("story", "then this happened", "i survived")):
        scores["narrated_story"] += 2.8

    if any(word in title for word in ("guess", "which voice", "real voice", "pick one")):
        scores["interactive_guess"] += 3.2

    if any(word in title for word in ("sound", "scream", "voice")):
        scores["sound_replacement"] += 1.2

    if insert_ratio >= 0.22:
        scores["narrated_fact_list"] += 1.7
        scores["meme_edit"] += 1.2
        evidence.append("visual insert overlays detected")

    if text_density >= 0.18:
        scores["narrated_fact_list"] += 1.0
        scores["gameplay_caption"] += 1.2
        evidence.append("persistent on-screen text detected")

    if audio_event_count >= 3 and not analysis.probable_voiceover:
        scores["interactive_guess"] += 1.6
        scores["sound_replacement"] += 1.7
        evidence.append("multiple isolated sound events detected")

    if analysis.meme_template_matches:
        scores["meme_edit"] += 2.4
        evidence.append("local meme template visual match found")

    if cuts_per_10 >= 6.0:
        scores["manual_complex_edit"] += 1.8
        scores["meme_edit"] += 0.8
        evidence.append("high cut rate detected")

    if (
        not analysis.probable_voiceover
        and audio_event_count <= 2
        and text_density >= 0.12
    ):
        scores["gameplay_caption"] += 1.8

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    label, score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = score - second
    confidence = int(max(20, min(97, round(35 + score * 10 + margin * 8))))

    if score < 2.0 or margin < 0.45:
        label = "manual_complex_edit"
        confidence = min(confidence, 55)
        evidence.append("format evidence is ambiguous")

    return label, confidence, evidence[:10]


def build_production_plan(analysis: VideoAnalysis) -> ProductionPlan:
    format_name, confidence, evidence = _classify_format(analysis)

    mined_count = _count_files(
        MINED_DIR,
        {".mp4", ".mov", ".mkv", ".webm"},
    )
    sound_count = _count_files(
        SOUND_DIR,
        {".wav", ".mp3", ".m4a", ".ogg", ".flac"},
    )
    meme_count = _count_files(
        MEME_TEMPLATE_DIR,
        {".png", ".jpg", ".jpeg", ".webp"},
    )

    required: list[str] = []
    available: list[str] = []
    missing: list[str] = []
    timeline: list[dict[str, Any]] = []
    audio_plan: dict[str, Any] = {}
    visual_plan: dict[str, Any] = {}
    warnings = list(analysis.warnings)

    duration = max(1.0, analysis.duration)

    if format_name == "narrated_fact_list":
        required = [
            "continuous gameplay background",
            "fact/list script",
            "voiceover",
            "timed captions",
            "relevant visual inserts",
        ]
        if mined_count:
            available.append(f"{mined_count} mined gameplay clips")
        else:
            missing.append("continuous background gameplay")

        missing.extend(
            [
                "verified fact/list script",
                "voiceover voice or TTS configuration",
            ]
        )

        if analysis.visual_structure.get("visual_insert_ratio", 0) >= 0.15:
            missing.append("2-5 relevant images or meme/visual inserts")

        timeline = [
            {"segment": "hook", "start": 0.0, "end": min(0.8, duration)},
            {"segment": "fact_1", "start": 0.8, "end": round(duration * 0.36, 2)},
            {"segment": "fact_2", "start": round(duration * 0.36, 2), "end": round(duration * 0.66, 2)},
            {"segment": "fact_3", "start": round(duration * 0.66, 2), "end": round(duration * 0.94, 2)},
            {"segment": "loop_or_cta", "start": round(duration * 0.94, 2), "end": duration},
        ]
        audio_plan = {
            "voiceover": "required",
            "soundboard": False,
            "music": "optional low-volume bed",
            "reference_speech_ratio": analysis.speech_ratio,
        }
        visual_plan = {
            "background": "continuous gameplay",
            "captions": "large synchronized captions",
            "visual_inserts": "replace or illustrate each fact",
            "estimated_insert_ratio": analysis.visual_structure.get(
                "visual_insert_ratio",
                0,
            ),
        }

    elif format_name == "interactive_guess":
        required = [
            "one relevant character/source clip",
            "3-4 distinct sounds",
            "option labels",
            "reveal segment",
        ]
        if mined_count:
            available.append(f"{mined_count} mined gameplay clips")
        else:
            missing.append("relevant character/source clip")

        if sound_count >= 4:
            available.append(f"{sound_count} local sounds")
        else:
            missing.append(f"{max(0, 4 - sound_count)} additional distinct sounds")

        timeline = [
            {"segment": "hook", "start": 0.0, "end": 0.6},
            {"segment": "option_1", "start": 0.6, "end": 1.8},
            {"segment": "option_2", "start": 1.8, "end": 3.0},
            {"segment": "option_3", "start": 3.0, "end": 4.2},
            {"segment": "option_4", "start": 4.2, "end": 5.4},
            {"segment": "comment_prompt", "start": 5.4, "end": 6.3},
            {"segment": "reveal", "start": 6.3, "end": min(duration, 8.5)},
        ]
        audio_plan = {
            "voiceover": False,
            "soundboard": True,
            "required_unique_sounds": 4,
            "replay_correct_sound_on_reveal": True,
        }
        visual_plan = {
            "background": "relevant character clip",
            "captions": "option numbers + reveal",
            "visual_inserts": False,
        }

    elif format_name == "sound_replacement":
        required = [
            "one matching visual clip",
            "one approved meme/sound effect",
            "caption/hook",
        ]
        if mined_count:
            available.append(f"{mined_count} mined gameplay clips")
        else:
            missing.append("matching visual clip")
        if sound_count:
            available.append(f"{sound_count} local sounds")
        else:
            missing.append("approved replacement sound")

        audio_plan = {
            "voiceover": False,
            "soundboard": True,
            "required_unique_sounds": 1,
        }
        visual_plan = {
            "background": "matching source action",
            "captions": "hook only",
        }

    elif format_name == "meme_edit":
        required = [
            "matching background clip",
            "meme template/insert",
            "matching sound or caption",
        ]
        if mined_count:
            available.append(f"{mined_count} mined clips")
        else:
            missing.append("background clip")
        if meme_count or analysis.meme_template_matches:
            available.append("meme template match/library")
        else:
            missing.append("matching meme template image")
        if not analysis.local_sound_matches:
            missing.append("matching or approved alternative sound")

        audio_plan = {
            "voiceover": analysis.probable_voiceover,
            "soundboard": not analysis.probable_voiceover,
        }
        visual_plan = {
            "background": "gameplay or animation",
            "visual_inserts": True,
            "matched_templates": analysis.meme_template_matches,
        }

    elif format_name in {"narrated_story", "gameplay_caption"}:
        required = [
            "continuous gameplay",
            "script/captions",
        ]
        if analysis.probable_voiceover:
            required.append("voiceover")
            missing.append("script and voiceover voice/TTS configuration")
        elif format_name == "gameplay_caption":
            missing.append("caption text")

        if mined_count:
            available.append(f"{mined_count} mined clips")
        else:
            missing.append("background gameplay")

        audio_plan = {
            "voiceover": analysis.probable_voiceover,
            "soundboard": False,
        }
        visual_plan = {
            "background": "continuous gameplay",
            "captions": "timed narrative captions",
        }

    else:
        required = ["manual production plan review"]
        missing.append(
            "complex or uncertain format: approve/edit the extracted timeline manually"
        )
        audio_plan = {
            "voiceover": analysis.probable_voiceover,
            "soundboard": False,
        }
        visual_plan = {
            "scene_count": analysis.visual_structure.get("scene_count", 0),
            "cuts_per_10_seconds": analysis.visual_structure.get(
                "cuts_per_10_seconds",
                0,
            ),
        }

    # Auto recreation is conservative on purpose.
    can_auto = not missing and confidence >= 75
    mode = (
        "AUTO_READY"
        if can_auto
        else ("NEEDS_INPUTS" if confidence >= 58 else "MANUAL_REVIEW")
    )

    return ProductionPlan(
        source_analysis=analysis.source_file,
        detected_format=format_name,
        confidence=confidence,
        can_auto_recreate=can_auto,
        recreation_mode=mode,
        required_assets=required,
        available_assets=available,
        missing_assets=list(dict.fromkeys(missing)),
        timeline=timeline,
        audio_plan=audio_plan,
        visual_plan=visual_plan,
        explanation=evidence,
        warnings=warnings,
    )
