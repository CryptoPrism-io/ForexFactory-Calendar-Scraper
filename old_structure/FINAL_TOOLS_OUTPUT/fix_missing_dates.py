#!/usr/bin/env python3
"""
Fix missing dates in ForexFactory events
Since we scraped by week, we can reconstruct approximate dates
"""

import pandas as pd
from datetime import datetime, timedelta
import re

def get_week_monday(week_code):
    """
    Convert week code like '202531' to Monday of that week
    2025 = year, 31 = week number (ISO calendar)
    """
    year = int(week_code[:4])
    week = int(week_code[4:6])

    # January 4th is always in week 1
    jan4 = datetime(year, 1, 4)

    # Find the Monday of week 1
    week1_monday = jan4 - timedelta(days=jan4.weekday())

    # Add weeks
    target_monday = week1_monday + timedelta(weeks=week-1)

    return target_monday.date()


def add_dates_from_weekly_raw(raw_csv_files, output_csv):
    """
    Read weekly raw CSVs, extract week info, and add proper dates
    """
    all_events = []

    # Process each weekly file
    for raw_file in sorted(raw_csv_files):
        print(f"Processing {raw_file}...")

        # Extract week code from filename: events_raw_202531.csv → 202531
        match = re.search(r'(\d{6})\.csv', raw_file)
        if not match:
            print(f"  Skipping - couldn't extract week code")
            continue

        week_code = match.group(1)
        week_monday = get_week_monday(week_code)

        print(f"  Week code: {week_code} → Monday: {week_monday}")

        try:
            df = pd.read_csv(raw_file)

            # Add the Monday date to all events (best approximation)
            df['date_local_fixed'] = week_monday.isoformat()

            all_events.append(df)
            print(f"  ✓ Added {len(df)} events")
        except Exception as e:
            print(f"  ✗ Error: {e}")

    if not all_events:
        print("No events processed!")
        return False

    # Combine all weeks
    combined = pd.concat(all_events, ignore_index=True)

    # Replace empty date_local with fixed dates
    combined['date_local'] = combined['date_local_fixed']
    combined = combined.drop('date_local_fixed', axis=1)

    # Save
    combined.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n✓ Saved {len(combined)} events to {output_csv}")

    return True


def fix_csv_with_dates(input_csv, output_csv):
    """
    Add approximate dates to existing CSV based on week information
    """
    df = pd.read_csv(input_csv)

    print(f"Loaded {len(df)} events")
    print(f"Date column empty: {df['Date'].isna().sum()} out of {len(df)}")

    # All events are from Aug 1 - Nov 8, 2025
    # Assign approximate dates based on order/week

    # Simple approach: events are in chronological order, so estimate dates
    start_date = datetime(2025, 8, 1)

    # Count events per day (approximate 62 per week = ~9 per day)
    dates = []
    current_date = start_date

    for i in range(len(df)):
        dates.append(current_date.isoformat())

        # Move to next date roughly every 9 events (62/7 ≈ 9 per day)
        if (i + 1) % 9 == 0:
            current_date += timedelta(days=1)

    df['Date'] = dates

    # Save
    df.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n✓ Added approximate dates")
    print(f"✓ Date range: {df['Date'].min()} to {df['Date'].max()}")
    print(f"✓ Saved to {output_csv}")

    return True


if __name__ == '__main__':
    import glob
    from pathlib import Path

    print("="*80)
    print("Fixing Missing Dates in ForexFactory Events")
    print("="*80 + "\n")

    # Method 1: Use raw weekly files if available
    raw_files = sorted(glob.glob('outputs/events_raw_*.csv'))

    if raw_files:
        print(f"Found {len(raw_files)} weekly raw files")
        print("Building from weekly data...\n")
        add_dates_from_weekly_raw(raw_files, 'forexfactory_events_with_dates_v1.csv')

    # Method 2: Add approximate dates to existing CSV
    print("\nAdding approximate dates to existing CSV...\n")
    fix_csv_with_dates('forexfactory_events_with_impact.csv', 'forexfactory_events_FINAL.csv')

    print("\n" + "="*80)
    print("✓ Done! Use forexfactory_events_FINAL.csv")
    print("="*80)
