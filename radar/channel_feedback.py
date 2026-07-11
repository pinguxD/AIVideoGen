from __future__ import annotations

import csv
import json
import math
import os
import sqlite3
import statistics
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE / ".env")

OUTPUTS = BASE / "outputs"
DB_PATH = OUTPUTS / "channel_feedback.db"
CSV_PATH = OUTPUTS / "channel_performance.csv"
LEARNING_PATH = OUTPUTS / "channel_learning.json"
CHANNEL_ID_CACHE = OUTPUTS / "my_channel_id.txt"
PROJECT_DIR = OUTPUTS / "creator_projects"

DEFAULT_HANDLE = os.getenv("MY_CHANNEL_HANDLE", "@arnovcs-v2m").strip() or "@arnovcs-v2m"
DEFAULT_CHANNEL_ID = os.getenv("MY_CHANNEL_ID", "").strip()
SYNC_HOURS = max(1, int(os.getenv("CHANNEL_SYNC_HOURS", "6")))
MAX_UPLOADS = max(10, min(500, int(os.getenv("CHANNEL_MAX_UPLOADS", "100"))))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS channel_videos (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT,
    duration_seconds INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    views_per_hour REAL DEFAULT 0,
    like_rate REAL DEFAULT 0,
    comment_rate REAL DEFAULT 0,
    template_type TEXT,
    hook_type TEXT,
    matched_project_id TEXT,
    project_match_confidence REAL DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT
);
CREATE TABLE IF NOT EXISTS channel_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _connect() -> sqlite3.Connection:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(_SCHEMA)
    con.commit()
    return con


def _parse_iso_duration(value: str) -> int:
    try:
        import isodate
        return int(isodate.parse_duration(value).total_seconds())
    except Exception:
        return 0


def _parse_published(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def classify_template(title: str) -> str:
    low = str(title or "").lower()
    if "guess" in low and any(x in low for x in ("voice", "sound", "scream", "real one")):
        return "guess_voice"
    if any(x in low for x in ("scream", "sound replacement", "sounds like", "voice leaked")):
        return "sound_replacement"
    if any(x in low for x in ("fact", "secret", "did you know", "most players", "99%", "only og", "older than")):
        return "fact_card"
    if any(x in low for x in ("how to", "guide", "beat", "tutorial")):
        return "guide"
    if any(x in low for x in ("pov", "when you", "bro", "me when")):
        return "meme"
    return "other"


def classify_hook(title: str) -> str:
    low = str(title or "").lower().strip()
    if low.startswith("guess") or "guess the" in low:
        return "guess"
    if any(x in low for x in ("don't", "never", "warning", "one click")):
        return "threat"
    if any(x in low for x in ("99%", "most players", "only 1%", "everyone")):
        return "challenge_claim"
    if any(x in low for x in ("secret", "hidden", "nobody", "you won't believe", "wait")):
        return "curiosity"
    if any(x in low for x in ("oldest", "older than", "first ever", "og")):
        return "nostalgia"
    if low.startswith("how to") or "tutorial" in low:
        return "utility"
    return "other"


def _project_titles() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if not PROJECT_DIR.exists():
        return rows
    for path in PROJECT_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            title = str(data.get("final_title") or data.get("inspiration_title") or "").strip()
            if title:
                rows.append((path.stem, title))
        except Exception:
            continue
    return rows


def _match_project(title: str) -> tuple[str, float]:
    best_id, best_score = "", 0.0
    title_low = title.lower().strip()
    for project_id, candidate in _project_titles():
        score = SequenceMatcher(None, title_low, candidate.lower().strip()).ratio()
        if score > best_score:
            best_id, best_score = project_id, score
    return (best_id, round(best_score, 3)) if best_score >= 0.55 else ("", round(best_score, 3))


def _resolve_channel_id(youtube) -> str:
    if DEFAULT_CHANNEL_ID:
        return DEFAULT_CHANNEL_ID
    if CHANNEL_ID_CACHE.exists():
        cached = CHANNEL_ID_CACHE.read_text(encoding="utf-8").strip()
        if cached:
            return cached

    handle = DEFAULT_HANDLE.lstrip("@").strip()
    try:
        res = youtube.channels().list(part="id,snippet", forHandle=handle).execute()
        items = res.get("items", [])
        if items:
            channel_id = items[0]["id"]
            CHANNEL_ID_CACHE.write_text(channel_id, encoding="utf-8")
            return channel_id
    except Exception as exc:
        print(f"[Channel Feedback] forHandle lookup failed: {exc}")

    res = youtube.search().list(part="snippet", q=DEFAULT_HANDLE, type="channel", maxResults=10).execute()
    items = res.get("items", [])
    if not items:
        raise RuntimeError(f"Could not resolve YouTube channel for {DEFAULT_HANDLE}")
    exact = next(
        (x for x in items if str(x.get("snippet", {}).get("customUrl", "")).lower().endswith(handle.lower())),
        items[0],
    )
    channel_id = exact["snippet"]["channelId"]
    CHANNEL_ID_CACHE.write_text(channel_id, encoding="utf-8")
    return channel_id


def _upload_ids(youtube, uploads_playlist: str, limit: int) -> list[str]:
    ids: list[str] = []
    token = None
    while len(ids) < limit:
        res = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist,
            maxResults=min(50, limit - len(ids)),
            pageToken=token,
        ).execute()
        ids.extend(
            str(x.get("contentDetails", {}).get("videoId", ""))
            for x in res.get("items", [])
            if x.get("contentDetails", {}).get("videoId")
        )
        token = res.get("nextPageToken")
        if not token:
            break
    return ids[:limit]


def _video_details(youtube, ids: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for start in range(0, len(ids), 50):
        res = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(ids[start:start + 50]),
        ).execute()
        items.extend(res.get("items", []))
    return items


def _write_learning(con: sqlite3.Connection) -> dict[str, Any]:
    videos = [dict(row) for row in con.execute("SELECT * FROM channel_videos").fetchall()]
    if not videos:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "templates": {}, "hooks": {}, "baseline": {}}
        LEARNING_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    view_values = [max(1, int(v["view_count"] or 0)) for v in videos]
    velocity_values = [max(0.0, float(v["views_per_hour"] or 0)) for v in videos]
    median_views = statistics.median(view_values)
    median_velocity = statistics.median(velocity_values) or 1.0

    def aggregate(key: str) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in videos:
            grouped.setdefault(str(row.get(key) or "other"), []).append(row)
        out: dict[str, Any] = {}
        for name, rows in grouped.items():
            avg_views = sum(float(r["view_count"] or 0) for r in rows) / len(rows)
            avg_velocity = sum(float(r["views_per_hour"] or 0) for r in rows) / len(rows)
            avg_like = sum(float(r["like_rate"] or 0) for r in rows) / len(rows)
            avg_comment = sum(float(r["comment_rate"] or 0) for r in rows) / len(rows)
            # Blend total performance and early velocity, with sample-size shrinkage.
            raw = 0.55 * (avg_views / max(median_views, 1)) + 0.45 * (avg_velocity / max(median_velocity, 1))
            confidence = min(1.0, len(rows) / 8.0)
            multiplier = 1.0 + (max(0.6, min(1.6, raw)) - 1.0) * confidence
            out[name] = {
                "videos": len(rows),
                "avg_views": round(avg_views, 1),
                "avg_views_per_hour": round(avg_velocity, 2),
                "avg_like_rate": round(avg_like, 5),
                "avg_comment_rate": round(avg_comment, 5),
                "personal_multiplier": round(max(0.75, min(1.35, multiplier)), 3),
            }
        return out

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": {
            "videos": len(videos),
            "median_views": round(float(median_views), 1),
            "median_views_per_hour": round(float(median_velocity), 2),
        },
        "templates": aggregate("template_type"),
        "hooks": aggregate("hook_type"),
    }
    LEARNING_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def sync_channel_performance() -> dict[str, Any]:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing YOUTUBE_API_KEY in .env")
    youtube = build("youtube", "v3", developerKey=key, cache_discovery=False)
    channel_id = _resolve_channel_id(youtube)
    channel = youtube.channels().list(part="snippet,statistics,contentDetails", id=channel_id).execute().get("items", [])
    if not channel:
        raise RuntimeError(f"Channel not found: {channel_id}")
    channel_data = channel[0]
    uploads = channel_data["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = _upload_ids(youtube, uploads, MAX_UPLOADS)
    details = _video_details(youtube, ids)
    now = datetime.now(timezone.utc)

    con = _connect()
    try:
        existing_first = {
            row["video_id"]: row["first_seen"]
            for row in con.execute("SELECT video_id, first_seen FROM channel_videos").fetchall()
        }
        output_rows: list[dict[str, Any]] = []
        for item in details:
            video_id = str(item.get("id") or "")
            sn = item.get("snippet", {})
            st = item.get("statistics", {})
            title = str(sn.get("title") or "")
            published = str(sn.get("publishedAt") or "")
            hours = max(0.25, (now - _parse_published(published)).total_seconds() / 3600.0)
            views = int(st.get("viewCount", 0) or 0)
            likes = int(st.get("likeCount", 0) or 0)
            comments = int(st.get("commentCount", 0) or 0)
            template = classify_template(title)
            hook = classify_hook(title)
            project_id, match_conf = _match_project(title)
            first_seen = existing_first.get(video_id) or now.isoformat(timespec="seconds")
            row = {
                "video_id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": published,
                "duration_seconds": _parse_iso_duration(str(item.get("contentDetails", {}).get("duration", ""))),
                "view_count": views,
                "like_count": likes,
                "comment_count": comments,
                "views_per_hour": round(views / hours, 3),
                "like_rate": round(likes / max(views, 1), 6),
                "comment_rate": round(comments / max(views, 1), 6),
                "template_type": template,
                "hook_type": hook,
                "matched_project_id": project_id,
                "project_match_confidence": match_conf,
                "first_seen": first_seen,
                "last_seen": now.isoformat(timespec="seconds"),
            }
            columns = list(row)
            placeholders = ",".join("?" for _ in columns)
            updates = ",".join(f"{c}=excluded.{c}" for c in columns if c not in {"video_id", "first_seen"})
            con.execute(
                f"INSERT INTO channel_videos ({','.join(columns)}) VALUES ({placeholders}) "
                f"ON CONFLICT(video_id) DO UPDATE SET {updates}",
                [row[c] for c in columns],
            )
            con.execute(
                "INSERT INTO channel_snapshots(video_id, scanned_at, view_count, like_count, comment_count) VALUES (?,?,?,?,?)",
                (video_id, now.isoformat(timespec="seconds"), views, likes, comments),
            )
            output_rows.append(row)

        con.execute("INSERT OR REPLACE INTO sync_state(key,value) VALUES('last_sync',?)", (now.isoformat(timespec="seconds"),))
        con.execute("INSERT OR REPLACE INTO sync_state(key,value) VALUES('channel_id',?)", (channel_id,))
        con.commit()
        learning = _write_learning(con)
    finally:
        con.close()

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if output_rows:
        with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(output_rows[0]))
            writer.writeheader()
            writer.writerows(output_rows)

    return {
        "channel_id": channel_id,
        "channel_title": str(channel_data.get("snippet", {}).get("title", "")),
        "subscriber_count": int(channel_data.get("statistics", {}).get("subscriberCount", 0) or 0),
        "video_count": len(output_rows),
        "learning": learning,
        "synced_at": now.isoformat(timespec="seconds"),
    }


def load_channel_rows(limit: int = 100) -> list[dict[str, Any]]:
    con = _connect()
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM channel_videos ORDER BY published_at DESC LIMIT ?", (limit,)
        ).fetchall()]
    finally:
        con.close()


def load_learning() -> dict[str, Any]:
    if not LEARNING_PATH.exists():
        return {"templates": {}, "hooks": {}, "baseline": {}}
    try:
        return json.loads(LEARNING_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"templates": {}, "hooks": {}, "baseline": {}}


def personal_multiplier(template_type: str, hook_type: str = "") -> float:
    data = load_learning()
    template = float(data.get("templates", {}).get(template_type, {}).get("personal_multiplier", 1.0))
    hook = float(data.get("hooks", {}).get(hook_type, {}).get("personal_multiplier", 1.0)) if hook_type else 1.0
    return max(0.75, min(1.35, 0.7 * template + 0.3 * hook))


def last_sync_age_hours() -> float | None:
    con = _connect()
    try:
        row = con.execute("SELECT value FROM sync_state WHERE key='last_sync'").fetchone()
    finally:
        con.close()
    if not row:
        return None
    try:
        dt = datetime.fromisoformat(str(row[0]))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except Exception:
        return None


def sync_if_stale(force: bool = False) -> dict[str, Any] | None:
    age = last_sync_age_hours()
    if not force and age is not None and age < SYNC_HOURS:
        return None
    return sync_channel_performance()


def start_background_sync() -> threading.Thread:
    def worker() -> None:
        # Small delay so Flask can finish starting first.
        time.sleep(2)
        while True:
            try:
                result = sync_if_stale()
                if result:
                    print(f"[Channel Feedback] Synced {result['video_count']} uploads for {result['channel_title']}")
            except Exception as exc:
                print(f"[Channel Feedback] Sync failed: {type(exc).__name__}: {exc}")
            time.sleep(SYNC_HOURS * 3600)

    thread = threading.Thread(target=worker, name="channel-feedback-sync", daemon=True)
    thread.start()
    return thread
