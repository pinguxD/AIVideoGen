from __future__ import annotations

import argparse
import json
from pathlib import Path

from radar.reference_scout import (
    DB_PATH,
    list_reference_queue,
    update_reference_queue,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Use the latest Trend Radar scan to choose the most useful videos "
            "for the AI's reference-learning queue."
        )
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Number of top learning candidates to keep/update. Default: 25",
    )
    args = parser.parse_args()

    selected = update_reference_queue(limit=max(1, args.limit))
    print(f"Reference queue updated: {DB_PATH}")
    print(f"Selected {len(selected)} learning candidates.\n")

    for index, item in enumerate(selected[: args.limit], start=1):
        print(
            f"{index:02d}. [{item['learning_value']}] "
            f"{item['title']}\n"
            f"    {item['url']}\n"
            f"    Why: {', '.join(item['reasons'])}\n"
        )


if __name__ == "__main__":
    main()
