from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .full_video_analyzer import BASE

DB_PATH = BASE / "outputs" / "reference_queue.db"
TREND_REPORT = BASE / "outputs" / "trend_report.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reference_queue (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    channel_title TEXT DEFAULT '',
    view_count INTEGER DEFAULT 0,
    subscriber_count INTEGER DEFAULT 0,
    age_days REAL DEFAULT 0,
    primary_format TEXT DEFAULT '',
    classification_confidence INTEGER DEFAULT 0,
    learning_value INTEGER DEFAULT 0,
    novelty_score INTEGER DEFAULT 0,
    recreation_score INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    reasons_json TEXT DEFAULT '[]',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMA)
    con.commit()
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def score_learning_value(row: dict[str, Any]) -> tuple[int, list[str]]:
    views = max(1, _int(row.get("view_count")))
    subscribers = max(1, _int(row.get("subscriber_count")))
    age_days = max(0.05, _float(row.get("age_days") or 1))
    confidence = _int(row.get("classification_confidence"))
    recreation = _int(
        row.get("auto_recreate_score")
        or row.get("production_score")
        or 0
    )
    format_name = str(
        row.get("primary_format")
        or row.get("template_type")
        or ""
    )

    views_per_day = views / age_days
    views_per_sub = views / subscribers

    velocity_score = min(100.0, math.log10(views_per_day + 10) * 24.0)
    small_channel_score = min(
        100.0,
        math.log10(views_per_sub + 1) * 42.0,
    )

    novelty = 60
    common_formats = {
        "fact_card",
        "guess_voice",
        "meme_caption",
        "sound_replacement",
    }
    if format_name not in common_formats:
        novelty += 20
    if confidence < 70:
        novelty += 10
    novelty = min(100, novelty)

    score = int(
        max(
            0,
            min(
                100,
                0.30 * velocity_score
                + 0.20 * small_channel_score
                + 0.20 * novelty
                + 0.15 * recreation
                + 0.10 * confidence
                + 5,
            ),
        )
    )

    reasons: list[str] = []
    if views_per_day >= 25000:
        reasons.append("high recent view velocity")
    if views_per_sub >= 20:
        reasons.append("strong views-per-subscriber proof")
    if novelty >= 80:
        reasons.append("uncommon or uncertain format worth learning")
    if recreation >= 75:
        reasons.append("likely useful for the current workflow")
    if confidence >= 80:
        reasons.append("classification is relatively confident")

    if not reasons:
        reasons.append("balanced learning candidate")

    return score, reasons


def update_reference_queue(
    source_csv: Path = TREND_REPORT,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not source_csv.exists():
        raise FileNotFoundError(
            f"Trend report not found: {source_csv}. Run trend_radar.py first."
        )

    frame = pd.read_csv(source_csv).fillna("")
    candidates: list[dict[str, Any]] = []

    for _, series in frame.iterrows():
        row = series.to_dict()
        video_id = str(row.get("video_id") or "").strip()
        if not video_id:
            continue

        learning_value, reasons = score_learning_value(row)
        candidate = {
            "video_id": video_id,
            "title": str(row.get("title") or ""),
            "url": str(
                row.get("url")
                or f"https://www.youtube.com/shorts/{video_id}"
            ),
            "channel_title": str(row.get("channel_title") or ""),
            "view_count": _int(row.get("view_count")),
            "subscriber_count": _int(row.get("subscriber_count")),
            "age_days": _float(row.get("age_days")),
            "primary_format": str(
                row.get("primary_format")
                or row.get("template_type")
                or ""
            ),
            "classification_confidence": _int(
                row.get("classification_confidence")
            ),
            "learning_value": learning_value,
            "novelty_score": 0,
            "recreation_score": _int(
                row.get("auto_recreate_score")
                or row.get("production_score")
            ),
            "status": "DISCOVERED",
            "reasons": reasons,
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: item["learning_value"],
        reverse=True,
    )
    selected = candidates[: max(1, int(limit))]
    now = _now()

    with _connect() as con:
        for item in selected:
            existing = con.execute(
                "SELECT status, first_seen FROM reference_queue WHERE video_id=?",
                (item["video_id"],),
            ).fetchone()

            status = (
                str(existing["status"])
                if existing
                and str(existing["status"]) not in {"REJECTED", "FULLY_ANALYZED"}
                else item["status"]
            )
            first_seen = str(existing["first_seen"]) if existing else now

            con.execute(
                """
                INSERT INTO reference_queue (
                    video_id, title, url, channel_title,
                    view_count, subscriber_count, age_days,
                    primary_format, classification_confidence,
                    learning_value, novelty_score, recreation_score,
                    status, reasons_json, first_seen, last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    url=excluded.url,
                    channel_title=excluded.channel_title,
                    view_count=excluded.view_count,
                    subscriber_count=excluded.subscriber_count,
                    age_days=excluded.age_days,
                    primary_format=excluded.primary_format,
                    classification_confidence=excluded.classification_confidence,
                    learning_value=excluded.learning_value,
                    novelty_score=excluded.novelty_score,
                    recreation_score=excluded.recreation_score,
                    reasons_json=excluded.reasons_json,
                    last_seen=excluded.last_seen
                """,
                (
                    item["video_id"],
                    item["title"],
                    item["url"],
                    item["channel_title"],
                    item["view_count"],
                    item["subscriber_count"],
                    item["age_days"],
                    item["primary_format"],
                    item["classification_confidence"],
                    item["learning_value"],
                    item["novelty_score"],
                    item["recreation_score"],
                    status,
                    json.dumps(item["reasons"], ensure_ascii=False),
                    first_seen,
                    now,
                ),
            )
        con.commit()

    return selected


def list_reference_queue(
    status: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with _connect() as con:
        if status:
            rows = con.execute(
                """
                SELECT *
                FROM reference_queue
                WHERE status=?
                ORDER BY learning_value DESC
                LIMIT ?
                """,
                (status, max(1, int(limit))),
            ).fetchall()
        else:
            rows = con.execute(
                """
                SELECT *
                FROM reference_queue
                ORDER BY learning_value DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["reasons"] = json.loads(item.pop("reasons_json"))
        except Exception:
            item["reasons"] = []
        results.append(item)
    return results


def set_reference_status(video_id: str, status: str) -> None:
    allowed = {
        "DISCOVERED",
        "APPROVED",
        "MEDIA_NEEDED",
        "METADATA_ANALYZED",
        "FULLY_ANALYZED",
        "REJECTED",
    }
    normalized = status.strip().upper()
    if normalized not in allowed:
        raise ValueError(
            f"Invalid status {status!r}; expected one of {sorted(allowed)}"
        )

    with _connect() as con:
        con.execute(
            """
            UPDATE reference_queue
            SET status=?, last_seen=?
            WHERE video_id=?
            """,
            (normalized, _now(), video_id),
        )
        con.commit()
