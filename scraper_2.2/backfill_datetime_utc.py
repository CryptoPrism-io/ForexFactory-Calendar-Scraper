#!/usr/bin/env python3
"""
Backfill datetime_utc field for existing records in the database.
Combines date_utc + time_utc into a proper TIMESTAMPTZ.
"""

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / 'src'))

    from database import get_db_manager
    from config import get_config

    print("="*100)
    print("BACKFILL datetime_utc FIELD")
    print("="*100)

    config = get_config()
    db = get_db_manager(config.get_db_config())

    print("\n1. Checking current state...")

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Check total records
            cur.execute("SELECT COUNT(*) FROM economic_calendar_ff")
            total_records = cur.fetchone()[0]
            print(f"   Total records in database: {total_records}")

            # Check records with datetime_utc already set
            cur.execute("SELECT COUNT(*) FROM economic_calendar_ff WHERE datetime_utc IS NOT NULL")
            already_set = cur.fetchone()[0]
            print(f"   Records with datetime_utc already set: {already_set}")

            # Check records that need backfilling
            cur.execute("SELECT COUNT(*) FROM economic_calendar_ff WHERE datetime_utc IS NULL")
            need_backfill = cur.fetchone()[0]
            print(f"   Records that need backfilling: {need_backfill}")

    if need_backfill == 0:
        print("\n✅ All records already have datetime_utc set. Nothing to do!")
        sys.exit(0)

    print(f"\n2. Backfilling {need_backfill} records...")
    print("   This will combine date_utc + time_utc into datetime_utc")

    # Backfill query
    backfill_query = """
        UPDATE economic_calendar_ff
        SET datetime_utc = (
            CASE
                -- Handle special values (set to midnight UTC)
                WHEN time_utc IN ('All Day', 'Tentative', 'Day 1', 'Day 2', 'Day 3', '')
                    OR time_utc IS NULL
                THEN date_utc::TIMESTAMPTZ

                -- Parse normal times (format: "HH:MM" or "H:MM")
                WHEN time_utc ~ '^\d{1,2}:\d{2}$'
                THEN (date_utc::TEXT || ' ' || time_utc || ':00')::TIMESTAMPTZ

                -- Fallback: midnight UTC
                ELSE date_utc::TIMESTAMPTZ
            END
        )
        WHERE datetime_utc IS NULL
          AND date_utc IS NOT NULL
    """

    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(backfill_query)
                updated_count = cur.rowcount
                conn.commit()

        print(f"   ✅ Updated {updated_count} records")

        # Verify the backfill
        print("\n3. Verifying backfill...")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Check records still missing datetime_utc
                cur.execute("SELECT COUNT(*) FROM economic_calendar_ff WHERE datetime_utc IS NULL")
                still_null = cur.fetchone()[0]

                if still_null > 0:
                    print(f"   ⚠️  Warning: {still_null} records still have NULL datetime_utc")
                    print("       These may be records with invalid date_utc values")
                else:
                    print("   ✅ All records now have datetime_utc set!")

                # Show sample of backfilled data
                print("\n4. Sample of backfilled data:")
                cur.execute("""
                    SELECT
                        event,
                        date_utc,
                        time_utc,
                        datetime_utc,
                        CASE
                            WHEN time_utc IN ('All Day', 'Tentative', 'Day 1', 'Day 2', 'Day 3', '')
                                OR time_utc IS NULL
                            THEN CASE
                                WHEN datetime_utc = date_utc::TIMESTAMPTZ
                                THEN '✅ MIDNIGHT (special value)'
                                ELSE '❌ MISMATCH'
                            END
                            WHEN time_utc ~ '^\d{1,2}:\d{2}$'
                            THEN CASE
                                WHEN (date_utc::TEXT || ' ' || time_utc || ':00')::TIMESTAMPTZ = datetime_utc
                                THEN '✅ MATCH'
                                ELSE '❌ MISMATCH'
                            END
                            ELSE '⚠️ UNKNOWN FORMAT'
                        END AS validation
                    FROM economic_calendar_ff
                    WHERE datetime_utc IS NOT NULL
                    ORDER BY datetime_utc DESC
                    LIMIT 5
                """)

                rows = cur.fetchall()
                for i, row in enumerate(rows, 1):
                    print(f"\n   Record {i}:")
                    print(f"      Event:        {row[0]}")
                    print(f"      date_utc:     {row[1]}")
                    print(f"      time_utc:     {row[2]}")
                    print(f"      datetime_utc: {row[3]}")
                    print(f"      Validation:   {row[4]}")

        print("\n" + "="*100)
        print("✅ BACKFILL COMPLETE")
        print("="*100)
        print(f"   Total records backfilled: {updated_count}")
        print(f"   Records still NULL: {still_null}")
        print()

    except Exception as e:
        print(f"\n❌ ERROR during backfill: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
