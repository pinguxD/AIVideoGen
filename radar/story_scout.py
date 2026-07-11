from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import CONFIG
from .full_video_analyzer import BASE
from .youtube_client import YouTubeClient

OUTPUT_DIR = BASE / "outputs" / "story_scout"
DATABASE_PATH = OUTPUT_DIR / "story_candidates.json"
IMPORT_DIR = BASE / "assets" / "story_references" / "pending"

DEFAULT_QUERIES = [
    "minecraft parkour storytime shorts english",
    "minecraft reddit story shorts english",
    "roblox storytime shorts english",
    "roblox reddit story gameplay shorts english",
    "minecraft gameplay confession story shorts",
    "roblox gameplay story shorts",
]

STORY_TERMS = {
    "story",
    "storytime",
    "reddit",
    "confession",
    "secret",
    "mistake",
    "worst",
    "crazy",
    "never",
    "finally",
    "found",
    "discovered",
    "happened",
    "realized",
    "friend",
    "school",
    "teacher",
    "girlfriend",
    "boyfriend",
    "parents",
    "brother",
    "sister",
    "part 1",
    "part 2",
    "pov",
}

GAMING_TERMS = {
    "minecraft",
    "minecraft parkour",
    "minecraft gameplay",
    "roblox",
    "roblox gameplay",
    "roblox obby",
    "obby",
}


@dataclass
class StoryCandidate:
    video_id: str
    title: str
    description: str
    url: str
    channel_id: str
    channel_title: str
    published_at: str
    age_days: float
    duration_seconds: int
    view_count: int
    like_count: int
    comment_count: int
    subscriber_count: int
    views_per_day: int
    engagement_rate: float
    views_to_subs: float
    storytelling_score: int
    gaming_background_score: int
    english_confidence: int
    detected_game: str
    viral_score: int
    opportunity_score: int
    matched_query: str
    reasons: list[str]
    status: str = "NEW"
    reviewed_at: float | None = None
    imported_path: str = ""
    notes: str = ""

    @property
    def thumbnail_url(self) -> str:
        return f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg"


def _load_rows() -> list[dict[str, Any]]:
    if not DATABASE_PATH.exists():
        return []
    try:
        value = json.loads(DATABASE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_rows(rows: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _normalize_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    """Load old Story Scout records without breaking the v1.1 page."""
    normalized = dict(row)

    title = str(normalized.get("title") or "")
    description = str(normalized.get("description") or "")
    query = str(normalized.get("matched_query") or "")

    normalized.setdefault(
        "english_confidence",
        _english_confidence(f"{title} {description}"),
    )

    if "detected_game" not in normalized:
        _, detected_game = _is_roblox_or_minecraft(
            f"{title} {description} {query}"
        )
        normalized["detected_game"] = detected_game

    defaults = {
        "description": "",
        "url": "",
        "channel_id": "",
        "channel_title": "",
        "published_at": "",
        "age_days": 0.05,
        "duration_seconds": 0,
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
        "subscriber_count": 0,
        "views_per_day": 0,
        "engagement_rate": 0.0,
        "views_to_subs": 0.0,
        "storytelling_score": 0,
        "gaming_background_score": 0,
        "viral_score": 0,
        "opportunity_score": 0,
        "matched_query": "",
        "reasons": [],
        "status": "NEW",
        "reviewed_at": None,
        "imported_path": "",
        "notes": "",
    }
    for key, value in defaults.items():
        normalized.setdefault(key, value)

    allowed = set(StoryCandidate.__dataclass_fields__)
    return {
        key: value
        for key, value in normalized.items()
        if key in allowed
    }


def list_candidates(
    status: str = "",
    limit: int = 300,
) -> list[StoryCandidate]:
    rows = [_normalize_candidate_row(row) for row in _load_rows()]
    candidates = [StoryCandidate(**row) for row in rows]
    if status:
        candidates = [
            item
            for item in candidates
            if item.status == status
        ]
    candidates.sort(
        key=lambda item: (
            item.status == "APPROVED",
            item.opportunity_score,
            item.view_count,
        ),
        reverse=True,
    )
    return candidates[: max(1, int(limit))]



ENGLISH_STOPWORDS = {
    "the", "and", "that", "this", "was", "were", "with", "from", "when",
    "what", "why", "how", "then", "but", "because", "they", "their", "there",
    "you", "your", "his", "her", "him", "she", "he", "my", "me", "we", "our",
    "story", "storytime", "shorts", "gameplay", "minecraft", "roblox", "reddit",
}

NON_ENGLISH_MARKERS = {
    "historia", "historias", "juego", "jugando", "mientras", "porque", "cuando",
    "pero", "esto", "esta", "como", "para", "parte",
    "histoire", "jeu", "joueur", "quand", "pourquoi", "avec", "mais",
    "geschichte", "spiel", "spieler", "warum", "aber", "mit",
    "storia", "gioco", "perché", "quando", "con",
    "história", "jogo", "porque", "quando", "com",
    "рассказ", "история", "игра", "почему",
    "قصه", "قصة", "لعبة",
    "कहानी", "खेल",
    "cerita", "permainan", "kisah",
    "hikaye", "oyun",
    "verhaal", "spel",
}


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", text.lower())


def _english_confidence(text: str) -> int:
    cleaned = str(text or "").strip()
    if not cleaned:
        return 0

    ascii_chars = sum(
        char.isascii() and (char.isalpha() or char.isspace() or char.isdigit())
        for char in cleaned
    )
    visible_chars = sum(not char.isspace() for char in cleaned)
    ascii_ratio = ascii_chars / max(len(cleaned), 1)

    tokens = _word_tokens(cleaned)
    english_hits = sum(token in ENGLISH_STOPWORDS for token in tokens)
    foreign_hits = sum(token in NON_ENGLISH_MARKERS for token in tokens)

    score = 48
    score += int((ascii_ratio - 0.72) * 80)
    score += min(28, english_hits * 7)
    score -= min(45, foreign_hits * 16)

    if visible_chars < 8:
        score -= 15
    if re.search(r"[\u0400-\u052F\u0600-\u06FF\u0900-\u097F\u3040-\u30FF\u4E00-\u9FFF]", cleaned):
        score -= 55

    return max(0, min(100, score))


def _is_roblox_or_minecraft(text: str) -> tuple[bool, str]:
    lowered = str(text or "").lower()

    minecraft_markers = {
        "minecraft",
        "minecraft parkour",
        "minecraft gameplay",
        "mc parkour",
    }
    roblox_markers = {
        "roblox",
        "roblox gameplay",
        "roblox obby",
        "obby",
    }

    if any(marker in lowered for marker in minecraft_markers):
        return True, "minecraft"
    if any(marker in lowered for marker in roblox_markers):
        return True, "roblox"
    return False, ""


def _passes_language_and_game_filter(
    title: str,
    description: str,
    query: str,
) -> tuple[bool, int, str]:
    combined = f"{title} {description}".strip()
    english_score = _english_confidence(combined)

    game_ok, game = _is_roblox_or_minecraft(
        f"{title} {description} {query}"
    )

    # relevanceLanguage is only a relevance hint, so enforce our own filter.
    if english_score < 62:
        return False, english_score, game
    if not game_ok:
        return False, english_score, game

    return True, english_score, game

def _text_score(text: str, terms: set[str]) -> tuple[int, list[str]]:
    lowered = text.lower()
    matches = sorted(term for term in terms if term in lowered)
    score = min(100, len(matches) * 14)
    return score, matches


def _score_candidate(
    item: dict[str, Any],
    query: str,
) -> StoryCandidate:
    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    combined = f"{title} {description} {query}".lower()

    views = int(item.get("view_count") or 0)
    likes = int(item.get("like_count") or 0)
    comments = int(item.get("comment_count") or 0)
    subscribers = int(item.get("subscriber_count") or 0)
    age_days = max(0.05, float(item.get("age_days") or 0.05))
    duration = int(item.get("duration_seconds") or 0)

    views_per_day = int(round(views / age_days))
    engagement_rate = (
        round((likes + comments * 2) / max(views, 1) * 100, 3)
    )
    views_to_subs = round(views / max(subscribers, 1), 2)

    story_score, story_matches = _text_score(combined, STORY_TERMS)
    gaming_score, gaming_matches = _text_score(combined, GAMING_TERMS)

    # Search-query evidence matters because titles often do not mention the
    # background gameplay itself.
    if any(term in query.lower() for term in GAMING_TERMS):
        gaming_score = min(100, gaming_score + 32)
    if "story" in query.lower() or "reddit" in query.lower():
        story_score = min(100, story_score + 26)

    velocity_component = min(
        100,
        int(round(math.log10(max(views_per_day, 1)) * 22)),
    )
    total_views_component = min(
        100,
        int(round(math.log10(max(views, 1)) * 18)),
    )
    engagement_component = min(
        100,
        int(round(engagement_rate * 14)),
    )
    breakout_component = min(
        100,
        int(round(math.log10(max(views_to_subs, 1)) * 32)),
    )

    viral_score = int(
        round(
            velocity_component * 0.38
            + total_views_component * 0.30
            + engagement_component * 0.20
            + breakout_component * 0.12
        )
    )
    opportunity_score = int(
        round(
            viral_score * 0.50
            + story_score * 0.28
            + gaming_score * 0.22
        )
    )

    reasons = []
    if views_per_day >= 100_000:
        reasons.append(f"{views_per_day:,} views/day")
    elif views_per_day >= 25_000:
        reasons.append(f"Strong velocity: {views_per_day:,}/day")
    if views_to_subs >= 10:
        reasons.append(
            f"Breakout: {views_to_subs:.1f}× channel subscribers"
        )
    if engagement_rate >= 4:
        reasons.append(f"{engagement_rate:.1f}% interaction rate")
    if story_matches:
        reasons.append(
            "Story signals: " + ", ".join(story_matches[:5])
        )
    if gaming_matches:
        reasons.append(
            "Gaming signals: " + ", ".join(gaming_matches[:4])
        )
    if 12 <= duration <= 45:
        reasons.append("Strong Shorts storytelling length")
    elif duration <= 60:
        reasons.append("Short-form duration")

    return StoryCandidate(
        video_id=str(item.get("video_id") or ""),
        title=title,
        description=description,
        url=str(item.get("url") or ""),
        channel_id=str(item.get("channel_id") or ""),
        channel_title=str(item.get("channel_title") or ""),
        published_at=str(item.get("published_at") or ""),
        age_days=round(age_days, 2),
        duration_seconds=duration,
        view_count=views,
        like_count=likes,
        comment_count=comments,
        subscriber_count=subscribers,
        views_per_day=views_per_day,
        engagement_rate=engagement_rate,
        views_to_subs=views_to_subs,
        storytelling_score=story_score,
        gaming_background_score=gaming_score,
        english_confidence=0,
        detected_game="",
        viral_score=viral_score,
        opportunity_score=opportunity_score,
        matched_query=query,
        reasons=reasons,
    )


def scan_storytelling_shorts(
    days_back: int = 30,
    region: str = "US",
    min_views: int = 100_000,
    max_queries: int = 4,
    custom_query: str = "",
) -> list[StoryCandidate]:
    api_key = str(
        os.getenv("YOUTUBE_API_KEY")
        or getattr(CONFIG, "youtube_api_key", "")
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError("Missing YOUTUBE_API_KEY in .env")

    queries = list(DEFAULT_QUERIES)
    if custom_query.strip():
        queries.insert(0, custom_query.strip())
    queries = queries[: max(1, min(6, int(max_queries)))]

    client = YouTubeClient(api_key)
    existing = {
        item.video_id: item
        for item in list_candidates(limit=1000)
    }
    found: dict[str, StoryCandidate] = {}

    for query in queries:
        search_items = client.search(
            q=query,
            days_back=max(1, min(365, int(days_back))),
            max_results=25,
            region=region,
            relevance_language="en",
        )
        videos = client.enrich(search_items)

        for video in videos:
            duration = int(video.get("duration_seconds") or 0)
            views = int(video.get("view_count") or 0)

            # The Data API does not expose a direct isShort flag. We use
            # short-form duration plus the Shorts URL and human review.
            if not 8 <= duration <= 60:
                continue
            if views < min_views:
                continue

            passes_filter, english_score, detected_game = (
                _passes_language_and_game_filter(
                    str(video.get("title") or ""),
                    str(video.get("description") or ""),
                    query,
                )
            )
            if not passes_filter:
                continue

            candidate = _score_candidate(video, query)
            candidate.english_confidence = english_score
            candidate.detected_game = detected_game

            if (
                candidate.storytelling_score < 35
                or candidate.gaming_background_score < 40
            ):
                continue

            prior = existing.get(candidate.video_id)
            if prior:
                candidate.status = prior.status
                candidate.reviewed_at = prior.reviewed_at
                candidate.imported_path = prior.imported_path
                candidate.notes = prior.notes

            current = found.get(candidate.video_id)
            if (
                current is None
                or candidate.opportunity_score > current.opportunity_score
            ):
                found[candidate.video_id] = candidate

    merged = {
        item.video_id: asdict(item)
        for item in existing.values()
    }
    for candidate in found.values():
        merged[candidate.video_id] = asdict(candidate)

    rows = list(merged.values())
    rows.sort(
        key=lambda row: (
            int(row.get("opportunity_score") or 0),
            int(row.get("view_count") or 0),
        ),
        reverse=True,
    )
    _save_rows(rows)
    return list_candidates(limit=300)


def update_status(
    video_id: str,
    status: str,
    notes: str = "",
) -> StoryCandidate:
    allowed = {
        "NEW",
        "APPROVED",
        "REJECTED",
        "DOWNLOADED",
        "IMPORTED",
    }
    if status not in allowed:
        raise ValueError(f"Invalid status: {status}")

    rows = _load_rows()
    for row in rows:
        if str(row.get("video_id")) != video_id:
            continue
        row["status"] = status
        row["reviewed_at"] = time.time()
        if notes:
            row["notes"] = notes
        _save_rows(rows)
        return StoryCandidate(**row)

    raise FileNotFoundError(f"Candidate not found: {video_id}")


def import_downloaded_reference(
    video_id: str,
    uploaded_file: Any,
    notes: str = "",
) -> StoryCandidate:
    filename = str(
        getattr(uploaded_file, "filename", "") or ""
    ).strip()
    extension = Path(filename).suffix.lower()
    if extension not in {".mp4", ".mov", ".mkv", ".webm"}:
        raise ValueError(
            "Upload the downloaded reference as MP4, MOV, MKV or WEBM."
        )

    candidate = next(
        (
            item
            for item in list_candidates(limit=1000)
            if item.video_id == video_id
        ),
        None,
    )
    if candidate is None:
        raise FileNotFoundError(f"Candidate not found: {video_id}")
    if candidate.status not in {"APPROVED", "DOWNLOADED", "IMPORTED"}:
        raise RuntimeError(
            "Approve the reference before importing the downloaded video."
        )

    folder = IMPORT_DIR / video_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"reference{extension}"
    uploaded_file.save(target)

    metadata = {
        "video_id": candidate.video_id,
        "title": candidate.title,
        "channel_title": candidate.channel_title,
        "url": candidate.url,
        "view_count_at_discovery": candidate.view_count,
        "storytelling_score": candidate.storytelling_score,
        "gaming_background_score": candidate.gaming_background_score,
        "viral_score": candidate.viral_score,
        "opportunity_score": candidate.opportunity_score,
        "matched_query": candidate.matched_query,
        "notes": notes,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "local_video_path": str(target),
        "learning_status": "READY_FOR_STORY_ANALYSIS",
    }
    (folder / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rows = _load_rows()
    for row in rows:
        if str(row.get("video_id")) == video_id:
            row["status"] = "IMPORTED"
            row["reviewed_at"] = time.time()
            row["imported_path"] = str(target)
            row["notes"] = notes
            break
    _save_rows(rows)
    return next(
        item
        for item in list_candidates(limit=1000)
        if item.video_id == video_id
    )


def scout_stats() -> dict[str, int]:
    candidates = list_candidates(limit=5000)
    counts = {
        "total": len(candidates),
        "new": 0,
        "approved": 0,
        "rejected": 0,
        "downloaded": 0,
        "imported": 0,
    }
    for item in candidates:
        key = item.status.lower()
        if key in counts:
            counts[key] += 1
    return counts
