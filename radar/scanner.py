from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pandas as pd
from rich.console import Console

from .assets import scan_assets
from .config import CONFIG
from .db import connect, upsert_video
from .gameplay_miner import mine_raw_gameplay
from .scoring import (
    auto_recreate,
    detect_game,
    opportunity_score,
    production_score,
    title_variants,
    viral_dna,
)
from .sound_finder import build_sound_searches
from .video_intelligence import enrich_video
from .youtube import YouTubeClient, parse_duration_seconds

console = Console()


def _bool_value(value: object) -> bool:
    """Handle booleans read back from CSVs as bools or strings."""
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _json_tags(value: object) -> str:
    """Store YouTube tags safely in CSV/SQLite-friendly form."""
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return json.dumps([], ensure_ascii=False)


def run_scan() -> pd.DataFrame:
    out = Path(CONFIG.output_dir)
    diagnostics = out / "diagnostics"
    diagnostics.mkdir(parents=True, exist_ok=True)

    if CONFIG.mine_raw_gameplay:
        try:
            hits = mine_raw_gameplay(
                max_clips_per_file=CONFIG.max_mined_clips_per_file,
                clip_len=CONFIG.mined_clip_length_seconds,
            )
            console.print(f"[cyan]Raw gameplay miner:[/] {len(hits)} clips registered/mined")
        except Exception as exc:
            console.print(f"[yellow]Raw gameplay miner skipped/failed: {exc}[/]")

    asset_index = scan_assets()
    console.print(
        "[cyan]Asset library:[/] "
        f"{asset_index['source']} source files, "
        f"{asset_index['sounds']} sounds, "
        f"{asset_index.get('raw_gameplay', 0)} raw gameplay files"
    )

    yt = YouTubeClient(CONFIG.youtube_api_key)
    raw: list[dict] = []
    seen: set[str] = set()

    for query in CONFIG.queries:
        try:
            items = yt.search(
                query,
                CONFIG.days_back,
                CONFIG.max_results_per_query,
                CONFIG.region_code,
            )
        except Exception as exc:
            console.print(f"[red]Search failed for {query}: {exc}[/]")
            continue

        for item in items:
            video_id = item.get("id", {}).get("videoId")
            if video_id and video_id not in seen:
                seen.add(video_id)
                raw.append(
                    {
                        "video_id": video_id,
                        "query": query,
                        "search_title": item.get("snippet", {}).get("title", ""),
                    }
                )
            if len(raw) >= CONFIG.max_total_candidates:
                break
        if len(raw) >= CONFIG.max_total_candidates:
            break

    pd.DataFrame(raw).to_csv(diagnostics / "raw_candidates.csv", index=False)
    console.print(f"[green]Raw candidates:[/] {len(raw)}")

    videos = yt.videos([row["video_id"] for row in raw])
    channels = yt.channels(
        [video.get("snippet", {}).get("channelId", "") for video in videos]
    )

    processed: list[dict] = []
    rejected: list[dict] = []
    now = datetime.now(timezone.utc)
    con = connect(CONFIG.db_path)

    try:
        for video in videos:
            snippet = video.get("snippet", {})
            statistics = video.get("statistics", {})
            content_details = video.get("contentDetails", {})

            channel_id = snippet.get("channelId", "")
            channel = channels.get(channel_id, {})
            views = int(statistics.get("viewCount", 0) or 0)
            subscribers = int(
                channel.get("statistics", {}).get("subscriberCount", 0) or 0
            )
            duration = parse_duration_seconds(content_details.get("duration", ""))
            published = snippet.get("publishedAt", "")

            try:
                age_days = max(
                    0.05,
                    (
                        now
                        - datetime.fromisoformat(published.replace("Z", "+00:00"))
                    ).total_seconds()
                    / 86400,
                )
            except Exception:
                age_days = 1.0

            row = {
                "video_id": video.get("id", ""),
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": _json_tags(snippet.get("tags", [])),
                "url": f"https://www.youtube.com/shorts/{video.get('id', '')}",
                "channel_id": channel_id,
                "channel_title": snippet.get("channelTitle", ""),
                "subscriber_count": subscribers,
                "view_count": views,
                "published_at": published,
                "age_days": round(age_days, 3),
                "duration_seconds": duration,
                "thumbnail": (
                    snippet.get("thumbnails", {}).get("high", {}).get("url", "")
                ),
            }

            reasons: list[str] = []
            if views < CONFIG.min_views:
                reasons.append("below MIN_VIEWS")
            if subscribers > CONFIG.max_channel_subs:
                reasons.append("channel over MAX_CHANNEL_SUBS")
            if duration and duration > 65:
                reasons.append("not a Short duration")

            row["views_per_day"] = round(views / age_days, 2)
            row["views_per_sub"] = round(views / max(1, subscribers), 2)
            row["game"] = detect_game(row)

            # The new classifier uses title, description, tags, duration and thumbnail.
            row = enrich_video(row)

            # Production and auto-create scoring now consume the classifier's
            # template_type instead of reclassifying from title keywords.
            row["viral_dna"] = viral_dna(row)
            prod_score, prod_verdict, tools, missing_skills, why_make = (
                production_score(row)
            )
            auto_score, auto_verdict, template, required, missing_assets = (
                auto_recreate(row, asset_index)
            )

            row.update(
                {
                    "production_score": prod_score,
                    "production_verdict": prod_verdict,
                    "required_tools": tools,
                    "missing_skills": missing_skills,
                    "why_make": why_make,
                    "auto_recreate_score": auto_score,
                    "auto_recreate_verdict": auto_verdict,
                    "required_inputs": required,
                    "missing_assets": missing_assets,
                    "opportunity_score": opportunity_score(
                        row, prod_score, auto_score
                    ),
                    "title_variants": title_variants(row),
                }
            )

            if _bool_value(row.get("classification_needs_review")):
                reasons.append("classification needs manual review")

            row["rejection_reason"] = "; ".join(dict.fromkeys(reasons))
            processed.append(row)

            if reasons:
                rejected.append(row)
            else:
                upsert_video(con, row)
    finally:
        con.commit()
        con.close()

    if processed:
        frame = pd.DataFrame(processed).sort_values(
            "opportunity_score", ascending=False
        )
    else:
        frame = pd.DataFrame()

    frame.to_csv(out / "trend_report.csv", index=False)
    frame.to_csv(diagnostics / "processed_candidates.csv", index=False)
    pd.DataFrame(rejected).to_csv(
        diagnostics / "rejected_candidates.csv", index=False
    )

    if not frame.empty:
        build_sound_searches(frame.to_dict("records"))

    # Creator AI reads this file. Uncertain classifications are intentionally
    # excluded until corrected on /classification-review and rescanned.
    usable = (
        frame[frame["rejection_reason"].eq("")].copy()
        if not frame.empty
        else frame
    )
    usable.to_csv(out / "final_opportunities.csv", index=False)

    with (diagnostics / "rejection_summary.md").open(
        "w", encoding="utf-8"
    ) as handle:
        handle.write(
            "# Rejection Summary\n\n"
            f"Raw candidates: {len(raw)}\n"
            f"Processed: {len(processed)}\n"
            f"Usable: {len(usable)}\n"
            f"Rejected: {len(rejected)}\n\n"
        )
        if rejected:
            handle.write(
                pd.Series(
                    [item["rejection_reason"] for item in rejected]
                ).value_counts().to_markdown()
            )

    auto_count = (
        len(
            usable[
                usable["auto_recreate_verdict"].astype(str).eq("AUTO CREATE")
            ]
        )
        if not usable.empty
        else 0
    )
    review_count = (
        int(
            frame["classification_needs_review"]
            .map(_bool_value)
            .sum()
        )
        if not frame.empty
        and "classification_needs_review" in frame.columns
        else 0
    )

    console.print(
        f"[bold green]Saved {len(usable)} usable candidates.[/] "
        f"{auto_count} auto-create now. "
        f"{review_count} waiting for classification review."
    )
    return usable
