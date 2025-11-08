#!/usr/bin/env python3
"""
ForexFactory Economic Calendar Scraper - Full Year 2025
Scrapes all events for the specified date range
"""

import csv
import time
from datetime import datetime, date, timedelta
from pathlib import Path
import pandas as pd

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Missing required packages")
    print("Install with: pip install selenium undetected-chromedriver beautifulsoup4")
    exit(1)


class ForexFactoryScraper:
    def __init__(self):
        self.base_url = "https://www.forexfactory.com/calendar"
        self.all_events = []
        self.driver = None

    def get_driver(self):
        """Create undetected Chrome driver with realistic settings"""
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        try:
            driver = uc.Chrome(options=options, version_main=None)
            return driver
        except Exception as e:
            print(f"Error creating driver: {e}")
            return None

    def scrape_week(self, week_date: date):
        """Scrape events for a single week"""
        week_str = week_date.isoformat()
        print(f"  {week_str}...", end=" ", flush=True)

        driver = self.get_driver()
        if not driver:
            print("FAILED")
            return 0

        try:
            url = f"{self.base_url}?day={week_str}"
            driver.get(url)

            # Wait for Cloudflare challenge to complete and page to load
            # Try multiple wait strategies
            time.sleep(3)

            # Wait for actual content to appear
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "calendar__row")) > 0 or
                              "Just a moment" not in d.page_source
                )
            except:
                pass  # Continue anyway, some pages might not have rows

            # Extra wait for Cloudflare
            time.sleep(2)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            rows = soup.find_all('tr', class_='calendar__row')

            week_count = 0
            for row in rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 7:
                        continue

                    date_text = cells[0].get_text(strip=True)
                    time_text = cells[1].get_text(strip=True)
                    currency = cells[2].get_text(strip=True)
                    impact = cells[3].get_text(strip=True)
                    title = cells[4].get_text(strip=True)
                    actual = cells[5].get_text(strip=True)
                    forecast = cells[6].get_text(strip=True)
                    previous = cells[7].get_text(strip=True) if len(cells) > 7 else ""

                    if not title:
                        continue

                    event = {
                        'Date': date_text if date_text else week_str,
                        'Time': time_text,
                        'Currency': currency,
                        'Impact': impact,
                        'Event': title,
                        'Actual': actual if actual != "--" else "",
                        'Forecast': forecast if forecast != "--" else "",
                        'Previous': previous if previous != "--" else ""
                    }

                    self.all_events.append(event)
                    week_count += 1

                except Exception:
                    continue

            print(f"OK ({week_count})")
            return week_count

        except Exception as e:
            print(f"ERROR: {str(e)[:40]}")
            return 0
        finally:
            try:
                driver.quit()
            except:
                pass

    def scrape_year(self, year: int = 2025):
        """Scrape all weeks in a year"""
        print(f"\n{'='*70}")
        print(f"Scraping ForexFactory {year} - All Weeks")
        print(f"{'='*70}\n")

        # Start from Jan 1, go through Dec 31
        start = date(year, 1, 1)
        end = date(year, 12, 31)

        current = start
        total = 0
        request_count = 0

        while current <= end:
            # Get Monday of the week
            monday = current - timedelta(days=current.weekday())

            if monday <= end:
                try:
                    count = self.scrape_week(monday)
                    total += count
                    request_count += 1

                    # More realistic rate limiting - add extra delay every few requests
                    if request_count % 5 == 0:
                        print(f"\n   [Pausing to avoid rate limiting...]", flush=True)
                        time.sleep(5)
                    else:
                        time.sleep(2)  # Rate limiting between requests

                except KeyboardInterrupt:
                    print("\n\nInterrupted by user")
                    break
                except Exception as e:
                    print(f"Error: {e}")

            current += timedelta(days=7)

        print(f"\n{'='*70}")
        print(f"Total Events Scraped: {total}")
        print(f"{'='*70}\n")

        return total

    def classify_impact(self, title):
        """Classify impact based on event title"""
        if not title:
            return "unknown"

        title_lower = title.lower()

        high_keywords = ['fomc', 'fed', 'ecb', 'boe', 'boj', 'rba', 'boc',
                        'nonfarm payroll', 'employment change', 'jobless claims',
                        'unemployment', 'gdp', 'cpi', 'ppi', 'inflation']

        medium_keywords = ['pmi', 'ism', 'factory orders', 'durable goods',
                          'consumer confidence', 'retail sales', 'building permits']

        low_keywords = ['speaks', 'speech', 'holiday', 'daylight saving',
                       'sentiment', 'survey', 'preliminary']

        for keyword in high_keywords:
            if keyword in title_lower:
                return "high"

        for keyword in medium_keywords:
            if keyword in title_lower:
                return "medium"

        for keyword in low_keywords:
            if keyword in title_lower:
                return "low"

        return "unknown"

    def save_to_csv(self, output_file: str):
        """Save events to CSV with impact classification"""
        if not self.all_events:
            print("No events to save!")
            return False

        df = pd.DataFrame(self.all_events)

        # Add impact classification
        df['Impact'] = df['Event'].apply(self.classify_impact)

        # Reorder columns
        columns_order = ['Date', 'Time', 'Currency', 'Impact', 'Event',
                        'Actual', 'Forecast', 'Previous']
        df = df[columns_order]

        # Save
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False, encoding='utf-8')

        print(f"✓ Saved {len(df)} events to: {output_file}")
        print(f"  File size: {Path(output_file).stat().st_size / 1024:.1f} KB")

        # Show summary
        print(f"\n{'='*70}")
        print("DATA SUMMARY")
        print(f"{'='*70}")
        print(f"Total Events: {len(df)}")
        print(f"\nImpact Distribution:")
        for impact, count in df['Impact'].value_counts().items():
            pct = (count / len(df)) * 100
            print(f"  {impact:10} {count:5} ({pct:5.1f}%)")

        print(f"\nCurrency Distribution:")
        for ccy, count in df['Currency'].value_counts().items():
            pct = (count / len(df)) * 100
            print(f"  {ccy:10} {count:5} ({pct:5.1f}%)")

        print(f"\nDate Range:")
        print(f"  From: {df['Date'].min()}")
        print(f"  To:   {df['Date'].max()}")

        print(f"\n{'='*70}\n")

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape ForexFactory Economic Calendar for full year"
    )
    parser.add_argument('--year', type=int, default=2025,
                       help='Year to scrape (default: 2025)')
    parser.add_argument('--output', default='forexfactory_events_FINAL.csv',
                       help='Output CSV file')

    args = parser.parse_args()

    scraper = ForexFactoryScraper()
    scraper.scrape_year(args.year)
    scraper.save_to_csv(args.output)

    print("✓ Done!")


if __name__ == '__main__':
    main()
