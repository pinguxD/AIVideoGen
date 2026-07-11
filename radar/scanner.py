from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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


def run_scan():
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
        f"[cyan]Asset library:[/] {asset_index['source']} source files, "
        f"{asset_index['sounds']} sounds, {asset_index.get('raw_gameplay', 0)} raw gameplay files"
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
    channels = yt.channels([video["snippet"]["channelId"] for video in videos])

    processed: list[dict] = []
    rejected: list[dict] = []
    now = datetime.now(timezone.utc)
    con = connect(CONFIG.db_path)

    try:
        for video in videos:
            snippet = video.get("snippet", {})
            stats = video.get("statistics", {})
            details = video.get("contentDetails", {})
            channel_id = snippet.get("channelId", "")
            channel = channels.get(channel_id, {})

            views = int(stats.get("viewCount", 0) or 0)
            subs = int(channel.get("statistics", {}).get("subscriberCount", 0) or 0)
            duration = parse_duration_seconds(details.get("duration", ""))
            published = snippet.get("publishedAt", "")
            try:
                age = max(
                    0.05,
                    (now - datetime.fromisoformat(published.replace("Z", "+00:00"))).total_seconds()
                    / 86400,
                )
            except Exception:
                age = 1.0

            row = {
                "video_id": video["id"],
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "tags": snippet.get("tags", []),
                "category_id": snippet.get("categoryId", ""),
                "default_language": snippet.get("defaultLanguage", ""),
                "url": f"https://www.youtube.com/shorts/{video['id']}",
                "channel_id": channel_id,
                "channel_title": snippet.get("channelTitle", ""),
                "subscriber_count": subs,
                "view_count": views,
                "published_at": published,
                "age_days": round(age, 3),
                "duration_seconds": duration,
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            }

            reasons: list[str] = []
            if views < CONFIG.min_views:
                reasons.append("below MIN_VIEWS")
            if subs > CONFIG.max_channel_subs:
                reasons.append("channel over MAX_CHANNEL_SUBS")
            if duration and duration > 65:
                reasons.append("not a Short duration")

            row["views_per_day"] = round(views / age, 2)
            row["views_per_sub"] = round(views / max(1, subs), 2)
            row["game"] = detect_game(row)

            # New evidence-based, multi-label intelligence layer.
            row = enrich_video(row)
            row["viral_dna"] = viral_dna(row)

            production, production_verdict, tools, missing_skills, why = production_score(row)
            auto_score, auto_verdict, template, required, missing = auto_recreate(row, asset_index)

            row.update(
                {
                    "production_score": production,
                    "production_verdict": production_verdict,
                    "required_tools": tools,
                    "missing_skills": missing_skills,
                    "why_make": why,
                    "auto_recreate_score": auto_score,
                    "auto_recreate_verdict": auto_verdict,
                    "auto_status": auto_verdict.replace(" ", "_") if auto_verdict != "MANUAL ONLY" else "MANUAL_ONLY",
                    "required_inputs": required,
                    "missing_assets": missing,
                    "title_variants": title_variants(row),
                }
            )
            row["opportunity_score"] = opportunity_score(row, production, auto_score)

            # Do not let uncertain classifications automatically enter Creator AI.
            if bool(row.get("classification_needs_review")):
                row["auto_status"] = "MANUAL_ONLY"
                row["auto_recreate_verdict"] = "MANUAL ONLY"
                if "classification review required" not in reasons:
                    reasons.append("classification review required")

            row["rejection_reason"] = "; ".join(reasons) if reasons else ""
            processed.append(row)

            # Public trend filters still determine whether it is "usable". Classification-review
            # videos remain in trend_report.csv, but are not pushed into the auto-creation queue.
            hard_reasons = [reason for reason in reasons if reason != "classification review required"]
            if hard_reasons:
                rejected.append(row)
            else:
                upsert_video(con, row)
    finally:
        con.commit()
        con.close()

    df = (
        pd.DataFrame(processed).sort_values("opportunity_score", ascending=False)
        if processed
        else pd.DataFrame()
    )
    df.to_csv(out / "trend_report.csv", index=False)
    df.to_csv(diagnostics / "processed_candidates.csv", index=False)
    pd.DataFrame(rejected).to_csv(diagnostics / "rejected_candidates.csv", index=False)

    if not df.empty:
        build_sound_searches(df.to_dict("records"))

    usable = df[~df["rejection_reason"].astype(str).str.contains(
        "below MIN_VIEWS|channel over MAX_CHANNEL_SUBS|not a Short duration",
        regex=True,
        na=False,
    )] if not df.empty else df
    usable.to_csv(out / "final_opportunities.csv", index=False)

    with (diagnostics / "rejection_summary.md").open("w", encoding="utf-8") as handle:
        handle.write(
            f"# Rejection Summary\n\nRaw candidates: {len(raw)}\n"
            f"Processed: {len(processed)}\nUsable: {len(usable)}\nRejected: {len(rejected)}\n\n"
        )
        if rejected:
            handle.write(
                pd.Series([row["rejection_reason"] for row in rejected])
                .value_counts()
                .to_markdown()
            )

    review_count = int(
        pd.to_numeric(df.get("classification_needs_review", False), errors="coerce")
        .fillna(0)
        .astype(bool)
        .sum()
    ) if not df.empty else 0
    auto_count = int((usable.get("auto_status", pd.Series(dtype=str)) == "AUTO_CREATE").sum()) if not usable.empty else 0
    console.print(
        f"[bold green]Saved {len(usable)} usable candidates.[/] "
        f"{auto_count} auto-create now; {review_count} need classification review."
    )
    return usable
