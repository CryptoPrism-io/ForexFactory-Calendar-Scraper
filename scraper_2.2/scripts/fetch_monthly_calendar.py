#!/usr/bin/env python3
"""Fetch ForexFactory calendar rows for a month and dump them for inspection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scraper import ForexFactoryScraper  # noqa: E402


def format_event(event: dict, mode: str) -> str:
    """Render a single event according to the requested output mode."""
    if mode == "json":
        return json.dumps(event, default=str, ensure_ascii=False)

    friendly = (
        f"{event.get('date')} {event.get('time', ''):8} "
        f"{event.get('time_utc', ''):6} UTC "
        f"{event.get('currency', ''):5} {event.get('impact', ''):5} "
        f"{event.get('event', '')}"
    )
    return friendly


def print_events(events: Iterable[dict], mode: str, limit: int | None) -> None:
    """Print the fetched events respecting the limit and format."""
    count = 0
    for event in events:
        if limit is not None and count >= limit:
            break
        print(format_event(event, mode))
        count += 1
    if count == 0:
        print("No events were returned for the requested period.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch ForexFactory calendar data for a month.")
    parser.add_argument(
        "--period",
        default="month=this",
        help="Calendar period to scrape (day=today, week=this, month=last|this|next).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="How to render each event in the output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="How many events to show (default: all).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scraper = ForexFactoryScraper(verbose=True)
    success = scraper.scrape_period(args.period)

    if not success:
        print("Scraper reported failure; no events were collected.", file=sys.stderr)
        return 1

    events = scraper.get_events()
    print("\n===== EVENTS =====")
    print(f"Period: {args.period}")
    print(f"Total events fetched: {len(events)}\n")
    print_events(events, args.format, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
