from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from radar.full_video_analyzer import (
    BASE,
    REFERENCE_DIR,
    analyze_reference_video,
)
from radar.production_planner import build_production_plan


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze an entire local reference video, identify its editing/audio "
            "structure, and create an executable or missing-assets production plan."
        )
    )
    parser.add_argument(
        "video",
        nargs="?",
        help=(
            "Path to a local MP4/MOV/MKV/WEBM. "
            "Place owned/licensed reference videos in assets/reference_videos/."
        ),
    )
    parser.add_argument(
        "--title",
        default="",
        help="Optional original title to improve format classification.",
    )
    parser.add_argument(
        "--sample-every",
        type=float,
        default=0.5,
        help="Frame sampling interval in seconds. Default: 0.5.",
    )
    args = parser.parse_args()

    if args.video:
        path = Path(args.video)
    else:
        candidates = sorted(
            path
            for path in REFERENCE_DIR.rglob("*")
            if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
        )
        if not candidates:
            raise SystemExit(
                "No reference video supplied. Put an owned/licensed MP4 in "
                "assets/reference_videos/ or pass its path."
            )
        path = candidates[0]

    if not path.is_absolute():
        project_relative = BASE / path
        if project_relative.exists():
            path = project_relative

    print(f"Analyzing full video: {path}")
    analysis = analyze_reference_video(
        path,
        title_hint=args.title,
        sample_interval=max(0.2, args.sample_every),
    )
    analysis_path = analysis.save()

    plan = build_production_plan(analysis)
    plan_path = plan.save()

    print("\nAnalysis complete")
    print(f"Analysis: {analysis_path}")
    print(f"Plan:     {plan_path}")
    print(f"Format:   {plan.detected_format}")
    print(f"Confidence: {plan.confidence}%")
    print(f"Mode:     {plan.recreation_mode}")

    if plan.missing_assets:
        print("\nNeeds from you:")
        for item in plan.missing_assets:
            print(f"- {item}")
    else:
        print("\nAll required assets appear available.")

    print("\nPlan summary:")
    print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
