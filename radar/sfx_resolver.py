from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .full_video_analyzer import BASE
from .sound_library import download_freesound, load_index

OUTPUT_DIR = BASE / "outputs" / "resolved_sound_effects"

FAMILY_QUERIES = {
    "click_or_ui_tick": [
        "short clean UI click",
        "game menu click short",
        "interface tick short",
    ],
    "pop_or_snap": [
        "short cartoon pop",
        "clean snap sound",
        "small bubble pop short",
    ],
    "bass_hit_or_vine_boom": [
        "deep bass impact short",
        "dramatic bass hit short",
        "low boom meme impact",
    ],
    "riser_or_build_up": [
        "short tension riser",
        "quick cinematic build up",
        "short suspense riser",
    ],
    "whoosh_or_swipe": [
        "fast whoosh transition short",
        "quick swipe whoosh",
        "short motion whoosh",
    ],
    "impact_or_explosion": [
        "short impact hit",
        "cartoon explosion short",
        "dramatic impact sound short",
    ],
    "scream_noise_or_glitch": [
        "short funny scream",
        "short digital glitch",
        "short panic yell",
    ],
    "unknown_effect": [
        "short meme sound effect",
        "short transition sound",
    ],
}


@dataclass
class ResolvedSound:
    event_index: int
    start: float
    end: float
    requested_family: str
    query_used: str
    sound_file: str
    sound_name: str
    creator: str
    license: str
    risk: str
    status: str


def _item_value(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _normalise_file(value: str) -> str:
    path = Path(str(value or ""))
    if not path:
        return ""
    if path.is_absolute():
        try:
            return str(path.relative_to(BASE)).replace("\\", "/")
        except ValueError:
            return str(path)
    return str(path).replace("\\", "/")


def _usable_items(query: str) -> list[Any]:
    lowered = query.lower()
    items = []
    for item in load_index():
        item_query = str(_item_value(item, "query", "")).lower()
        risk = str(_item_value(item, "risk", "")).lower()
        file_value = str(_item_value(item, "file", ""))
        path = Path(file_value)
        if not path.is_absolute():
            path = BASE / path

        if lowered not in item_query and item_query not in lowered:
            continue
        if not path.exists():
            continue
        if risk in {"high", "blocked", "never_use", "never use"}:
            continue
        items.append(item)
    return items


def _find_or_download(query: str, count: int = 4) -> list[Any]:
    existing = _usable_items(query)
    if existing:
        return existing

    download_freesound(query, count=max(1, int(count)))
    return _usable_items(query)


def resolve_sound_events(
    events: list[dict[str, Any]],
    source_name: str,
    options_per_query: int = 4,
) -> tuple[list[ResolvedSound], list[str]]:
    resolved: list[ResolvedSound] = []
    unresolved: list[str] = []
    used_files: set[str] = set()

    for index, event in enumerate(events):
        family = str(
            event.get("family")
            or event.get("effect_type")
            or "unknown_effect"
        )
        queries = FAMILY_QUERIES.get(
            family,
            FAMILY_QUERIES["unknown_effect"],
        )
        selected = None
        selected_query = ""

        for query in queries:
            candidates = _find_or_download(
                query,
                count=options_per_query,
            )
            for candidate in candidates:
                file_value = _normalise_file(
                    str(_item_value(candidate, "file", ""))
                )
                if not file_value or file_value in used_files:
                    continue
                selected = candidate
                selected_query = query
                used_files.add(file_value)
                break
            if selected is not None:
                break

        if selected is None:
            unresolved.append(
                f"Event {index + 1} at {event.get('start', 0)}s: {family}"
            )
            resolved.append(
                ResolvedSound(
                    event_index=index,
                    start=float(event.get("start") or 0),
                    end=float(event.get("end") or 0),
                    requested_family=family,
                    query_used=queries[0],
                    sound_file="",
                    sound_name="",
                    creator="",
                    license="",
                    risk="",
                    status="UNRESOLVED",
                )
            )
            continue

        resolved.append(
            ResolvedSound(
                event_index=index,
                start=float(event.get("start") or 0),
                end=float(event.get("end") or 0),
                requested_family=family,
                query_used=selected_query,
                sound_file=_normalise_file(
                    str(_item_value(selected, "file", ""))
                ),
                sound_name=str(_item_value(selected, "name", "")),
                creator=str(_item_value(selected, "creator", "")),
                license=str(_item_value(selected, "license", "")),
                risk=str(_item_value(selected, "risk", "")),
                status="RESOLVED",
            )
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        character if character.isalnum() or character in "-_"
        else "_"
        for character in Path(source_name).stem
    ).strip("_") or "reference"

    output = OUTPUT_DIR / f"{safe_name}.resolved_sfx.json"
    output.write_text(
        json.dumps(
            {
                "source_name": source_name,
                "resolved": [asdict(item) for item in resolved],
                "unresolved": unresolved,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return resolved, unresolved
