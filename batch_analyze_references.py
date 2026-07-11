from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar.reference_library import (
    ANALYZED_DIR,
    FAILED_DIR,
    PENDING_DIR,
    REPORT_DIR,
    analyze_pending_references,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze every reference video in assets/reference_videos/pending, "
            "write analysis/plan/reports, then move successful videos to analyzed "
            "and failures to failed."
        )
    )
    parser.add_argument(
        "--sample-every",
        type=float,
        default=0.5,
        help="Frame sampling interval in seconds. Default: 0.5",
    )
    parser.add_argument(
        "--keep-in-pending",
        action="store_true",
        help="Do not move analyzed/failed files out of pending.",
    )
    args = parser.parse_args()

    print(f"Pending folder:  {PENDING_DIR}")
    print(f"Analyzed folder: {ANALYZED_DIR}")
    print(f"Failed folder:   {FAILED_DIR}")
    print(f"Reports folder:  {REPORT_DIR}")

    results = analyze_pending_references(
        sample_interval=max(0.2, args.sample_every),
        move_after=not args.keep_in_pending,
    )

    analyzed = [item for item in results if item["status"] == "ANALYZED"]
    failed = [item for item in results if item["status"] == "FAILED"]

    print("\nBatch complete")
    print(f"Analyzed: {len(analyzed)}")
    print(f"Failed:   {len(failed)}")

    if failed:
        print("\nFailures:")
        for item in failed:
            print(f"- {Path(item['source']).name}: {item.get('error', 'unknown')}")

    summary_path = REPORT_DIR / "last_batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "analyzed": analyzed,
                "failed": failed,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Summary:  {summary_path}")


if __name__ == "__main__":
    main()
