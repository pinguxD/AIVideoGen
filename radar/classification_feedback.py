from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
DB_PATH = BASE / "outputs" / "video_classification.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS classification_feedback (
    video_id TEXT PRIMARY KEY,
    ai_label TEXT,
    correct_label TEXT NOT NULL,
    content_type TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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


def save_feedback(
    video_id: str,
    ai_label: str,
    correct_label: str,
    content_type: str = "",
    reason: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as con:
        con.execute(
            """
            INSERT INTO classification_feedback (
                video_id, ai_label, correct_label, content_type,
                reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                ai_label=excluded.ai_label,
                correct_label=excluded.correct_label,
                content_type=excluded.content_type,
                reason=excluded.reason,
                updated_at=excluded.updated_at
            """,
            (
                video_id,
                ai_label,
                correct_label,
                content_type,
                reason,
                now,
                now,
            ),
        )
        con.commit()


def get_feedback_for_video(video_id: str) -> dict[str, Any] | None:
    with _connect() as con:
        row = con.execute(
            "SELECT * FROM classification_feedback WHERE video_id=?",
            (video_id,),
        ).fetchone()
    return dict(row) if row else None


def list_feedback() -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            "SELECT * FROM classification_feedback ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_label_priors() -> dict[str, float]:
    """Small calibration priors learned from your corrections."""
    priors: dict[str, float] = {}
    for row in list_feedback():
        correct = str(row.get("correct_label") or "")
        ai_label = str(row.get("ai_label") or "")
        if correct:
            priors[correct] = priors.get(correct, 0.0) + 0.12
        if ai_label and ai_label != correct:
            priors[ai_label] = priors.get(ai_label, 0.0) - 0.08
    return {
        key: max(-0.75, min(0.75, value))
        for key, value in priors.items()
    }
