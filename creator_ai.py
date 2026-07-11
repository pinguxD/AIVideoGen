from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from radar.creator_projects import analyze_dataframe
from radar.template_renderer import render_project

BASE = Path(__file__).resolve().parent


def load_candidates() -> pd.DataFrame:
    for name in ["final_opportunities.csv", "trend_report.csv"]:
        path = BASE / "outputs" / name
        if path.exists():
            return pd.read_csv(path).fillna("")
    return pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend Radar X Creator AI")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Create projects from viral candidates")
    analyze.add_argument("--fetch-sounds", action="store_true")
    analyze.add_argument("--limit", type=int, default=100)
    generate = sub.add_parser("generate", help="Render an AUTO_READY project")
    generate.add_argument("video_id")
    args = parser.parse_args()

    if args.command == "analyze":
        projects = analyze_dataframe(load_candidates(), fetch_sounds=args.fetch_sounds, limit=args.limit)
        ready = sum(p.status == "AUTO_READY" for p in projects)
        needs = sum(p.status == "NEEDS_ASSETS" for p in projects)
        print(f"Analyzed {len(projects)} projects: {ready} ready, {needs} need assets.")
    elif args.command == "generate":
        print(render_project(args.video_id))


if __name__ == "__main__":
    main()
