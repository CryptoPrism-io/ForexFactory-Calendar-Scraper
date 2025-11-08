#!/usr/bin/env python3
"""
Real-Time Fetcher (CSV Version): Update actual values for today's events
Local testing version - no database required
"""

import logging
import pandas as pd
from datetime import datetime
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


def extract_actual_updates(df_events):
    """Extract only rows with actual values from scraped data"""
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
    logger.info("REAL-TIME FETCHER (CSV): Updating actual values for today")
    logger.info("="*70)

    try:
        main_file = Path("forexfactory_events_FINAL.csv")
        realtime_file = Path("forexfactory_events_REALTIME.csv")

        # Fetch today's events
        today = datetime.now().date()
        logger.info(f"Fetching today's events for {today}...")

        # Initialize scraper
        scraper = ForexFactoryScraperCore()

        # Scrape today's events
        df_today = scraper.scrape_date(today)

        if not df_today:
            logger.info("No events scraped for today")
            return 0

        events_processed = len(df_today)
        logger.info(f"Scraped {events_processed} events for today")

        # Add impact classification
        df_today['impact'] = df_today['event'].apply(
            lambda x: scraper.classify_impact(x)
        )

        # Rename columns
        df_today.columns = ['Date', 'Time', 'Currency', 'Impact', 'Event', 'Actual', 'Forecast', 'Previous']

        # Extract updates (events with actual values)
        updates = extract_actual_updates(df_today)

        if updates:
            logger.info(f"Found {len(updates)} events with actual values")

            # Load existing data
            if main_file.exists():
                df_main = pd.read_csv(main_file)
                logger.info(f"Loaded {len(df_main)} events from main file")
            else:
                logger.error(f"Main file {main_file} not found!")
                return 1

            # Apply updates
            events_updated = 0
            for update in updates:
                # Convert date string to match format
                mask = (
                    (df_main['Date'].astype(str).str.contains(str(update['date']), na=False)) &
                    (df_main['Currency'] == update['currency']) &
                    (df_main['Event'] == update['event'])
                )

                if mask.any():
                    # Only update if current actual is empty
                    current_actual = df_main.loc[mask, 'Actual'].iloc[0]
                    if not current_actual or current_actual.strip() == '':
                        df_main.loc[mask, 'Actual'] = update['actual']
                        events_updated += 1
                        logger.info(f"  Updated {update['currency']} {update['event']}: {update['actual']}")

            # Save updated main file
            if events_updated > 0:
                logger.info(f"Saving {events_updated} updates to {main_file}")
                df_main.to_csv(main_file, index=False, encoding='utf-8')

            # Save realtime snapshot
            logger.info(f"Saving realtime snapshot to {realtime_file}")
            df_today.to_csv(realtime_file, index=False, encoding='utf-8')

            logger.info("="*70)
            logger.info(f"REAL-TIME FETCHER COMPLETE")
            logger.info(f"  Processed: {events_processed}")
            logger.info(f"  Updated: {events_updated}")
            logger.info("="*70)

            return 0

        else:
            logger.info("No actual values found in today's data")
            return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
