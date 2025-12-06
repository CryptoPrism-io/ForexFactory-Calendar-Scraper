#!/usr/bin/env python3
"""
Complete end-to-end integration test for new timezone system
Tests the full scraping flow with timezone detection and conversion
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from scraper import ForexFactoryScraper
from config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def main():
    print("="*70)
    print("COMPLETE INTEGRATION TEST - New Timezone System")
    print("="*70)
    print()

    config = get_config()

    print("Initializing scraper...")
    scraper = ForexFactoryScraper(verbose=True)

    try:
        print("\nAttempting to scrape today's events...")
        print("This will:")
        print("  1. Detect ForexFactory's timezone from hidden input")
        print("  2. Scrape events in ForexFactory's displayed timezone")
        print("  3. Convert all times to UTC using zoneinfo")
        print("  4. Store events with source_timezone audit trail")
        print()

        success = scraper.scrape_period("day=today")

        if not success:
            logger.error("❌ Scraping failed")
            return 1

        events = scraper.get_events()
        logger.info(f"\n✅ Scraping successful! Retrieved {len(events)} events")

        if events:
            print("\n" + "="*70)
            print("SAMPLE EVENTS (first 3)")
            print("="*70)

            for i, event in enumerate(events[:3], 1):
                print(f"\nEvent {i}:")
                print(f"  Currency:        {event.get('currency', 'N/A')}")
                print(f"  Event:           {event.get('event', 'N/A')[:50]}")
                print(f"  Time (original): {event.get('time', 'N/A')}")
                print(f"  Time UTC:        {event.get('time_utc', 'N/A')}")
                print(f"  Date UTC:        {event.get('date_utc', 'N/A')}")
                print(f"  Source TZ:       {event.get('source_timezone', 'N/A')}")
                print(f"  TZ Label:        {event.get('time_zone', 'N/A')}")

            # Verify all events have source_timezone
            print("\n" + "="*70)
            print("VERIFICATION CHECKS")
            print("="*70)

            events_with_source_tz = sum(1 for e in events if e.get('source_timezone'))
            print(f"✓ Events with source_timezone: {events_with_source_tz}/{len(events)}")

            events_with_time_utc = sum(1 for e in events if e.get('time_utc'))
            print(f"✓ Events with time_utc: {events_with_time_utc}/{len(events)}")

            events_with_date_utc = sum(1 for e in events if e.get('date_utc'))
            print(f"✓ Events with date_utc: {events_with_date_utc}/{len(events)}")

            if events_with_source_tz == len(events):
                print("\n✅ All events have source_timezone field!")
            else:
                print(f"\n⚠️  {len(events) - events_with_source_tz} events missing source_timezone")

        else:
            print("\n⚠️  No events found for today")

        print("\n" + "="*70)
        print("INTEGRATION TEST COMPLETE")
        print("="*70)
        print()
        print("Summary:")
        print(f"  - Scraping:     {'✅ SUCCESS' if success else '❌ FAILED'}")
        print(f"  - Events found: {len(events)}")
        print(f"  - Data quality: {'✅ GOOD' if events_with_source_tz == len(events) else '⚠️ CHECK LOGS'}")

        return 0

    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
