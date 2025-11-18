#!/usr/bin/env python3
"""
ForexFactory Monthly Backfill Job (One-Time Initialization)
Scrapes ?month=last, ?month=this, ?month=next to backfill historical and upcoming events
Run manually to initialize the database with complete data
"""

import sys
import logging
import uuid
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from scraper import ForexFactoryScraper
from database import get_db_manager
from config import get_config

# Setup logging with UTF-8 encoding for console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monthly_backfill.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logger = logging.getLogger(__name__)


def save_events_to_csv(events, config, period_name):
    """Save events to CSV file"""
    if not events or config.OUTPUT_MODE == 'db':
        return True

    import csv
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"month_{period_name}_{timestamp}.csv"

    output_dir = Path(config.CSV_OUTPUT_DIR) / 'backfill'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / csv_filename

    try:
        # Map database field names to CSV field names
        csv_fieldnames = [
            'date', 'date_utc', 'time', 'time_zone', 'time_utc', 'currency',
            'impact', 'event', 'actual', 'actual_status', 'forecast', 'previous'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
            writer.writeheader()

            for event in events:
                row = {field: event.get(field, '') for field in csv_fieldnames}
                writer.writerow(row)

        file_size_kb = output_path.stat().st_size / 1024
        logger.info(f"CSV saved: {csv_filename} ({file_size_kb:.1f} KB, {len(events)} records)")
        return True

    except Exception as e:
        logger.error(f"Error saving CSV: {e}")
        return False


def main():
    """Main execution"""
    run_id = str(uuid.uuid4())[:8]

    logger.info("="*70)
    logger.info("FOREXFACTORY MONTHLY BACKFILL JOB")
    logger.info("="*70)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("This job scrapes last, this, and next months for complete historical data")

    # Load configuration
    config = get_config()
    logger.info(f"Database: {config.describe_db()}")
    logger.info(f"Output Mode: {config.OUTPUT_MODE}")

    # Initialize database
    try:
        db = get_db_manager(config.get_db_config())
        log_id = db.log_sync_start('monthly_backfill', 'backfill', run_id)
        logger.info(f"Sync log created: {log_id}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Periods to scrape
    periods = [
        ("month=last", "last"),
        ("month=this", "this"),
        ("month=next", "next")
    ]

    total_inserted = 0
    total_updated = 0
    total_processed = 0
    total_errors = 0

    for period_param, period_name in periods:
        logger.info(f"\n{'='*70}")
        logger.info(f"Scraping {period_name.upper()} month ({period_param})...")
        logger.info("="*70)

        scraper = ForexFactoryScraper(verbose=config.SCRAPER_VERBOSE)

        try:
            if not scraper.scrape_period(period_param):
                logger.error(f"Scraping {period_name} month failed")
                total_errors += 1
                continue

            events = scraper.get_events()
            logger.info(f"Scraped {len(events)} events for {period_name} month")

            if not events:
                logger.warning(f"No events scraped for {period_name} month")
                continue

            # Save to CSV if enabled
            if config.OUTPUT_MODE in ['csv', 'both']:
                logger.info(f"\nSaving {period_name} month to CSV...")
                save_events_to_csv(events, config, period_name)

            # UPSERT to database
            logger.info(f"\nUpserting {period_name} month events to database...")
            try:
                inserted, updated, processed = db.upsert_events(events, source_scope='month')
                logger.info(f"UPSERT Results: {inserted} inserted, {updated} updated, {processed} processed")

                total_inserted += inserted
                total_updated += updated
                total_processed += processed

            except Exception as e:
                logger.error(f"Error during UPSERT for {period_name} month: {e}")
                total_errors += 1

        except Exception as e:
            logger.error(f"Error during scraping {period_name} month: {e}")
            total_errors += 1

    # Log completion
    try:
        db.log_sync_complete(
            log_id,
            total_processed,
            total_inserted,
            total_updated,
            errors=total_errors
        )
    except Exception as e:
        logger.error(f"Error logging sync completion: {e}")

    logger.info("\n" + "="*70)
    logger.info("MONTHLY BACKFILL SUMMARY")
    logger.info("="*70)
    logger.info(f"Total Events Processed: {total_processed}")
    logger.info(f"Total Inserted: {total_inserted}")
    logger.info(f"Total Updated: {total_updated}")
    logger.info(f"Total Errors: {total_errors}")
    logger.info("="*70)

    return 1 if total_errors > 0 else 0


if __name__ == '__main__':
    exit(main())
