from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

BASE = Path(__file__).resolve().parents[1]
MINED_DIR = BASE / "assets" / "source" / "mined"
REPORT = BASE / "outputs" / "clip_miner_report.csv"
DB_PATH = BASE / "outputs" / "clip_brain.db"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


@dataclass
class ClipMetadata:
    path: str
    duration: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    motion: float = 0.0
    camera_motion: float = 0.0
    edge_density: float = 0.0
    ui_risk: float = 0.0
    center_activity: float = 0.0
    scene_changes: int = 0
    closeup_score: float = 0.0
    clean_framing: float = 0.0
    visual_quality: float = 0.0
    shot_type: str = "unknown"
    pacing: str = "medium"
    tags: list[str] = field(default_factory=list)
    analyzed_at: str = ""


@dataclass
class ClipRequirements:
    template_type: str
    character_name: str = ""
    desired_shot: str = "medium"
    desired_pacing: str = "medium"
    minimum_duration: float = 6.0
    low_ui: bool = True
    character_visible: bool = True
    action: str = "idle_or_reaction"
    context_tokens: list[str] = field(default_factory=list)


@dataclass
class ClipMatch:
    path: str
    score: float
    reasons: list[str]
    warnings: list[str]
    metadata: ClipMetadata


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS clip_metadata (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            payload TEXT NOT NULL,
            analyzed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clip_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_path TEXT NOT NULL,
            video_id TEXT NOT NULL,
            template_type TEXT,
            character_name TEXT,
            action TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_clip ON clip_feedback(clip_path);
        CREATE INDEX IF NOT EXISTS idx_feedback_context ON clip_feedback(template_type, character_name);
        """
    )
    con.commit()
    return con


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _absolute(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE / path


def _tokenize(value: str) -> set[str]:
    ignored = {"the", "a", "an", "real", "voice", "sound", "roblox", "shorts", "short", "guess"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) > 2 and token not in ignored
    }


def _frame_features(frame: Any, previous: Any | None = None) -> dict[str, float]:
    import numpy as np

    rgb = frame[..., :3].astype("float32")
    # Analysis at a modest resolution keeps one-hour libraries practical.
    step_y = max(1, rgb.shape[0] // 180)
    step_x = max(1, rgb.shape[1] // 320)
    small = rgb[::step_y, ::step_x]
    gray = small.mean(axis=2)

    brightness = float(gray.mean())
    contrast = float(gray.std())
    gx = float(np.abs(np.diff(gray, axis=1)).mean()) if gray.shape[1] > 1 else 0.0
    gy = float(np.abs(np.diff(gray, axis=0)).mean()) if gray.shape[0] > 1 else 0.0
    edge = (gx + gy) / 2.0

    h, w = gray.shape
    y1, y2 = int(h * 0.2), int(h * 0.8)
    x1, x2 = int(w * 0.2), int(w * 0.8)
    center = gray[y1:y2, x1:x2]
    center_activity = float(center.std()) if center.size else 0.0

    border = np.concatenate([
        gray[: max(1, h // 7), :].ravel(),
        gray[-max(1, h // 7):, :].ravel(),
        gray[:, : max(1, w // 8)].ravel(),
        gray[:, -max(1, w // 8):].ravel(),
    ])
    border_edge = float(border.std()) if border.size else 0.0
    ui_risk = min(100.0, max(0.0, (border_edge - center_activity * 0.45) * 2.4 + edge * 0.7))

    motion = 0.0
    if previous is not None and getattr(previous, "shape", None) == small.shape:
        motion = float(np.abs(small - previous).mean())

    return {
        "small": small,
        "brightness": brightness,
        "contrast": contrast,
        "edge": edge,
        "center_activity": center_activity,
        "ui_risk": ui_risk,
        "motion": motion,
    }


def analyze_clip(path_value: str | Path, force: bool = False) -> ClipMetadata:
    from moviepy.editor import VideoFileClip
    import numpy as np

    path = _absolute(path_value).resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    rel = _relative(path)
    mtime = path.stat().st_mtime
    con = _connect()
    try:
        if not force:
            row = con.execute("SELECT mtime, payload FROM clip_metadata WHERE path=?", (rel,)).fetchone()
            if row and abs(float(row["mtime"]) - mtime) < 0.001:
                return ClipMetadata(**json.loads(row["payload"]))
    finally:
        con.close()

    with VideoFileClip(str(path)) as clip:
        duration = float(clip.duration or 0.0)
        if duration <= 0:
            raise RuntimeError(f"No usable duration: {path}")

        sample_count = min(16, max(5, int(math.ceil(duration * 1.5))))
        times = np.linspace(0.05, max(0.05, duration - 0.05), sample_count)
        values: list[dict[str, float]] = []
        previous = None
        scene_changes = 0
        for timestamp in times:
            data = _frame_features(clip.get_frame(float(timestamp)), previous)
            if data["motion"] > 24:
                scene_changes += 1
            previous = data.pop("small")
            values.append(data)

    def avg(key: str) -> float:
        return float(sum(item[key] for item in values) / max(1, len(values)))

    brightness = avg("brightness")
    contrast = avg("contrast")
    motion = avg("motion")
    edge = avg("edge")
    ui_risk = avg("ui_risk")
    center_activity = avg("center_activity")

    exposure_score = max(0.0, 100.0 - abs(brightness - 118.0) * 0.85)
    closeup_score = max(0.0, min(100.0, center_activity * 2.3 - ui_risk * 0.25))
    clean_framing = max(0.0, min(100.0, 100.0 - ui_risk * 0.75 + center_activity * 0.45))
    motion_fit = max(0.0, 100.0 - abs(motion - 10.0) * 4.0)
    visual_quality = max(
        0.0,
        min(100.0, exposure_score * 0.28 + clean_framing * 0.34 + motion_fit * 0.20 + min(100.0, contrast * 2.0) * 0.18),
    )

    if closeup_score >= 68:
        shot_type = "closeup"
    elif closeup_score >= 40:
        shot_type = "medium"
    else:
        shot_type = "wide"

    if motion >= 18:
        pacing = "fast"
    elif motion <= 5:
        pacing = "calm"
    else:
        pacing = "medium"

    tags = [shot_type, pacing]
    if ui_risk <= 35:
        tags.append("low_ui")
    if clean_framing >= 65:
        tags.append("clean_framing")
    if center_activity >= 25:
        tags.append("subject_centered")
    if scene_changes >= 2:
        tags.append("multiple_changes")

    metadata = ClipMetadata(
        path=rel,
        duration=round(duration, 3),
        brightness=round(brightness, 3),
        contrast=round(contrast, 3),
        motion=round(motion, 3),
        camera_motion=round(motion, 3),
        edge_density=round(edge, 3),
        ui_risk=round(ui_risk, 3),
        center_activity=round(center_activity, 3),
        scene_changes=scene_changes,
        closeup_score=round(closeup_score, 2),
        clean_framing=round(clean_framing, 2),
        visual_quality=round(visual_quality, 2),
        shot_type=shot_type,
        pacing=pacing,
        tags=tags,
        analyzed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    con = _connect()
    try:
        con.execute(
            "INSERT INTO clip_metadata(path,mtime,payload,analyzed_at) VALUES(?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime,payload=excluded.payload,analyzed_at=excluded.analyzed_at",
            (rel, mtime, json.dumps(asdict(metadata)), metadata.analyzed_at),
        )
        con.commit()
    finally:
        con.close()
    return metadata


def requirements_from_inspiration(title: str, template_type: str, character_name: str = "") -> ClipRequirements:
    title_low = (title or "").lower()
    character = (character_name or "").strip()
    if not character:
        match = re.search(r"(?:real\s+)?([a-z0-9 _-]{2,30}?)\s+(?:voice|sound|scream)", title or "", re.I)
        if match:
            character = match.group(1).strip()

    if template_type == "guess_voice":
        shot, pacing, duration, action = "closeup", "medium", 7.0, "idle_or_reaction"
    elif template_type == "sound_replacement":
        shot, pacing, duration, action = "medium", "fast", 6.0, "reaction_or_attack"
    elif template_type == "fact_card":
        shot, pacing, duration, action = "medium", "medium", 9.0, "continuous_gameplay"
    else:
        shot, pacing, duration, action = "medium", "medium", 6.0, "unknown"

    if any(word in title_low for word in ("monster", "scream", "attack", "jumpscare")):
        pacing = "fast"
        action = "reaction_or_attack"
    return ClipRequirements(
        template_type=template_type,
        character_name=character,
        desired_shot=shot,
        desired_pacing=pacing,
        minimum_duration=duration,
        low_ui=True,
        character_visible=bool(character),
        action=action,
        context_tokens=sorted(_tokenize(f"{title} {character}")),
    )


def save_feedback(
    clip_path: str,
    video_id: str,
    template_type: str,
    character_name: str,
    action: str,
    reason: str = "",
) -> None:
    con = _connect()
    try:
        con.execute(
            "INSERT INTO clip_feedback(clip_path,video_id,template_type,character_name,action,reason,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                _relative(_absolute(clip_path)),
                video_id,
                template_type,
                character_name,
                action,
                reason,
                time.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
        con.commit()
    finally:
        con.close()


def _feedback_adjustment(path: str, requirements: ClipRequirements) -> tuple[float, list[str]]:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT action,reason,template_type,character_name FROM clip_feedback WHERE clip_path=? ORDER BY id DESC LIMIT 100",
            (path,),
        ).fetchall()
    finally:
        con.close()

    adjustment = 0.0
    notes: list[str] = []
    for row in rows:
        same_template = not row["template_type"] or row["template_type"] == requirements.template_type
        same_character = not row["character_name"] or row["character_name"].lower() == requirements.character_name.lower()
        contextual = same_template and same_character
        action = row["action"]
        if action == "fits":
            adjustment += 14 if contextual else 4
            notes.append("Previously approved for this context" if contextual else "Previously approved")
        elif action in {"does_not_fit", "wrong_character", "wrong_action", "character_not_visible", "too_much_ui", "poor_framing"}:
            adjustment -= 26 if contextual else 6
            notes.append(f"Past rejection: {action.replace('_', ' ')}")
        elif action == "never_use":
            adjustment -= 100
            notes.append("Globally blacklisted")
    return adjustment, notes


def _manual_rating_map() -> dict[str, float]:
    import csv

    result: dict[str, float] = {}
    if not REPORT.exists():
        return result
    try:
        with REPORT.open("r", newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = row.get("user_rating") or 0
                try:
                    rating = float(value)
                except (TypeError, ValueError):
                    rating = 0.0
                path = row.get("output") or ""
                if path:
                    result[_relative(_absolute(path))] = rating
    except Exception:
        pass
    return result


def score_clip(metadata: ClipMetadata, requirements: ClipRequirements, user_rating: float = 0.0) -> ClipMatch:
    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0

    # Visual suitability (measurable without pretending we recognize the exact Roblox character).
    score += metadata.visual_quality * 0.22
    score += metadata.clean_framing * 0.18
    score += max(0.0, 100.0 - metadata.ui_risk) * 0.12

    if metadata.duration >= requirements.minimum_duration:
        score += 10
        reasons.append("Long enough for the template")
    else:
        score -= 12
        warnings.append("Shorter than the requested shot")

    shot_points = {
        ("closeup", "closeup"): 18,
        ("closeup", "medium"): 9,
        ("medium", "medium"): 15,
        ("medium", "closeup"): 11,
        ("medium", "wide"): 5,
        ("wide", "wide"): 12,
    }
    score += shot_points.get((requirements.desired_shot, metadata.shot_type), 0)
    if metadata.shot_type == requirements.desired_shot:
        reasons.append(f"Matches requested {requirements.desired_shot} shot")
    else:
        warnings.append(f"Detected {metadata.shot_type}; wanted {requirements.desired_shot}")

    if metadata.pacing == requirements.desired_pacing:
        score += 10
        reasons.append("Pacing matches inspiration")
    elif {metadata.pacing, requirements.desired_pacing} == {"medium", "fast"}:
        score += 5
    else:
        warnings.append(f"Pacing is {metadata.pacing}")

    filename_tokens = _tokenize(Path(metadata.path).stem)
    overlap = filename_tokens.intersection(requirements.context_tokens)
    if overlap:
        score += min(18.0, 6.0 * len(overlap))
        reasons.append("Filename/context match: " + ", ".join(sorted(overlap)))
    elif requirements.character_name:
        warnings.append("Character identity is not verified")

    if metadata.ui_risk <= 35:
        reasons.append("Low estimated UI obstruction")
    elif metadata.ui_risk >= 65:
        warnings.append("High estimated UI obstruction")

    if user_rating:
        score += (user_rating - 3.0) * 5.0
        reasons.append(f"Your library rating: {user_rating:g}/5")

    feedback, feedback_notes = _feedback_adjustment(metadata.path, requirements)
    score += feedback
    for note in feedback_notes:
        (reasons if "approved" in note.lower() else warnings).append(note)

    return ClipMatch(
        path=metadata.path,
        score=round(max(0.0, min(100.0, score)), 1),
        reasons=reasons[:6],
        warnings=warnings[:6],
        metadata=metadata,
    )


def rank_clips(requirements: ClipRequirements, limit: int = 10, force_analysis: bool = False) -> list[ClipMatch]:
    ratings = _manual_rating_map()
    clips = sorted(p for p in MINED_DIR.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXT)
    matches: list[ClipMatch] = []
    for path in clips:
        try:
            metadata = analyze_clip(path, force=force_analysis)
            matches.append(score_clip(metadata, requirements, ratings.get(metadata.path, 0.0)))
        except Exception as exc:
            print(f"[Clip Brain] Could not analyze {path.name}: {exc}")
    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[:limit]


def choose_clips_for_project(
    title: str,
    template_type: str,
    character_name: str = "",
    count: int = 5,
) -> tuple[list[Path], list[ClipMatch], ClipRequirements, str]:
    requirements = requirements_from_inspiration(title, template_type, character_name)
    matches = rank_clips(requirements, limit=max(count, 10))
    selected = [_absolute(match.path) for match in matches[:count] if _absolute(match.path).exists()]

    recording_task = ""
    best_score = matches[0].score if matches else 0.0
    if not matches or best_score < 62:
        subject = requirements.character_name or "the required character"
        recording_task = (
            f"Record a {requirements.minimum_duration:.0f}-10 second {requirements.desired_shot} shot of {subject}; "
            f"keep the subject centered, reduce UI, and use {requirements.desired_pacing} pacing."
        )
    return selected, matches, requirements, recording_task
