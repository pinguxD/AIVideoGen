from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE / ".env")

SOUND_DIR = BASE / "assets" / "sounds"
INDEX_PATH = SOUND_DIR / "sound_index.csv"
PREF_PATH = SOUND_DIR / "sound_preferences.json"
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}


@dataclass
class SoundAsset:
    asset_id: str
    query: str
    name: str
    file: str
    source: str
    source_url: str
    creator: str
    license: str
    duration: float
    tags: str
    risk: str


def ensure_dirs() -> None:
    SOUND_DIR.mkdir(parents=True, exist_ok=True)


def _slug(text: str, max_len: int = 80) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")
    return value[:max_len] or "sound"


def _risk_for_license(license_url: str) -> str:
    low = (license_url or "").lower()
    if "publicdomain" in low or "cc0" in low:
        return "LOW"
    if "/by/" in low:
        return "LOW_ATTRIBUTION_REQUIRED"
    if "/by-nc/" in low or "noncommercial" in low:
        return "HIGH_NOT_FOR_MONETIZED_USE"
    return "MEDIUM_MANUAL_REVIEW"


def load_preferences() -> dict[str, dict]:
    ensure_dirs()
    if not PREF_PATH.exists():
        return {}
    try:
        data = json.loads(PREF_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_preferences(data: dict[str, dict]) -> None:
    ensure_dirs()
    PREF_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def update_sound_feedback(asset_id: str, action: str, context: str = "general") -> dict:
    prefs = load_preferences()
    item = prefs.setdefault(asset_id, {
        "rating": 0,
        "blocked": False,
        "approved": 0,
        "rejected": 0,
        "contexts_good": {},
        "contexts_bad": {},
    })
    if action == "good":
        item["rating"] = min(5, max(1, int(item.get("rating", 0)) + 1))
        item["approved"] = int(item.get("approved", 0)) + 1
        item["contexts_good"][context] = int(item["contexts_good"].get(context, 0)) + 1
    elif action == "bad":
        item["rating"] = max(-5, int(item.get("rating", 0)) - 1)
        item["rejected"] = int(item.get("rejected", 0)) + 1
        item["contexts_bad"][context] = int(item["contexts_bad"].get(context, 0)) + 1
    elif action == "never":
        item["blocked"] = True
        item["rating"] = -5
        item["rejected"] = int(item.get("rejected", 0)) + 1
    elif action == "unblock":
        item["blocked"] = False
    save_preferences(prefs)
    return item


def preference_for(asset_id: str) -> dict:
    return load_preferences().get(asset_id, {})


def load_index() -> list[SoundAsset]:
    ensure_dirs()
    out: list[SoundAsset] = []
    if INDEX_PATH.exists():
        with INDEX_PATH.open("r", newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                try:
                    row["duration"] = float(row.get("duration") or 0)
                    out.append(SoundAsset(**row))
                except Exception:
                    continue
    known = {Path(x.file).name.lower() for x in out}
    changed = False
    for path in local_audio_files():
        if path.name.lower() in known:
            continue
        item = SoundAsset(
            asset_id=f"local_{_slug(path.stem, 60)}",
            query=path.stem.replace("_", " "),
            name=path.stem,
            file=str(path.relative_to(BASE)).replace("\\", "/"),
            source="Local / user supplied",
            source_url="",
            creator="",
            license="Unknown — review before monetized use",
            duration=0.0,
            tags=path.stem.replace("_", ","),
            risk="MEDIUM_MANUAL_REVIEW",
        )
        out.append(item)
        known.add(path.name.lower())
        changed = True
    if changed:
        save_index(out)
    return out


def save_index(items: Iterable[SoundAsset]) -> None:
    ensure_dirs()
    rows = [asdict(x) for x in items]
    fields = list(SoundAsset.__annotations__.keys())
    with INDEX_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def local_audio_files() -> list[Path]:
    ensure_dirs()
    return [p for p in SOUND_DIR.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXT]


def _candidate_score(item: SoundAsset, query: str, context: str = "guess_voice") -> float:
    prefs = preference_for(item.asset_id)
    if prefs.get("blocked"):
        return -9999
    words = {w.lower() for w in re.findall(r"[a-zA-Z0-9]+", query)}
    hay = f"{item.query} {item.name} {item.tags}".lower()
    lexical = sum(5 for word in words if word in hay)
    duration = float(item.duration or 0)
    duration_fit = 10 if 0.35 <= duration <= 2.2 else 4 if duration <= 3.5 else -6
    risk_score = 8 if item.risk == "LOW" else 5 if item.risk == "LOW_ATTRIBUTION_REQUIRED" else -2
    personal = int(prefs.get("rating", 0)) * 9
    personal += int(prefs.get("contexts_good", {}).get(context, 0)) * 5
    personal -= int(prefs.get("contexts_bad", {}).get(context, 0)) * 7
    return lexical + duration_fit + risk_score + personal


def rank_sound_candidates(items: Iterable[SoundAsset], query: str, context: str = "guess_voice") -> list[SoundAsset]:
    return sorted(items, key=lambda x: _candidate_score(x, query, context), reverse=True)


def search_local(query: str, limit: int = 10, context: str = "guess_voice") -> list[SoundAsset]:
    ranked = rank_sound_candidates(load_index(), query, context)
    return [x for x in ranked if _candidate_score(x, query, context) > -999][:limit]


def search_freesound(query: str, limit: int = 8, max_duration: float = 8.0) -> list[dict]:
    token = os.getenv("FREESOUND_API_KEY", "").strip()
    if not token:
        raise RuntimeError("FREESOUND_API_KEY is missing from .env")
    params = {
        "query": query,
        "token": token,
        "page_size": min(max(limit, 1), 50),
        "fields": "id,name,previews,license,username,url,duration,tags,description",
        "filter": f"duration:[0.1 TO {max_duration}]",
        "sort": "rating_desc",
    }
    response = requests.get("https://freesound.org/apiv2/search/", params=params, timeout=30)
    response.raise_for_status()
    return list(response.json().get("results", []))


def download_freesound(query: str, count: int = 4, max_duration: float = 8.0) -> list[SoundAsset]:
    ensure_dirs()
    existing = load_index()
    existing_ids = {x.asset_id for x in existing}
    downloaded: list[SoundAsset] = []
    for result in search_freesound(query, limit=max(count * 5, 12), max_duration=max_duration):
        if len(downloaded) >= count:
            break
        asset_id = f"freesound_{result.get('id')}"
        if asset_id in existing_ids:
            item = next((x for x in existing if x.asset_id == asset_id), None)
            if item and not preference_for(item.asset_id).get("blocked"):
                downloaded.append(item)
            continue
        previews = result.get("previews") or {}
        preview_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3") or previews.get("preview-hq-ogg")
        if not preview_url:
            continue
        license_url = str(result.get("license") or "")
        risk = _risk_for_license(license_url)
        if risk == "HIGH_NOT_FOR_MONETIZED_USE":
            continue
        ext = ".ogg" if "ogg" in preview_url.lower() else ".mp3"
        filename = f"{_slug(query)}__{result.get('id')}__{_slug(str(result.get('name') or 'sound'), 45)}{ext}"
        target = SOUND_DIR / filename
        audio = requests.get(preview_url, timeout=45)
        audio.raise_for_status()
        target.write_bytes(audio.content)
        item = SoundAsset(
            asset_id=asset_id,
            query=query,
            name=str(result.get("name") or filename),
            file=str(target.relative_to(BASE)).replace("\\", "/"),
            source="Freesound",
            source_url=str(result.get("url") or ""),
            creator=str(result.get("username") or ""),
            license=license_url,
            duration=float(result.get("duration") or 0),
            tags=",".join(result.get("tags") or []),
            risk=risk,
        )
        existing.append(item)
        existing_ids.add(asset_id)
        downloaded.append(item)
    save_index(existing)
    return downloaded


def attribution_text(items: Iterable[SoundAsset]) -> str:
    return "\n".join(f"{x.name} — {x.creator} — {x.license} — {x.source_url}" for x in items)


def _dedupe_assets(items: Iterable[SoundAsset]) -> list[SoundAsset]:
    unique: list[SoundAsset] = []
    seen_files: set[str] = set()
    seen_ids: set[str] = set()
    for item in items:
        file_key = str(Path(item.file)).lower()
        if item.asset_id in seen_ids or file_key in seen_files:
            continue
        if preference_for(item.asset_id).get("blocked"):
            continue
        seen_ids.add(item.asset_id)
        seen_files.add(file_key)
        unique.append(item)
    return unique


def search_local_unique(queries: list[str], required_total: int, exclude_ids: set[str] | None = None) -> tuple[list[SoundAsset], list[str]]:
    selected: list[SoundAsset] = []
    unresolved: list[str] = []
    exclude_ids = exclude_ids or set()
    for query in queries:
        candidates = [x for x in search_local(query, limit=30) if x.risk != "HIGH_NOT_FOR_MONETIZED_USE" and x.asset_id not in exclude_ids]
        before = len(selected)
        selected = _dedupe_assets([*selected, *candidates])
        if len(selected) == before:
            unresolved.append(query)
        if len(selected) >= required_total:
            break
    return selected[:required_total], unresolved


def ensure_unique_sounds(queries: list[str], required_total: int = 4, exclude_ids: set[str] | None = None) -> tuple[list[SoundAsset], list[str]]:
    exclude_ids = exclude_ids or set()
    selected, unresolved = search_local_unique(queries, required_total, exclude_ids)
    if len(selected) >= required_total:
        return selected[:required_total], []
    fallback_queries = [
        *queries,
        "viral meme scream short",
        "funny distorted yell short",
        "cartoon scream short",
        "monster roar short",
        "goofy shout short",
        "panic scream short",
        "funny creature noise short",
        "absurd meme yell short",
    ]
    errors: list[str] = []
    for query in fallback_queries:
        if len(selected) >= required_total:
            break
        try:
            fresh = download_freesound(query, count=max(6, required_total - len(selected)), max_duration=3.0)
            fresh = [x for x in fresh if x.asset_id not in exclude_ids]
            selected = _dedupe_assets([*selected, *rank_sound_candidates(fresh, query)])
        except Exception as exc:
            message = f"{query}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(f"[Sound AI] {message}")
    selected = selected[:required_total]
    if len(selected) < required_total:
        unresolved = [f"need {required_total - len(selected)} additional unique sounds"]
        if errors:
            unresolved.append("sound search errors were printed in the terminal")
    else:
        unresolved = []
    return selected, unresolved


def find_replacement_sound(query: str, excluded_asset_ids: set[str], context: str = "guess_voice") -> SoundAsset | None:
    local, _ = search_local_unique([query], 1, excluded_asset_ids)
    if local:
        return local[0]
    try:
        fresh = download_freesound(query, count=8, max_duration=3.0)
        ranked = [x for x in rank_sound_candidates(fresh, query, context) if x.asset_id not in excluded_asset_ids and not preference_for(x.asset_id).get("blocked")]
        return ranked[0] if ranked else None
    except Exception as exc:
        print(f"[Sound AI] replacement failed for '{query}': {exc}")
        return None
