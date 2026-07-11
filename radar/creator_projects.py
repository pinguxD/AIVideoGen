from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .sound_library import ensure_unique_sounds, search_local_unique
from .channel_feedback import classify_hook, personal_multiplier
from .clip_brain import choose_clips_for_project

BASE = Path(__file__).resolve().parents[1]
PROJECT_DIR = BASE / "outputs" / "creator_projects"
DRAFT_DIR = BASE / "outputs" / "drafts"
MINED_DIR = BASE / "assets" / "source" / "mined"
REPORT = BASE / "outputs" / "clip_miner_report.csv"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


@dataclass
class CreatorProject:
    video_id: str
    inspiration_title: str
    inspiration_url: str
    template_type: str
    status: str
    confidence: int
    source_clip: str = ""
    source_clips: list[str] = field(default_factory=list)
    sounds: list[str] = field(default_factory=list)
    sound_queries: list[str] = field(default_factory=list)
    text_lines: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    output_file: str = ""
    notes: list[str] = field(default_factory=list)
    character_name: str = ""
    correct_answer: int = 1
    approved: bool = False
    approval_notes: str = ""
    clip_match_score: float = 0.0
    clip_match_reasons: list[str] = field(default_factory=list)
    clip_match_warnings: list[str] = field(default_factory=list)
    recording_task: str = ""

    def save(self) -> Path:
        PROJECT_DIR.mkdir(parents=True, exist_ok=True)
        path = PROJECT_DIR / f"{self.video_id}.json"
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


def _normalise_template(value: str, title: str = "") -> str:
    value = (value or "").lower().strip()
    title_low = (title or "").lower()
    if value in {"guess_voice", "sound_replacement", "fact_card"}:
        return value
    if "guess" in title_low and any(x in title_low for x in ("voice", "sound", "scream")):
        return "guess_voice"
    if any(x in title_low for x in ("scream", "sound", "voice")):
        return "sound_replacement"
    if any(x in title_low for x in ("secret", "fact", "did you know", "99%", "most players")):
        return "fact_card"
    return "manual"


def _clip_candidates() -> list[Path]:
    return sorted(p for p in MINED_DIR.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT)


def _choose_clips(count: int = 5) -> list[Path]:
    clips = _clip_candidates()
    if not clips:
        return []

    ranked: list[Path] = []
    seen: set[str] = set()

    if REPORT.exists():
        try:
            df = pd.read_csv(REPORT).fillna("")
            df["_rating"] = pd.to_numeric(df.get("user_rating", 0), errors="coerce").fillna(0)
            df["_score"] = pd.to_numeric(df.get("score", 0), errors="coerce").fillna(0)
            df = df.sort_values(["_rating", "_score"], ascending=False)
            for _, row in df.iterrows():
                out = Path(str(row.get("output") or ""))
                if not out.is_absolute():
                    out = BASE / out
                if not out.exists():
                    out = MINED_DIR / out.name
                key = str(out.resolve()).lower() if out.exists() else ""
                if out.exists() and key not in seen:
                    ranked.append(out)
                    seen.add(key)
                if len(ranked) >= count:
                    return ranked
        except Exception as exc:
            print(f"[Creator AI] Could not read clip ratings: {exc}")

    for clip in clips:
        key = str(clip.resolve()).lower()
        if key not in seen:
            ranked.append(clip)
            seen.add(key)
        if len(ranked) >= count:
            break
    return ranked


def _sound_queries(template: str, title: str) -> list[str]:
    low = title.lower()
    if template == "guess_voice":
        return [
            "viral funny scream short",
            "goofy yell meme short",
            "monster roar short",
            "cartoon panic scream short",
        ]
    if template == "sound_replacement":
        return ["viral funny scream short"] if ("monster" in low or "scream" in low) else ["funny impact meme short"]
    return []


def _text_lines(template: str, title: str) -> list[str]:
    if template == "guess_voice":
        subject = "CHARACTER"
        match = re.search(r"(?:guess\s+)?(?:the\s+)?(?:real\s+)?([a-z0-9 _-]{2,30}?)\s+(?:voice|sound|scream)", title, re.I)
        if match:
            subject = match.group(1).strip().upper()
        return [f"GUESS THE REAL {subject} VOICE", "1", "2", "3", "4", "COMMENT BEFORE THE REVEAL"]
    if template == "sound_replacement":
        return ["WHICH SOUND FITS BEST?", "COMMENT YOUR PICK"]
    if template == "fact_card":
        return [title.strip() or "THIS ROBLOX FACT IS WILD..."]
    return []


def analyze_candidate(video: dict[str, Any], fetch_sounds: bool = False) -> CreatorProject:
    video_id = str(video.get("video_id") or "unknown")
    title = str(video.get("title") or "")
    template = _normalise_template(str(video.get("template_type") or ""), title)

    clip_count = 5 if template == "guess_voice" else 1
    character_match = re.search(r"(?:real\s+)?([a-z0-9 _-]{2,30}?)\s+(?:voice|sound|scream)", title, re.I)
    character_name = character_match.group(1).strip() if character_match else ""
    clips, clip_matches, clip_requirements, recording_task = choose_clips_for_project(
        title=title,
        template_type=template,
        character_name=character_name,
        count=clip_count,
    )
    queries = _sound_queries(template, title)

    if fetch_sounds:
        assets, unresolved = ensure_unique_sounds(queries, required_total=4 if template == "guess_voice" else len(queries))
    else:
        assets, unresolved = search_local_unique(queries, required_total=4 if template == "guess_voice" else len(queries))

    sound_files = [asset.file for asset in assets]
    source_files = [str(path.relative_to(BASE)).replace("\\", "/") for path in clips]

    missing: list[str] = []
    if not clips:
        missing.append("source gameplay/character clip")
    if template == "guess_voice" and len(clips) < 1:
        missing.append("one relevant character/gameplay clip")
    if template == "guess_voice" and len(sound_files) < 4:
        missing.append(f"{4 - len(sound_files)} more unique sounds")
    elif unresolved:
        missing.extend(f"sound: {query}" for query in unresolved)
    if template == "fact_card":
        missing.append("fact/script text (review before publishing)")
    if template == "manual":
        missing.append("manual template definition")

    hook_type = classify_hook(title)
    channel_multiplier = personal_multiplier(template, hook_type)

    if template == "manual":
        status, confidence = "MANUAL_ONLY", 25
    elif missing:
        status, confidence = "NEEDS_ASSETS", 72 if clips else 48
    else:
        status, confidence = "AUTO_READY", 94

    # Personalize confidence using automatic public performance feedback.
    confidence = int(max(1, min(99, round(confidence * channel_multiplier))))

    project = CreatorProject(
        video_id=video_id,
        inspiration_title=title,
        inspiration_url=str(video.get("url") or ""),
        template_type=template,
        status=status,
        confidence=confidence,
        source_clip=source_files[0] if source_files else "",
        source_clips=source_files,
        sounds=sound_files,
        sound_queries=queries,
        text_lines=_text_lines(template, title),
        missing=missing,
        character_name=character_name,
        clip_match_score=clip_matches[0].score if clip_matches else 0.0,
        clip_match_reasons=clip_matches[0].reasons if clip_matches else [],
        clip_match_warnings=clip_matches[0].warnings if clip_matches else [],
        recording_task=recording_task,
        notes=[
            "Clip Brain selected assets against the inspiration requirements, your ratings, and project feedback.",
            "Sound AI searches locally first, then Freesound until it has unique licensed assets.",
            f"Automatic channel-learning multiplier: {channel_multiplier:.2f} for {template}/{hook_type}.",
        ],
    )
    project.save()
    return project


def analyze_dataframe(df: pd.DataFrame, fetch_sounds: bool = False, limit: int = 100) -> list[CreatorProject]:
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    if df.empty:
        return []
    work = df.copy()
    if "opportunity_score" in work.columns:
        work["_score"] = pd.to_numeric(work["opportunity_score"], errors="coerce").fillna(0)
        work = work.sort_values("_score", ascending=False)
    return [analyze_candidate(row.to_dict(), fetch_sounds=fetch_sounds) for _, row in work.head(limit).iterrows()]



def _normalise_project_data(data: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "source_clip": "", "source_clips": [], "sounds": [], "sound_queries": [],
        "text_lines": [], "missing": [], "output_file": "", "notes": [],
        "character_name": "", "correct_answer": 1, "approved": False,
        "approval_notes": "", "clip_match_score": 0.0,
        "clip_match_reasons": [], "clip_match_warnings": [], "recording_task": "",
    }
    for key, value in defaults.items():
        data.setdefault(key, value.copy() if isinstance(value, list) else value)
    if not data.get("source_clips") and data.get("source_clip"):
        data["source_clips"] = [data["source_clip"]]
    allowed = set(CreatorProject.__dataclass_fields__)
    return {key: value for key, value in data.items() if key in allowed}

def load_projects() -> list[CreatorProject]:
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    projects: list[CreatorProject] = []
    for path in sorted(PROJECT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("source_clips", [data.get("source_clip", "")] if data.get("source_clip") else [])
            projects.append(CreatorProject(**_normalise_project_data(data)))
        except Exception as exc:
            print(f"[Creator AI] Could not load {path.name}: {exc}")
    return projects
def load_project(video_id: str) -> CreatorProject:
    path = PROJECT_DIR / f"{video_id}.json"

    if not path.exists():
        raise FileNotFoundError(f"Creator project not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # Compatibility with older saved projects.
    data.setdefault(
        "source_clips",
        [data.get("source_clip", "")]
        if data.get("source_clip")
        else [],
    )

    return CreatorProject(**_normalise_project_data(data))