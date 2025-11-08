#!/usr/bin/env python3
"""
Export ForexFactory Events to Clean CSV
Converts the already-scraped SQLite data to a simple, clean CSV
"""

import sqlite3
import pandas as pd
import argparse
from pathlib import Path


def export_from_sqlite(db_path: str, output_csv: str):
    """Read events from SQLite and export to clean CSV"""

    print(f"Reading from database: {db_path}")

    # Connect to database
    con = sqlite3.connect(db_path)

    # Read events table
    try:
        df = pd.read_sql_query('SELECT * FROM events', con)
        print(f"✓ Loaded {len(df)} records from SQLite")
    except Exception as e:
        print(f"Error reading database: {e}")
        con.close()
        return False
    finally:
        con.close()

    if df.empty:
        print("No data found!")
        return False

    # Select and rename columns for clean output
    columns_map = {
        'date_local': 'Date',
        'time_local': 'Time',
        'currency': 'Currency',
        'impact_norm': 'Impact',
        'title': 'Event',
        'actual': 'Actual',
        'forecast': 'Forecast',
        'previous': 'Previous'
    }

    # Keep only columns that exist
    available_cols = [col for col in columns_map.keys() if col in df.columns]
    rename_map = {col: columns_map[col] for col in available_cols}

    df_clean = df[available_cols].rename(columns=rename_map)

    # Fill missing values
    for col in ['Date', 'Time', 'Actual', 'Forecast', 'Previous']:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('')

    # Sort by date and time
    if 'Date' in df_clean.columns:
        df_clean = df_clean.sort_values('Date', na_position='last')

    # Save to CSV
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)

    try:
        df_clean.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"\n✓ Exported {len(df_clean)} events to: {output_csv}")

        # Show file info
        file_size = Path(output_csv).stat().st_size / 1024
        print(f"✓ File size: {file_size:.1f} KB")
        print(f"✓ Columns: {', '.join(df_clean.columns)}")

        # Show summary
        print(f"\n{'='*70}")
        print("DATA SUMMARY")
        print(f"{'='*70}")
        print(f"Total Events: {len(df_clean)}")

        if 'Currency' in df_clean.columns:
            print(f"\nEvents by Currency:")
            for ccy, count in df_clean['Currency'].value_counts().items():
                print(f"  {ccy}: {count}")

        if 'Impact' in df_clean.columns:
            print(f"\nEvents by Impact:")
            for impact, count in df_clean['Impact'].value_counts().items():
                print(f"  {impact}: {count}")

        print(f"\nSample Events (first 5):")
        print(df_clean.head(5).to_string(index=False))
        print(f"{'='*70}\n")

        return True

    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False


def export_from_csv(input_csv: str, output_csv: str):
    """Read from normalized CSV and export to clean CSV"""

    print(f"Reading from CSV: {input_csv}")

    try:
        df = pd.read_csv(input_csv)
        print(f"✓ Loaded {len(df)} records from CSV")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

    if df.empty:
        print("No data found!")
        return False

    # Select and rename columns for clean output
    columns_map = {
        'date_local': 'Date',
        'time_local': 'Time',
        'currency': 'Currency',
        'impact': 'Impact',
        'title': 'Event',
        'actual': 'Actual',
        'forecast': 'Forecast',
        'previous': 'Previous'
    }

    # Keep only columns that exist
    available_cols = [col for col in columns_map.keys() if col in df.columns]
    rename_map = {col: columns_map[col] for col in available_cols}

    df_clean = df[available_cols].rename(columns=rename_map)

    # Fill missing values
    for col in ['Date', 'Time', 'Actual', 'Forecast', 'Previous']:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].fillna('')

    # Sort by date and time
    if 'Date' in df_clean.columns:
        df_clean = df_clean.sort_values('Date', na_position='last')

    # Save to CSV
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)

    try:
        df_clean.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"\n✓ Exported {len(df_clean)} events to: {output_csv}")

        # Show file info
        file_size = Path(output_csv).stat().st_size / 1024
        print(f"✓ File size: {file_size:.1f} KB")
        print(f"✓ Columns: {', '.join(df_clean.columns)}")

        # Show summary
        print(f"\n{'='*70}")
        print("DATA SUMMARY")
        print(f"{'='*70}")
        print(f"Total Events: {len(df_clean)}")

        if 'Currency' in df_clean.columns:
            print(f"\nEvents by Currency:")
            for ccy, count in df_clean['Currency'].value_counts().items():
                print(f"  {ccy}: {count}")

        if 'Impact' in df_clean.columns:
            print(f"\nEvents by Impact:")
            for impact, count in df_clean['Impact'].value_counts().items():
                print(f"  {impact}: {count}")

        print(f"\nSample Events (first 5):")
        print(df_clean.head(5).to_string(index=False))
        print(f"{'='*70}\n")

        return True

    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Export ForexFactory Events to CSV"
    )
    parser.add_argument(
        '--db',
        default='outputs/ff_calendar.sqlite',
        help='Path to SQLite database (default: outputs/ff_calendar.sqlite)'
    )
    parser.add_argument(
        '--csv-in',
        default='outputs/events_normalized.csv',
        help='Input CSV file (if using CSV source)'
    )
    parser.add_argument(
        '--output',
        default='forexfactory_events.csv',
        help='Output CSV file (default: forexfactory_events.csv)'
    )
    parser.add_argument(
        '--source',
        choices=['sqlite', 'csv'],
        default='sqlite',
        help='Data source (sqlite or csv)'
    )

    args = parser.parse_args()

    print("="*70)
    print("ForexFactory Events CSV Exporter")
    print("="*70 + "\n")

    if args.source == 'sqlite':
        success = export_from_sqlite(args.db, args.output)
    else:
        success = export_from_csv(args.csv_in, args.output)

    if success:
        print("✓ Export completed successfully!")
    else:
        print("✗ Export failed!")
        return 1

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
