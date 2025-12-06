#!/usr/bin/env python3
"""Test database connection with new fx_global database"""

if __name__ == '__main__':
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / 'src'))

    from database import get_db_manager
    from config import get_config

    print("="*80)
    print("DATABASE CONNECTION TEST - fx_global")
    print("="*80)

    config = get_config()
    db_config = config.get_db_config()

    print(f"\nDatabase: {db_config['database']}")
    print(f"Host:     {db_config['host']}")
    print(f"Port:     {db_config['port']}")
    print(f"User:     {db_config['user']}")

    try:
        print("\nAttempting connection...")
        db = get_db_manager(db_config)

        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"✅ Connected successfully!")
                print(f"   PostgreSQL version: {version}")

                # Check if table exists
                cur.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_name = 'economic_calendar_ff'
                """)
                table_exists = cur.fetchone()[0]

                if table_exists:
                    print(f"✅ Table 'economic_calendar_ff' exists")

                    # Count records
                    cur.execute("SELECT COUNT(*) FROM economic_calendar_ff")
                    count = cur.fetchone()[0]
                    print(f"✅ Total records: {count}")

                    # Check datetime_utc column
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = 'economic_calendar_ff'
                          AND column_name = 'datetime_utc'
                    """)
                    has_datetime_utc = cur.fetchone()[0]

                    if has_datetime_utc:
                        print(f"✅ datetime_utc column exists")
                    else:
                        print(f"⚠️  datetime_utc column missing (will be created on next scrape)")

                else:
                    print(f"⚠️  Table 'economic_calendar_ff' does not exist")
                    print(f"    Will be created automatically on first scrape")

        print("\n" + "="*80)
        print("✅ CONNECTION TEST PASSED")
        print("="*80)

    except Exception as e:
        print(f"\n❌ CONNECTION FAILED: {e}")
        print("\nPossible issues:")
        print("  1. Database 'fx_global' doesn't exist yet")
        print("     → Run: ALTER DATABASE dbcp RENAME TO fx_global;")
        print("  2. Network/firewall issue")
        print("  3. Wrong credentials")
        sys.exit(1)
