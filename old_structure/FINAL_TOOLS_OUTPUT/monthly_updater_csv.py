#!/usr/bin/env python3
"""
Monthly Updater (CSV Version): Fetch next 3 months and save to CSV
Local testing version - no database required
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

try:
    from scraper_core import ForexFactoryScraperCore
except ImportError:
    print("Error: Missing scraper_core.py")
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
    logger.info("MONTHLY UPDATER (CSV): Fetching next 3 months of events")
    logger.info("="*70)

    try:
        output_file = Path("forexfactory_events_MONTHLY.csv")

        # Calculate date range: next 3 months from today
        today = datetime.now().date()

        # Calculate end date (3 months ahead)
        year = today.year
        month = today.month + 3
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
        scraper = ForexFactoryScraperCore()

        # Scrape data
        logger.info("Starting scrape...")
        df_events = scraper.scrape_date_range(start_date, end_date)

        events_processed = len(df_events) if not df_events.empty else 0
        logger.info(f"Scraped {events_processed} events")

        # Add impact classification
        if not df_events.empty:
            logger.info("Adding impact classification...")
            df_events['impact'] = df_events['event'].apply(
                lambda x: scraper.classify_impact(x)
            )

            # Rename columns to match expected format
            df_events.columns = ['Date', 'Time', 'Currency', 'Impact', 'Event', 'Actual', 'Forecast', 'Previous']

            # Save to CSV
            logger.info(f"Saving {events_processed} events to {output_file}")
            df_events.to_csv(output_file, index=False, encoding='utf-8')

            logger.info(f"✓ Saved to {output_file}")
            logger.info(f"  Rows: {len(df_events)}")
            logger.info(f"  Impact distribution:")
            for impact, count in df_events['Impact'].value_counts().items():
                pct = (count / len(df_events)) * 100
                logger.info(f"    {impact:10} {count:5} ({pct:5.1f}%)")

        logger.info("="*70)
        logger.info(f"MONTHLY UPDATER COMPLETE - {events_processed} events")
        logger.info("="*70)

        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
