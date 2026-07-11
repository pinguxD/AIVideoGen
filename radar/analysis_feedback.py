from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE

DB_PATH = BASE / "outputs" / "analysis_feedback.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_corrections (
    source_key TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    original_format TEXT DEFAULT '',
    corrected_format TEXT DEFAULT '',
    hook_type TEXT DEFAULT '',
    video_goal TEXT DEFAULT '',
    emotion TEXT DEFAULT '',
    ending_type TEXT DEFAULT '',
    voice_type TEXT DEFAULT '',
    voice_style TEXT DEFAULT '',
    caption_style TEXT DEFAULT '',
    meme_usage TEXT DEFAULT '',
    sound_usage TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS timeline_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    start_time REAL DEFAULT 0,
    end_time REAL DEFAULT 0,
    event_type TEXT NOT NULL,
    label TEXT DEFAULT '',
    is_correct INTEGER DEFAULT 1,
    notes TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_timeline_corrections_source
ON timeline_corrections(source_key);

CREATE TABLE IF NOT EXISTS analysis_learning_stats (
    label_group TEXT NOT NULL,
    label_value TEXT NOT NULL,
    accepted_count INTEGER DEFAULT 0,
    corrected_count INTEGER DEFAULT 0,
    PRIMARY KEY(label_group, label_value)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMA)
    con.commit()
    return con


def save_analysis_correction(
    source_key: str,
    source_name: str,
    original_format: str = "",
    corrected_format: str = "",
    hook_type: str = "",
    video_goal: str = "",
    emotion: str = "",
    ending_type: str = "",
    voice_type: str = "",
    voice_style: str = "",
    caption_style: str = "",
    meme_usage: str = "",
    sound_usage: str = "",
    notes: str = "",
) -> None:
    now = _now()
    with _connect() as con:
        existing = con.execute(
            "SELECT created_at FROM analysis_corrections WHERE source_key=?",
            (source_key,),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else now

        con.execute(
            """
            INSERT INTO analysis_corrections (
                source_key, source_name, original_format, corrected_format,
                hook_type, video_goal, emotion, ending_type,
                voice_type, voice_style, caption_style,
                meme_usage, sound_usage, notes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                source_name=excluded.source_name,
                original_format=excluded.original_format,
                corrected_format=excluded.corrected_format,
                hook_type=excluded.hook_type,
                video_goal=excluded.video_goal,
                emotion=excluded.emotion,
                ending_type=excluded.ending_type,
                voice_type=excluded.voice_type,
                voice_style=excluded.voice_style,
                caption_style=excluded.caption_style,
                meme_usage=excluded.meme_usage,
                sound_usage=excluded.sound_usage,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                source_key,
                source_name,
                original_format,
                corrected_format,
                hook_type,
                video_goal,
                emotion,
                ending_type,
                voice_type,
                voice_style,
                caption_style,
                meme_usage,
                sound_usage,
                notes,
                created_at,
                now,
            ),
        )
        con.commit()

    rebuild_learning_stats()


def get_analysis_correction(source_key: str) -> dict[str, Any] | None:
    with _connect() as con:
        row = con.execute(
            "SELECT * FROM analysis_corrections WHERE source_key=?",
            (source_key,),
        ).fetchone()
    return dict(row) if row else None


def list_analysis_corrections(limit: int = 1000) -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT *
            FROM analysis_corrections
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [dict(row) for row in rows]


def add_timeline_correction(
    source_key: str,
    start_time: float,
    end_time: float,
    event_type: str,
    label: str = "",
    is_correct: bool = True,
    notes: str = "",
) -> int:
    with _connect() as con:
        cursor = con.execute(
            """
            INSERT INTO timeline_corrections (
                source_key, start_time, end_time, event_type,
                label, is_correct, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_key,
                float(start_time),
                float(end_time),
                event_type,
                label,
                1 if is_correct else 0,
                notes,
                _now(),
            ),
        )
        con.commit()
        return int(cursor.lastrowid)


def delete_timeline_correction(correction_id: int) -> None:
    with _connect() as con:
        con.execute(
            "DELETE FROM timeline_corrections WHERE id=?",
            (int(correction_id),),
        )
        con.commit()


def list_timeline_corrections(source_key: str) -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT *
            FROM timeline_corrections
            WHERE source_key=?
            ORDER BY start_time, id
            """,
            (source_key,),
        ).fetchall()
    return [dict(row) for row in rows]


def rebuild_learning_stats() -> None:
    rows = list_analysis_corrections()
    groups = {
        "format": "corrected_format",
        "hook": "hook_type",
        "goal": "video_goal",
        "emotion": "emotion",
        "ending": "ending_type",
        "voice_type": "voice_type",
        "voice_style": "voice_style",
        "caption_style": "caption_style",
        "meme_usage": "meme_usage",
        "sound_usage": "sound_usage",
    }

    counters: dict[tuple[str, str], int] = {}
    for row in rows:
        for group, field in groups.items():
            value = str(row.get(field) or "").strip()
            if value:
                counters[(group, value)] = counters.get((group, value), 0) + 1

    with _connect() as con:
        con.execute("DELETE FROM analysis_learning_stats")
        for (group, value), count in counters.items():
            con.execute(
                """
                INSERT INTO analysis_learning_stats (
                    label_group, label_value, accepted_count, corrected_count
                )
                VALUES (?, ?, ?, ?)
                """,
                (group, value, count, count),
            )
        con.commit()


def get_learning_stats() -> list[dict[str, Any]]:
    with _connect() as con:
        rows = con.execute(
            """
            SELECT *
            FROM analysis_learning_stats
            ORDER BY label_group, corrected_count DESC, label_value
            """
        ).fetchall()
    return [dict(row) for row in rows]
