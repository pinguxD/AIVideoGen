from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analysis_feedback import (
    get_analysis_correction,
    list_timeline_corrections,
)
from .full_video_analyzer import BASE
from .reference_library import REPORT_DIR

CORRECTED_DIR = BASE / "outputs" / "corrected_reference_analysis"

FORMAT_DEFAULTS = {
    "narrated_fact_list": {
        "audio_plan": {
            "voiceover": "required",
            "soundboard": False,
            "music": "optional low-volume bed",
        },
        "visual_plan": {
            "background": "continuous gameplay",
            "captions": "large synchronized captions",
            "visual_inserts": "relevant images/memes per fact",
        },
    },
    "narrated_story": {
        "audio_plan": {
            "voiceover": "required",
            "soundboard": False,
            "music": "optional emotional bed",
        },
        "visual_plan": {
            "background": "continuous or story-matched gameplay",
            "captions": "timed narrative captions",
        },
    },
    "interactive_guess": {
        "audio_plan": {
            "voiceover": False,
            "soundboard": True,
            "required_unique_sounds": 4,
            "replay_correct_sound_on_reveal": True,
        },
        "visual_plan": {
            "background": "relevant character/source clip",
            "captions": "option labels + reveal",
        },
    },
    "sound_replacement": {
        "audio_plan": {
            "voiceover": False,
            "soundboard": True,
            "required_unique_sounds": 1,
        },
        "visual_plan": {
            "background": "matching visual action",
            "captions": "short hook",
        },
    },
    "meme_edit": {
        "audio_plan": {
            "voiceover": "optional",
            "soundboard": "context-dependent",
        },
        "visual_plan": {
            "background": "gameplay or animation",
            "visual_inserts": "meme template / reaction image",
        },
    },
    "gameplay_caption": {
        "audio_plan": {
            "voiceover": False,
            "soundboard": False,
            "music": "optional",
        },
        "visual_plan": {
            "background": "continuous gameplay",
            "captions": "primary storytelling layer",
        },
    },
    "manual_complex_edit": {
        "audio_plan": {
            "voiceover": "unknown",
            "soundboard": False,
        },
        "visual_plan": {
            "manual_review": True,
        },
    },
}


def _safe_source_key(source_name: str) -> str:
    return "".join(
        ch if ch.isalnum() or ch in "-_" else "_"
        for ch in Path(source_name).stem
    ) or "reference"


def find_report_files(source_name: str) -> tuple[Path | None, Path | None]:
    """
    Locate report files using the original filename first.

    reference_library.py keeps spaces in report filenames, while source_key
    replaces spaces with underscores for database-safe identifiers.
    """
    original_stem = Path(source_name).stem.strip()
    safe_key = _safe_source_key(source_name)

    exact_analysis = REPORT_DIR / f"{original_stem}.analysis.json"
    exact_plan = REPORT_DIR / f"{original_stem}.plan.json"

    if exact_analysis.exists():
        analysis_path = exact_analysis
    else:
        analysis_candidates = list(
            REPORT_DIR.glob(f"{original_stem}*.analysis.json")
        )
        if not analysis_candidates:
            analysis_candidates = list(
                REPORT_DIR.glob(f"{safe_key}*.analysis.json")
            )
        analysis_path = analysis_candidates[0] if analysis_candidates else None

    if exact_plan.exists():
        plan_path = exact_plan
    else:
        plan_candidates = list(
            REPORT_DIR.glob(f"{original_stem}*.plan.json")
        )
        if not plan_candidates:
            plan_candidates = list(
                REPORT_DIR.glob(f"{safe_key}*.plan.json")
            )
        plan_path = plan_candidates[0] if plan_candidates else None

    return analysis_path, plan_path


def load_review_bundle(source_name: str) -> dict[str, Any]:
    source_key = _safe_source_key(source_name)
    analysis_path, plan_path = find_report_files(source_name)

    analysis: dict[str, Any] = {}
    plan: dict[str, Any] = {}

    if analysis_path and analysis_path.exists():
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if plan_path and plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))

    return {
        "source_key": source_key,
        "source_name": source_name,
        "analysis": analysis,
        "plan": plan,
        "correction": get_analysis_correction(source_key) or {},
        "timeline_corrections": list_timeline_corrections(source_key),
    }


def write_corrected_bundle(source_name: str) -> tuple[Path, Path]:
    bundle = load_review_bundle(source_name)
    source_key = bundle["source_key"]
    correction = bundle["correction"]
    analysis = dict(bundle["analysis"])
    plan = dict(bundle["plan"])

    corrected_format = (
        str(correction.get("corrected_format") or "").strip()
        or str(plan.get("detected_format") or "manual_complex_edit")
    )

    analysis["human_correction"] = correction
    analysis["human_timeline_events"] = bundle["timeline_corrections"]

    plan["original_detected_format"] = plan.get("detected_format", "")
    plan["detected_format"] = corrected_format
    plan["human_corrected"] = True
    plan["human_labels"] = {
        "hook_type": correction.get("hook_type", ""),
        "video_goal": correction.get("video_goal", ""),
        "emotion": correction.get("emotion", ""),
        "ending_type": correction.get("ending_type", ""),
        "voice_type": correction.get("voice_type", ""),
        "voice_style": correction.get("voice_style", ""),
        "caption_style": correction.get("caption_style", ""),
        "meme_usage": correction.get("meme_usage", ""),
        "sound_usage": correction.get("sound_usage", ""),
        "notes": correction.get("notes", ""),
    }

    defaults = FORMAT_DEFAULTS.get(
        corrected_format,
        FORMAT_DEFAULTS["manual_complex_edit"],
    )
    plan["audio_plan"] = {
        **defaults.get("audio_plan", {}),
        **plan.get("audio_plan", {}),
    }
    plan["visual_plan"] = {
        **defaults.get("visual_plan", {}),
        **plan.get("visual_plan", {}),
    }

    # Human choice wins over incompatible automatic defaults.
    if corrected_format in {
        "narrated_fact_list",
        "narrated_story",
        "gameplay_caption",
    }:
        plan["audio_plan"]["soundboard"] = False
    elif corrected_format in {"interactive_guess", "sound_replacement"}:
        plan["audio_plan"]["soundboard"] = True

    plan["timeline_corrections"] = bundle["timeline_corrections"]

    CORRECTED_DIR.mkdir(parents=True, exist_ok=True)
    corrected_analysis_path = CORRECTED_DIR / f"{source_key}.corrected.analysis.json"
    corrected_plan_path = CORRECTED_DIR / f"{source_key}.corrected.plan.json"

    corrected_analysis_path.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    corrected_plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return corrected_analysis_path, corrected_plan_path
