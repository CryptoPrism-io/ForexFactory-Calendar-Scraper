#!/usr/bin/env python3
"""
Daily Sync (CSV Version): Fetch last 3 + next 7 days and reconcile with existing CSV
Local testing version - no database required
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

try:
    from scraper_core import ForexFactoryScraperCore
    from data_reconciliation import DataReconciler
except ImportError:
    print("Error: Missing required modules")
    exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main execution"""
    logger.info("="*70)
    logger.info("DAILY SYNC (CSV): Fetch last 3 + next 7 days, reconcile with existing")
    logger.info("="*70)

    try:
        # File paths
        main_file = Path("forexfactory_events_FINAL.csv")
        backup_file = Path("forexfactory_events_BACKUP.csv")
        new_file = Path("forexfactory_events_DAILY.csv")
        summary_file = Path("sync_summary.txt")

        # Calculate date range
        today = datetime.now().date()
        days_back = 3
        days_forward = 7
        start_date = today - timedelta(days=days_back)
        end_date = today + timedelta(days=days_forward)

        logger.info(f"Syncing data from {start_date} to {end_date}")

        # Initialize scraper
        scraper = ForexFactoryScraperCore()

        # Scrape new data
        logger.info("Scraping new data...")
        df_new = scraper.scrape_date_range(start_date, end_date)

        events_processed = len(df_new) if not df_new.empty else 0
        logger.info(f"Scraped {events_processed} events")

        # Add impact classification
        if not df_new.empty:
            logger.info("Adding impact classification...")
            df_new['impact'] = df_new['event'].apply(
                lambda x: scraper.classify_impact(x)
            )

            # Rename columns
            df_new.columns = ['Date', 'Time', 'Currency', 'Impact', 'Event', 'Actual', 'Forecast', 'Previous']

            # Load existing data
            logger.info("Loading existing data...")
            if main_file.exists():
                df_existing = pd.read_csv(main_file)
                logger.info(f"Found {len(df_existing)} existing events")
            else:
                logger.warning("No existing CSV found, creating new")
                df_existing = pd.DataFrame()

            # Reconcile data
            logger.info("Reconciling data...")
            df_new_events, df_updates, summary = DataReconciler.reconcile(df_new, df_existing)

            # Create backup of original
            if main_file.exists():
                logger.info(f"Creating backup: {backup_file}")
                df_existing.to_csv(backup_file, index=False, encoding='utf-8')

            # Merge new events with existing
            if not df_new_events.empty:
                logger.info(f"Adding {len(df_new_events)} new events")
                df_merged = pd.concat([df_existing, df_new_events], ignore_index=True)
            else:
                df_merged = df_existing.copy()

            # Update actual values
            if not df_updates.empty:
                logger.info(f"Updating {len(df_updates)} actual values")
                for _, update in df_updates.iterrows():
                    mask = (
                        (df_merged['Date'] == update['date']) &
                        (df_merged['Currency'] == update['currency']) &
                        (df_merged['Event'] == update['event'])
                    )
                    if mask.any():
                        df_merged.loc[mask, 'Actual'] = update['actual']
                        logger.info(f"  Updated {update['currency']} {update['event']}: {update['actual']}")

            # Save merged data
            logger.info(f"Saving merged data to {main_file}")
            df_merged = df_merged.drop_duplicates(subset=['Date', 'Currency', 'Event'], keep='first')
            df_merged.to_csv(main_file, index=False, encoding='utf-8')

            # Save daily snapshot
            logger.info(f"Saving daily snapshot to {new_file}")
            df_new.to_csv(new_file, index=False, encoding='utf-8')

            # Print summary
            DataReconciler.print_summary(df_new_events, df_updates)

            # Write summary file
            with open(summary_file, 'w') as f:
                f.write("="*70 + "\n")
                f.write("DAILY SYNC SUMMARY\n")
                f.write("="*70 + "\n\n")
                f.write(f"Sync Date: {datetime.now().isoformat()}\n")
                f.write(f"Date Range: {start_date} to {end_date}\n\n")
                f.write(f"Events Scraped: {events_processed}\n")
                f.write(f"New Events Added: {len(df_new_events)}\n")
                f.write(f"Actual Values Updated: {len(df_updates)}\n")
                f.write(f"Total Events in DB: {len(df_merged)}\n\n")
                f.write("Files:\n")
                f.write(f"  Main: {main_file} ({len(df_merged)} events)\n")
                f.write(f"  Backup: {backup_file}\n")
                f.write(f"  Daily: {new_file}\n")

            logger.info("="*70)
            logger.info(f"DAILY SYNC COMPLETE")
            logger.info(f"  Processed: {events_processed}")
            logger.info(f"  Added: {len(df_new_events)}")
            logger.info(f"  Updated: {len(df_updates)}")
            logger.info(f"  Total in main file: {len(df_merged)}")
            logger.info("="*70)

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
