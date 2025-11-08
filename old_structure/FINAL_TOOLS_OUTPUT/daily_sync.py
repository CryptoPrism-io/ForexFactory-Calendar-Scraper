#!/usr/bin/env python3
"""
Daily Sync: Fetch past 3 days + next 7 days and reconcile with database
Runs daily at a configured time (default 6am UTC)
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
from data_reconciliation import DataReconciler
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
    logger.info("DAILY SYNC: Fetching last 3 + next 7 days, reconciling with DB")
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
        log_id = db.log_sync_start('daily_sync', 'daily', run_id)
        logger.info(f"Job logged with ID: {log_id}")

        # Calculate date range
        days_back = scraper_config.get('daily_days_back', 3)
        days_forward = scraper_config.get('daily_days_forward', 7)

        today = datetime.now().date()
        start_date = today - timedelta(days=days_back)
        end_date = today + timedelta(days=days_forward)

        logger.info(f"Fetching data from {start_date} to {end_date}")

        # Initialize scraper
        scraper = ForexFactoryScraperCore(config=scraper_config)

        # Scrape data
        logger.info("Starting scrape...")
        df_new = scraper.scrape_date_range(start_date, end_date)

        events_processed = len(df_new) if not df_new.empty else 0
        logger.info(f"Scraped {events_processed} events")

        # Add impact classification
        if not df_new.empty and 'impact' not in df_new.columns:
            logger.info("Adding impact classification...")
            impact_keywords = config.get('forexfactory', {}).get('impact_keywords', {})
            df_new['impact'] = df_new['event'].apply(
                lambda x: scraper.classify_impact(x, impact_keywords)
            )

        # Get existing data from database
        logger.info(f"Fetching existing data for {start_date} to {end_date}...")
        existing_records = db.get_events_by_date_range(str(start_date), str(end_date))

        if existing_records:
            import pandas as pd
            df_existing = pd.DataFrame(existing_records)
            logger.info(f"Found {len(df_existing)} existing records")
        else:
            import pandas as pd
            df_existing = pd.DataFrame()
            logger.info("No existing records found")

        # Reconcile data
        logger.info("Reconciling data...")
        df_new_events, df_updates, summary = DataReconciler.reconcile(df_new, df_existing)

        events_added = 0
        events_updated = 0

        # Insert new events
        if not df_new_events.empty:
            logger.info(f"Inserting {len(df_new_events)} new events...")
            events_list = df_new_events.to_dict('records')
            events_added, duplicates = db.insert_events(events_list, source='daily_sync')
            logger.info(f"Inserted {events_added} new events, skipped {duplicates} duplicates")

        # Update actual values
        if not df_updates.empty:
            logger.info(f"Updating {len(df_updates)} actual values...")
            updates_list = df_updates.to_dict('records')
            events_updated = db.update_actual_values(updates_list)
            logger.info(f"Updated {events_updated} actual values")

        # Print summary
        DataReconciler.print_summary(df_new_events, df_updates)

        # Log job completion
        db.log_sync_complete(
            log_id,
            events_processed=events_processed,
            events_added=events_added,
            events_updated=events_updated,
            errors=0
        )

        logger.info("="*70)
        logger.info(f"DAILY SYNC COMPLETE")
        logger.info(f"  Processed: {events_processed}")
        logger.info(f"  Added: {events_added}")
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
