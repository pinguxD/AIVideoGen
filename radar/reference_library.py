from __future__ import annotations

import json
import shutil
import sqlite3
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE, VideoAnalysis, analyze_reference_video
from .production_planner import ProductionPlan, build_production_plan

REFERENCE_ROOT = BASE / "assets" / "reference_videos"
PENDING_DIR = REFERENCE_ROOT / "pending"
ANALYZED_DIR = REFERENCE_ROOT / "analyzed"
FAILED_DIR = REFERENCE_ROOT / "failed"
REPORT_DIR = BASE / "outputs" / "reference_reports"
DB_PATH = BASE / "outputs" / "reference_library.db"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    final_path TEXT,
    title_hint TEXT DEFAULT '',
    status TEXT NOT NULL,
    detected_format TEXT DEFAULT '',
    confidence INTEGER DEFAULT 0,
    can_auto_recreate INTEGER DEFAULT 0,
    analysis_path TEXT DEFAULT '',
    plan_path TEXT DEFAULT '',
    report_path TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    started_at TEXT NOT NULL,
    finished_at TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_reference_runs_status
ON reference_runs(status);

CREATE INDEX IF NOT EXISTS idx_reference_runs_source_name
ON reference_runs(source_name);
"""


def ensure_reference_dirs() -> None:
    for directory in (
        PENDING_DIR,
        ANALYZED_DIR,
        FAILED_DIR,
        REPORT_DIR,
        DB_PATH.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    ensure_reference_dirs()
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMA)
    con.commit()
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_name(path: Path) -> str:
    stem = "".join(
        ch if ch.isalnum() or ch in "-_ " else "_"
        for ch in path.stem
    ).strip()
    return stem or "reference"


def _unique_destination(directory: Path, source: Path) -> Path:
    candidate = directory / source.name
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = directory / f"{source.stem}_{index}{source.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _format_seconds(value: float) -> str:
    minutes, seconds = divmod(max(0, int(round(value))), 60)
    return f"{minutes}:{seconds:02d}"


def build_why_viral_report(
    analysis: VideoAnalysis,
    plan: ProductionPlan,
) -> str:
    visual = analysis.visual_structure
    scene_count = int(visual.get("scene_count") or 0)
    cuts_per_10 = float(visual.get("cuts_per_10_seconds") or 0.0)
    text_density = float(visual.get("average_text_density") or 0.0)
    insert_ratio = float(visual.get("visual_insert_ratio") or 0.0)
    motion = float(visual.get("average_motion") or 0.0)

    strengths: list[str] = []
    risks: list[str] = []

    if cuts_per_10 >= 5:
        strengths.append(
            f"Fast pacing: approximately {cuts_per_10:.1f} cuts per 10 seconds."
        )
    elif cuts_per_10 >= 2:
        strengths.append(
            f"Moderate pacing: approximately {cuts_per_10:.1f} cuts per 10 seconds."
        )
    else:
        strengths.append(
            "Continuous visual flow with relatively few hard cuts."
        )

    if analysis.probable_voiceover:
        strengths.append(
            f"Narration is present across an estimated {analysis.speech_ratio:.0%} "
            "of sampled audio windows."
        )

    if text_density >= 0.15:
        strengths.append(
            "Persistent text/caption structure keeps the viewer oriented."
        )

    if insert_ratio >= 0.18:
        strengths.append(
            f"Visual inserts or meme/image overlays appear in roughly "
            f"{insert_ratio:.0%} of sampled frames."
        )

    if motion >= 0.05:
        strengths.append("Background movement reduces visually dead moments.")

    if analysis.audio_events:
        strengths.append(
            f"{len(analysis.audio_events)} isolated impact/sound-effect moments "
            "were detected."
        )

    if analysis.probable_synthetic_voice:
        risks.append(
            "Voice may be synthetic, but this is only a heuristic estimate."
        )

    if plan.confidence < 70:
        risks.append(
            "Format confidence is below 70%; review the extracted plan manually."
        )

    if plan.missing_assets:
        risks.append(
            "The current asset library does not contain everything needed "
            "for faithful recreation."
        )

    lines = [
        f"# Why this reference may work",
        "",
        f"**Source:** `{analysis.source_file}`",
        f"**Duration:** {_format_seconds(analysis.duration)}",
        f"**Detected format:** `{plan.detected_format}`",
        f"**Format confidence:** {plan.confidence}%",
        f"**Recreation mode:** `{plan.recreation_mode}`",
        "",
        "## Structural evidence",
        "",
        f"- Scene count: {scene_count}",
        f"- Average scene length: "
        f"{float(visual.get('average_scene_length') or 0):.2f}s",
        f"- Cuts per 10 seconds: {cuts_per_10:.2f}",
        f"- Estimated text density: {text_density:.2f}",
        f"- Estimated visual-insert ratio: {insert_ratio:.2f}",
        f"- Estimated speech ratio: {analysis.speech_ratio:.2f}",
        f"- Estimated silence ratio: {analysis.silence_ratio:.2f}",
        "",
        "## Likely strengths",
        "",
    ]

    lines.extend(
        f"- {item}"
        for item in (strengths or ["No strong pattern was identified automatically."])
    )

    lines.extend(["", "## Risks / uncertainty", ""])
    lines.extend(
        f"- {item}"
        for item in (risks or ["No major automatic warning was raised."])
    )

    lines.extend(["", "## Production plan", ""])
    for segment in plan.timeline:
        lines.append(
            f"- `{segment.get('start', 0):.2f}s–{segment.get('end', 0):.2f}s`: "
            f"{segment.get('segment', 'segment')}"
        )

    lines.extend(["", "## Required assets", ""])
    lines.extend(
        f"- {item}"
        for item in (plan.required_assets or ["No structured requirements recorded."])
    )

    lines.extend(["", "## Missing from the current library", ""])
    lines.extend(
        f"- {item}"
        for item in (plan.missing_assets or ["Nothing detected as missing."])
    )

    lines.extend(
        [
            "",
            "## Important",
            "",
            "This report explains structural signals. It does not prove why a video "
            "went viral, because reach also depends on audience fit, topic demand, "
            "distribution, timing, and viewer behavior that are not visible from "
            "the media file alone.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_outputs(
    source: Path,
    analysis: VideoAnalysis,
    plan: ProductionPlan,
) -> tuple[Path, Path, Path]:
    safe = _safe_name(source)
    analysis_path = REPORT_DIR / f"{safe}.analysis.json"
    plan_path = REPORT_DIR / f"{safe}.plan.json"
    report_path = REPORT_DIR / f"{safe}.why_viral.md"

    analysis_path.write_text(
        json.dumps(asdict(analysis), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    plan_path.write_text(
        json.dumps(asdict(plan), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report_path.write_text(
        build_why_viral_report(analysis, plan),
        encoding="utf-8",
    )
    return analysis_path, plan_path, report_path


def analyze_one_reference(
    source: Path,
    title_hint: str = "",
    sample_interval: float = 0.5,
    move_after: bool = True,
) -> dict[str, Any]:
    ensure_reference_dirs()
    source = source.resolve()
    started_at = _now()

    with _connect() as con:
        cursor = con.execute(
            """
            INSERT INTO reference_runs (
                source_name, original_path, title_hint, status, started_at
            )
            VALUES (?, ?, ?, 'ANALYZING', ?)
            """,
            (source.name, str(source), title_hint, started_at),
        )
        run_id = int(cursor.lastrowid)
        con.commit()

    try:
        analysis = analyze_reference_video(
            source,
            title_hint=title_hint,
            sample_interval=max(0.2, float(sample_interval)),
        )
        plan = build_production_plan(analysis)
        analysis_path, plan_path, report_path = _write_outputs(
            source,
            analysis,
            plan,
        )

        final_path = source
        if move_after:
            destination = _unique_destination(ANALYZED_DIR, source)
            shutil.move(str(source), str(destination))
            final_path = destination

        finished_at = _now()

        with _connect() as con:
            con.execute(
                """
                UPDATE reference_runs
                SET status='ANALYZED',
                    final_path=?,
                    detected_format=?,
                    confidence=?,
                    can_auto_recreate=?,
                    analysis_path=?,
                    plan_path=?,
                    report_path=?,
                    finished_at=?
                WHERE id=?
                """,
                (
                    str(final_path),
                    plan.detected_format,
                    plan.confidence,
                    1 if plan.can_auto_recreate else 0,
                    str(analysis_path),
                    str(plan_path),
                    str(report_path),
                    finished_at,
                    run_id,
                ),
            )
            con.commit()

        return {
            "status": "ANALYZED",
            "source": str(source),
            "final_path": str(final_path),
            "format": plan.detected_format,
            "confidence": plan.confidence,
            "can_auto_recreate": plan.can_auto_recreate,
            "missing_assets": plan.missing_assets,
            "analysis_path": str(analysis_path),
            "plan_path": str(plan_path),
            "report_path": str(report_path),
        }

    except Exception as exc:
        error_text = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        final_path = source

        try:
            if move_after and source.exists():
                destination = _unique_destination(FAILED_DIR, source)
                shutil.move(str(source), str(destination))
                final_path = destination

                error_file = destination.with_suffix(
                    destination.suffix + ".error.txt"
                )
                error_file.write_text(error_text, encoding="utf-8")
        except Exception:
            pass

        with _connect() as con:
            con.execute(
                """
                UPDATE reference_runs
                SET status='FAILED',
                    final_path=?,
                    error_message=?,
                    finished_at=?
                WHERE id=?
                """,
                (
                    str(final_path),
                    str(exc),
                    _now(),
                    run_id,
                ),
            )
            con.commit()

        return {
            "status": "FAILED",
            "source": str(source),
            "final_path": str(final_path),
            "error": str(exc),
        }


def analyze_pending_references(
    sample_interval: float = 0.5,
    move_after: bool = True,
) -> list[dict[str, Any]]:
    ensure_reference_dirs()
    candidates = sorted(
        path
        for path in PENDING_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    results: list[dict[str, Any]] = []

    for index, source in enumerate(candidates, start=1):
        print(
            f"[{index}/{len(candidates)}] Analyzing {source.name}",
            flush=True,
        )
        result = analyze_one_reference(
            source,
            title_hint=source.stem.replace("_", " "),
            sample_interval=sample_interval,
            move_after=move_after,
        )
        results.append(result)

        if result["status"] == "ANALYZED":
            print(
                f"  -> {result['format']} "
                f"({result['confidence']}% confidence)",
                flush=True,
            )
        else:
            print(f"  -> FAILED: {result.get('error', 'unknown error')}", flush=True)

    return results


def list_reference_runs(limit: int = 500) -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT *
            FROM reference_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(row) for row in rows]
