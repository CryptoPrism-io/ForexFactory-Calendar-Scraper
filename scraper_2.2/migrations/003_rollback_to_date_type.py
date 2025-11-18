#!/usr/bin/env python3
"""
Rollback Migration: Convert date column from VARCHAR back to DATE type with YYYY-MM-DD format

This migration:
1. Adds a new temporary column (date_new) as DATE type
2. Converts existing VARCHAR values (DD MM YYYY) to DATE format (YYYY-MM-DD)
3. Drops the old date column
4. Renames date_new to date
5. Updates constraints and indexes
"""

import sys
import psycopg2
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from config import get_config

def run_migration():
    """Execute the rollback migration"""

    config = get_config()
    db_config = config.get_db_config().copy()
    db_config.pop('pool_size', None)

    print("=" * 80)
    print("ROLLBACK MIGRATION: Convert date column back to DATE type (YYYY-MM-DD)")
    print("=" * 80)
    print(f"Database: {config.describe_db()}")

    try:
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        print("\n1. Adding temporary date_new column (DATE type)...")
        cur.execute("""
            ALTER TABLE economic_calendar_ff
            ADD COLUMN IF NOT EXISTS date_new DATE;
        """)
        conn.commit()
        print("   ✓ Temporary column added")

        print("\n2. Converting existing dates from DD MM YYYY to YYYY-MM-DD DATE...")
        cur.execute("""
            UPDATE economic_calendar_ff
            SET date_new = TO_DATE(date, 'DD MM YYYY')
            WHERE date_new IS NULL AND date IS NOT NULL;
        """)
        rows_updated = cur.rowcount
        conn.commit()
        print(f"   ✓ Converted {rows_updated} records")

        print("\n3. Dropping old date column...")
        cur.execute("""
            ALTER TABLE economic_calendar_ff
            DROP COLUMN IF EXISTS date CASCADE;
        """)
        conn.commit()
        print("   ✓ Old column dropped")

        print("\n4. Renaming date_new to date...")
        cur.execute("""
            ALTER TABLE economic_calendar_ff
            RENAME COLUMN date_new TO date;
        """)
        conn.commit()
        print("   ✓ Column renamed")

        print("\n5. Adding NOT NULL constraint...")
        cur.execute("""
            ALTER TABLE economic_calendar_ff
            ALTER COLUMN date SET NOT NULL;
        """)
        conn.commit()
        print("   ✓ Constraint added")

        print("\n6. Creating index on date column...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_economic_calendar_ff_date
            ON economic_calendar_ff(date);
        """)
        conn.commit()
        print("   ✓ Index created")

        # Verify the migration
        print("\n7. Verifying migration...")
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'economic_calendar_ff' AND column_name = 'date';
        """)
        result = cur.fetchone()
        print(f"   Column: {result[0]}, Type: {result[1]}, Max Length: {result[2]}")

        cur.execute("""
            SELECT date, time, currency, event
            FROM economic_calendar_ff
            ORDER BY id DESC
            LIMIT 5;
        """)
        print("\n   Sample records (YYYY-MM-DD format):")
        for row in cur.fetchall():
            print(f"   {row[0]}  | {row[1]:10} | {row[2]:3} | {row[3][:30]}")

        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("✓ Rollback migration completed successfully!")
        print("✓ Database is now using DATE type with YYYY-MM-DD format")
        print("=" * 80)
        return 0

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return 1


if __name__ == '__main__':
    exit(run_migration())
