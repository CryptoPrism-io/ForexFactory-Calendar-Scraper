#!/usr/bin/env python3
"""
ForexFactory Daily Sync Job (Once Per Day at 02:00 UTC)
Scrapes ?month=this and updates the database with monthly events
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
        logging.FileHandler('daily_sync.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
logger = logging.getLogger(__name__)


def save_events_to_csv(events, config):
    """Save events to CSV file"""
    if not events or config.OUTPUT_MODE == 'db':
        return True

    import csv
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"month_this_{timestamp}.csv"

    output_dir = Path(config.CSV_OUTPUT_DIR) / 'daily'
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
    logger.info("FOREXFACTORY DAILY SYNC JOB (MONTH VIEW)")
    logger.info("="*70)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load configuration
    config = get_config()
    logger.info(f"Database: {config.describe_db()}")
    logger.info(f"Output Mode: {config.OUTPUT_MODE}")

    # Initialize database
    try:
        db = get_db_manager(config.get_db_config())
        log_id = db.log_sync_start('daily_sync', 'daily', run_id)
        logger.info(f"Sync log created: {log_id}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return 1

    # Scrape this month's events
    logger.info("\nScraping this month's events from ForexFactory...")
    scraper = ForexFactoryScraper(verbose=config.SCRAPER_VERBOSE)

    try:
        if not scraper.scrape_period("month=this"):
            logger.error("Scraping failed")
            db.log_sync_complete(log_id, 0, 0, 0, errors=1, error_message="Scraping failed")
            return 1

        events = scraper.get_events()
        logger.info(f"Scraped {len(events)} events")

        if not events:
            logger.warning("No events scraped")
            db.log_sync_complete(log_id, 0, 0, 0)
            return 0

    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        db.log_sync_complete(log_id, 0, 0, 0, errors=1, error_message=str(e))
        return 1

    # Save to CSV if enabled
    if config.OUTPUT_MODE in ['csv', 'both']:
        logger.info("\nSaving to CSV...")
        save_events_to_csv(events, config)

    # UPSERT to database
    logger.info("\nUpserting events to database...")
    try:
        inserted, updated, processed = db.upsert_events(events, source_scope='month')
        logger.info(f"UPSERT Results: {inserted} inserted, {updated} updated, {processed} processed")

        # Log completion
        db.log_sync_complete(log_id, processed, inserted, updated, errors=0)

        logger.info("\n" + "="*70)
        logger.info("✓ Daily sync completed successfully!")
        logger.info("="*70)
        return 0

    except Exception as e:
        logger.error(f"Error during UPSERT: {e}")
        db.log_sync_complete(log_id, len(events), 0, 0, errors=1, error_message=str(e))
        return 1


if __name__ == '__main__':
    exit(main())
