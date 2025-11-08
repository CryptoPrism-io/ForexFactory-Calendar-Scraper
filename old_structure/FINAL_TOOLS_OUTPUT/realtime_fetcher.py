#!/usr/bin/env python3
"""
Real-Time Fetcher: Update actual values for today's events
Runs every 5 minutes throughout the day
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


def extract_actual_updates(df_events):
    """
    Extract only rows with actual values from scraped data

    Args:
        df_events: Scraped DataFrame

    Returns:
        List of dicts ready for DB update
    """
    if df_events.empty:
        return []

    updates = []

    for idx, row in df_events.iterrows():
        actual = row.get('actual', '')
        if actual and actual.strip() and actual != '--':
            updates.append({
                'date': row.get('date'),
                'currency': row.get('currency'),
                'event': row.get('event'),
                'actual': actual
            })

    return updates


def main():
    """Main execution"""
    logger.info("="*70)
    logger.info("REAL-TIME FETCHER: Updating actual values for today")
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
        timestamp = datetime.now().isoformat()
        log_id = db.log_sync_start('realtime_fetcher', 'realtime', f"{run_id}_{timestamp}")
        logger.info(f"Job logged with ID: {log_id}")

        # Fetch today's events
        today = datetime.now().date()
        logger.info(f"Fetching today's events for {today}...")

        # Initialize scraper
        scraper = ForexFactoryScraperCore(config=scraper_config)

        # Scrape today's events
        df_today = scraper.scrape_date(today)

        if not df_today:
            logger.info("No events scraped for today")
            events_processed = 0
            events_updated = 0
        else:
            events_processed = len(df_today)
            logger.info(f"Scraped {events_processed} events for today")

            # Extract updates (events with actual values)
            updates = extract_actual_updates(df_today)
            events_updated = 0

            if updates:
                logger.info(f"Found {len(updates)} events with actual values, updating...")
                events_updated = db.update_actual_values(updates)
                logger.info(f"Updated {events_updated} actual values")

                # Log which events were updated
                for update in updates:
                    logger.info(f"  Updated {update['currency']} {update['event']}: {update['actual']}")
            else:
                logger.info("No actual values found in today's data")

        # Log job completion
        db.log_sync_complete(
            log_id,
            events_processed=events_processed,
            events_added=0,
            events_updated=events_updated,
            errors=0
        )

        logger.info("="*70)
        logger.info(f"REAL-TIME FETCHER COMPLETE")
        logger.info(f"  Processed: {events_processed}")
        logger.info(f"  Updated: {events_updated}")
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
                error_message=str(e)[:500]
            )
        except:
            pass

        return 1


if __name__ == '__main__':
    exit(main())
