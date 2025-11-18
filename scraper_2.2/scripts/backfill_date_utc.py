#!/usr/bin/env python3
"""
One-off utility to backfill time_utc/date_utc using PST/PDT timezone logic.
"""

import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / 'src'
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scraper import ForexFactoryScraper


SPECIAL_TOKENS = {'all day', 'tentative', 'day', 'off'}


def should_skip(time_value: str) -> bool:
    if not time_value:
        return True
    lowered = time_value.strip().lower()
    if lowered in SPECIAL_TOKENS:
        return True
    if lowered.startswith('day ') or lowered.endswith('day'):
        return True
    if any(tag in lowered for tag in [' — ', '-', '–']) and not ':' in lowered:
        return True
    return False


def main():
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)

    scraper = ForexFactoryScraper(verbose=False)
    tz_obj = scraper.forced_zoneinfo or ZoneInfo('America/Los_Angeles')
    fallback_offset = -8

    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=os.getenv('POSTGRES_PORT'),
        database=os.getenv('POSTGRES_DB'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
    )
    conn.autocommit = False

    updated = 0
    processed = 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, date, time, time_zone, time_utc, date_utc
                FROM economic_calendar_ff
                """
            )
            rows = cur.fetchall()

        with conn.cursor() as cur:
            for row in rows:
                processed += 1
                row_id, date_val, time_val, time_zone_db, time_utc_db, date_utc_db = row
                date_iso = date_val.isoformat() if date_val else None

                new_time_utc = time_utc_db
                new_date_utc = date_utc_db or date_val
                new_time_zone = time_zone_db

                if time_val and not should_skip(time_val):
                    result = scraper.convert_to_utc(
                        time_val,
                        fallback_offset,
                        date_iso=date_iso,
                        return_date=True,
                        zoneinfo_obj=tz_obj,
                    )

                    if isinstance(result, tuple):
                        if len(result) == 3:
                            maybe_time, maybe_date, maybe_label = result
                        else:
                            maybe_time, maybe_date = result
                            maybe_label = None

                        if maybe_time:
                            new_time_utc = maybe_time
                        if maybe_date:
                            new_date_utc = maybe_date
                        if maybe_label:
                            new_time_zone = maybe_label
                    else:
                        new_time_utc = result
                else:
                    new_date_utc = date_val

                if (
                    new_time_utc != time_utc_db
                    or new_date_utc != date_utc_db
                    or (new_time_zone and new_time_zone != time_zone_db)
                ):
                    cur.execute(
                        """
                        UPDATE economic_calendar_ff
                        SET time_utc = %s,
                            date_utc = %s,
                            time_zone = %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (new_time_utc, new_date_utc, new_time_zone, row_id),
                    )
                    updated += 1

        conn.commit()
        print(f"Processed {processed} rows, updated {updated}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
