#!/usr/bin/env python3
"""
Core scraping functionality for ForexFactory
Reusable scraper logic with Cloudflare bypass
"""

import logging
import time
from datetime import date, timedelta
import pandas as pd

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Missing required packages. Install with: pip install selenium undetected-chromedriver beautifulsoup4")

logger = logging.getLogger(__name__)


class ForexFactoryScraperCore:
    """Core scraper with Cloudflare anti-detection"""

    def __init__(self, base_url="https://www.forexfactory.com/calendar", config=None):
        """
        Initialize scraper

        Args:
            base_url: ForexFactory calendar base URL
            config: Config dict with browser_timeout, page_load_wait, cloudflare_wait, request_delay
        """
        self.base_url = base_url
        self.config = config or {}
        self.browser_timeout = self.config.get('browser_timeout', 30)
        self.page_load_wait = self.config.get('page_load_wait', 3)
        self.cloudflare_wait = self.config.get('cloudflare_wait', 5)
        self.request_delay = self.config.get('request_delay', 2)

    def get_driver(self):
        """Create undetected Chrome driver with Cloudflare bypass"""
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        try:
            driver = uc.Chrome(options=options, version_main=None)
            logger.debug("Chrome driver created successfully")
            return driver
        except Exception as e:
            logger.error(f"Error creating Chrome driver: {e}")
            return None

    def scrape_date(self, target_date):
        """
        Scrape events for a specific date

        Args:
            target_date: datetime.date object

        Returns:
            List of dicts with event data
        """
        date_str = target_date.isoformat()
        logger.debug(f"Scraping {date_str}...")

        driver = self.get_driver()
        if not driver:
            logger.error(f"Failed to create driver for {date_str}")
            return []

        try:
            url = f"{self.base_url}?day={date_str}"
            driver.get(url)

            # Wait for page load
            time.sleep(self.page_load_wait)

            # Wait for Cloudflare challenge to complete
            try:
                WebDriverWait(driver, self.browser_timeout).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "calendar__row")) > 0 or
                              "Just a moment" not in d.page_source
                )
                logger.debug(f"Content loaded for {date_str}")
            except Exception as e:
                logger.warning(f"Timeout waiting for content on {date_str}: {e}")

            # Extra wait for Cloudflare
            time.sleep(self.cloudflare_wait)

            # Parse HTML
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            rows = soup.find_all('tr', class_='calendar__row')

            events = []
            for row in rows:
                try:
                    cells = row.find_all('td')
                    if len(cells) < 5:
                        continue

                    # Extract data from cells
                    date_text = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    time_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    currency = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    impact = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    title = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    actual = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    forecast = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                    previous = cells[7].get_text(strip=True) if len(cells) > 7 else ""

                    # Skip empty events
                    if not title:
                        continue

                    event = {
                        'date': date_text if date_text else date_str,
                        'time': time_text,
                        'currency': currency,
                        'impact': impact,
                        'event': title,
                        'actual': actual if actual != "--" else "",
                        'forecast': forecast if forecast != "--" else "",
                        'previous': previous if previous != "--" else ""
                    }

                    events.append(event)

                except Exception as e:
                    logger.warning(f"Error parsing row: {e}")
                    continue

            logger.info(f"Scraped {len(events)} events for {date_str}")
            return events

        except Exception as e:
            logger.error(f"Error scraping {date_str}: {e}")
            return []

        finally:
            try:
                driver.quit()
            except:
                pass

    def scrape_date_range(self, start_date, end_date):
        """
        Scrape events for a date range (one request per date)

        Args:
            start_date: datetime.date object
            end_date: datetime.date object

        Returns:
            Pandas DataFrame with all events
        """
        logger.info(f"Scraping from {start_date} to {end_date}")

        all_events = []
        current = start_date
        request_count = 0

        while current <= end_date:
            try:
                events = self.scrape_date(current)
                all_events.extend(events)
                request_count += 1

                # Rate limiting
                if request_count % 5 == 0:
                    logger.info(f"Pausing after {request_count} requests...")
                    time.sleep(5)
                else:
                    time.sleep(self.request_delay)

            except KeyboardInterrupt:
                logger.warning("Scraping interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing {current}: {e}")

            current += timedelta(days=1)

        logger.info(f"Scraping complete: {len(all_events)} total events scraped")

        # Convert to DataFrame
        if all_events:
            df = pd.DataFrame(all_events)
            # Convert date column to proper date type
            try:
                df['date'] = pd.to_datetime(df['date']).dt.date
            except:
                pass
            return df
        else:
            return pd.DataFrame()

    def scrape_week(self, monday_date):
        """
        Scrape events for a week (all events appear when you query by Monday)

        Args:
            monday_date: datetime.date for the Monday of the week

        Returns:
            List of dicts with event data
        """
        return self.scrape_date(monday_date)

    def scrape_year(self, year):
        """
        Scrape all events for a year

        Args:
            year: Integer year (e.g., 2025)

        Returns:
            Pandas DataFrame with all events
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)

        return self.scrape_date_range(start, end)

    def classify_impact(self, title, impact_keywords=None):
        """
        Classify impact based on event title

        Args:
            title: Event title string
            impact_keywords: Dict with 'high', 'medium', 'low' lists of keywords

        Returns:
            Impact level: 'high', 'medium', 'low', or 'unknown'
        """
        if not title:
            return "unknown"

        if impact_keywords is None:
            impact_keywords = {
                'high': ['fomc', 'fed', 'ecb', 'boe', 'boj', 'rba', 'boc',
                        'nonfarm payroll', 'employment change', 'jobless claims',
                        'unemployment', 'gdp', 'cpi', 'ppi', 'inflation'],
                'medium': ['pmi', 'ism', 'factory orders', 'durable goods',
                          'consumer confidence', 'retail sales', 'building permits'],
                'low': ['speaks', 'speech', 'holiday', 'daylight saving',
                       'sentiment', 'survey', 'preliminary']
            }

        title_lower = title.lower()

        for keyword in impact_keywords.get('high', []):
            if keyword in title_lower:
                return "high"

        for keyword in impact_keywords.get('medium', []):
            if keyword in title_lower:
                return "medium"

        for keyword in impact_keywords.get('low', []):
            if keyword in title_lower:
                return "low"

        return "unknown"


def scrape_date_range(start_date, end_date, config=None):
    """
    Convenience function to scrape a date range

    Args:
        start_date: datetime.date or string (YYYY-MM-DD)
        end_date: datetime.date or string (YYYY-MM-DD)
        config: Optional config dict

    Returns:
        Pandas DataFrame with events
    """
    # Convert strings to dates if needed
    if isinstance(start_date, str):
        start_date = pd.to_datetime(start_date).date()
    if isinstance(end_date, str):
        end_date = pd.to_datetime(end_date).date()

    scraper = ForexFactoryScraperCore(config=config)
    return scraper.scrape_date_range(start_date, end_date)


def scrape_year(year, config=None):
    """
    Convenience function to scrape a full year

    Args:
        year: Integer year
        config: Optional config dict

    Returns:
        Pandas DataFrame with events
    """
    scraper = ForexFactoryScraperCore(config=config)
    return scraper.scrape_year(year)
