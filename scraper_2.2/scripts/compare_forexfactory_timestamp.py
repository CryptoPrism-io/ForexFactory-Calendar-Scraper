#!/usr/bin/env python3
"""Compare system time vs the timezone currently displayed on ForexFactory."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from scraper import ForexFactoryScraper


URL = "https://www.forexfactory.com/calendar?day=today"


def pretty_print_delta(delta):
    total_seconds = delta.total_seconds()
    hours = int(total_seconds // 3600)
    minutes = int((abs(total_seconds) % 3600) // 60)
    sign = "+" if total_seconds >= 0 else "-"
    return f"{sign}{abs(hours):02d}:{minutes:02d}"


def main() -> int:
    print(f"Opening {URL}")
    scraper = ForexFactoryScraper(verbose=False)
    driver = scraper.get_driver()

    try:
        driver.get(URL)
        scraper.wait_for_calendar_ready(driver)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        ff_timezone, offset_hours = scraper.detect_timezone(soup, html)

        local_dt = datetime.now().astimezone()
        canonical_tz = scraper.resolve_timezone_name(ff_timezone) or ff_timezone
        try:
            ff_zone = ZoneInfo(canonical_tz)
        except Exception:
            ff_zone = timezone.utc
        ff_dt = datetime.now(ff_zone)

        delta = ff_dt - local_dt

        print(f"System time:        {local_dt:%Y-%m-%d %H:%M:%S %Z%z}")
        print(f"ForexFactory time:  {ff_dt:%Y-%m-%d %H:%M:%S %Z%z}")
        print(f"Detected timezone:  {ff_timezone} (UTC{offset_hours:+.1f})")
        print(f"Difference (FF - system): {pretty_print_delta(delta)}")
        return 0

    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
