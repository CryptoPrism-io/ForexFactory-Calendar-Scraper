#!/usr/bin/env python3
"""
Monthly Updater: Fetch next 3 months of ForexFactory events
Runs on the 1st of each month (or manually)
"""

import os
import sys
import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scraper_core import ForexFactoryScraperCore
from database import get_db_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.yaml"""
    config_file = Path(__file__).parent / 'config.yaml'

    if not config_file.exists():
        logger.warning(f"Config file not found at {config_file}, using defaults")
        return {}

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def main():
    """Main execution"""
    logger.info("="*70)
    logger.info("MONTHLY UPDATER: Fetching next 3 months of events")
    logger.info("="*70)

    try:
        # Load configuration
        config = load_config()
        scraper_config = config.get('scraper', {})
        db_config = config.get('database', {})

        # Initialize database
        logger.info("Initializing database connection...")
        db = get_db_manager(db_config)

        # Log job start
        run_id = os.getenv('GITHUB_RUN_ID', 'local')
        log_id = db.log_sync_start('monthly_updater', 'monthly', run_id)
        logger.info(f"Job logged with ID: {log_id}")

        # Calculate date range: next 3 months from today
        months_ahead = scraper_config.get('monthly_months_ahead', 3)
        today = datetime.now().date()

        # Calculate end date
        year = today.year
        month = today.month + months_ahead
        if month > 12:
            year += month // 12
            month = month % 12
            if month == 0:
                month = 12
                year -= 1

        end_date = datetime(year, month, 1).date() - timedelta(days=1)
        start_date = today

        logger.info(f"Fetching data from {start_date} to {end_date}")

        # Initialize scraper
        scraper = ForexFactoryScraperCore(config=scraper_config)

        # Scrape data
        logger.info("Starting scrape...")
        df_events = scraper.scrape_date_range(start_date, end_date)

        events_processed = len(df_events) if not df_events.empty else 0
        logger.info(f"Scraped {events_processed} events")

        # Add impact classification if not present
        if not df_events.empty and 'impact' not in df_events.columns:
            logger.info("Adding impact classification...")
            impact_keywords = config.get('forexfactory', {}).get('impact_keywords', {})
            df_events['impact'] = df_events['event'].apply(
                lambda x: scraper.classify_impact(x, impact_keywords)
            )

        # Insert into database
        events_added = 0
        if not df_events.empty:
            logger.info(f"Inserting {events_processed} events into database...")
            events_list = df_events.to_dict('records')
            events_added, duplicates = db.insert_events(events_list, source='monthly_updater')
            logger.info(f"Inserted {events_added} new events, skipped {duplicates} duplicates")

        # Log job completion
        db.log_sync_complete(
            log_id,
            events_processed=events_processed,
            events_added=events_added,
            events_updated=0,
            errors=0
        )

        logger.info("="*70)
        logger.info(f"MONTHLY UPDATER COMPLETE")
        logger.info(f"  Processed: {events_processed}")
        logger.info(f"  Added: {events_added}")
        logger.info("="*70)

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

        # Log failure
        try:
            db.log_sync_complete(
                log_id,
                events_processed=0,
                events_added=0,
                events_updated=0,
                errors=1,
                error_message=str(e)
            )
        except:
            pass

        return 1


if __name__ == '__main__':
    exit(main())
