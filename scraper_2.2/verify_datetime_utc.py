#!/usr/bin/env python3
"""Verify datetime_utc field is populated correctly"""

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / 'src'))

    from database import get_db_manager
    from config import get_config

    print("="*100)
    print("VERIFY datetime_utc FIELD")
    print("="*100)

    config = get_config()
    db = get_db_manager(config.get_db_config())

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Check total records
            cur.execute("SELECT COUNT(*) FROM economic_calendar_ff")
            total = cur.fetchone()[0]
            print(f"\nTotal records: {total}")

            # Check records with datetime_utc
            cur.execute("SELECT COUNT(*) FROM economic_calendar_ff WHERE datetime_utc IS NOT NULL")
            with_datetime = cur.fetchone()[0]
            print(f"Records with datetime_utc: {with_datetime}")

            # Check coverage percentage
            coverage = (with_datetime / total * 100) if total > 0 else 0
            print(f"Coverage: {coverage:.1f}%")

            if with_datetime == total:
                print("✅ All records have datetime_utc!")
            else:
                print(f"❌ {total - with_datetime} records missing datetime_utc")

            # Show samples with normal times
            print("\n" + "-"*100)
            print("Sample records with NORMAL TIMES:")
            print("-"*100)
            cur.execute("""
                SELECT
                    event,
                    date_utc,
                    time_utc,
                    datetime_utc
                FROM economic_calendar_ff
                WHERE time_utc ~ '^\d{1,2}:\d{2}$'
                  AND datetime_utc IS NOT NULL
                ORDER BY datetime_utc DESC
                LIMIT 5
            """)

            rows = cur.fetchall()
            for i, row in enumerate(rows, 1):
                print(f"\n{i}. {row[0]}")
                print(f"   date_utc:     {row[1]}")
                print(f"   time_utc:     {row[2]}")
                print(f"   datetime_utc: {row[3]}")

            # Show samples with special values
            print("\n" + "-"*100)
            print("Sample records with SPECIAL VALUES (All Day, etc.):")
            print("-"*100)
            cur.execute("""
                SELECT
                    event,
                    date_utc,
                    time_utc,
                    datetime_utc
                FROM economic_calendar_ff
                WHERE time_utc IN ('All Day', 'Tentative', 'Day 1', 'Day 2', 'Day 3', '')
                   OR time_utc IS NULL
                ORDER BY datetime_utc DESC
                LIMIT 5
            """)

            rows = cur.fetchall()
            for i, row in enumerate(rows, 1):
                print(f"\n{i}. {row[0]}")
                print(f"   date_utc:     {row[1]}")
                print(f"   time_utc:     {row[2]}")
                print(f"   datetime_utc: {row[3]}")

    print("\n" + "="*100)
    print("✅ VERIFICATION COMPLETE")
    print("="*100)
