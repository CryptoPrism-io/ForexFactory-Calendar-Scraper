#!/usr/bin/env python3
"""
ForexFactory Calendar Scraper - Semantic Structure-Aware Version
Scrapes ForexFactory calendar for different periods (today, week, month)
Uses CSS selectors to read HTML semantic structure, not text guessing
Supports URL parameter: ?day=today, ?week=this, ?month=last|this|next
"""

import time
import re
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError("Missing required packages. Install with: pip install -r requirements.txt")

logger = logging.getLogger(__name__)


class ForexFactoryScraper:
    """Modular ForexFactory Calendar Scraper supporting multiple periods"""

    def __init__(self, verbose=True):
        self.base_url = "https://www.forexfactory.com/calendar"
        self.period_param = None
        self.events = []
        self.driver = None
        self.verbose = verbose
        self.today_date = datetime.now().strftime("%a %b %d")

    # ===== HELPER FUNCTIONS: Semantic HTML Extraction =====

    def detect_timezone(self, soup, page_source):
        """
        Detect timezone from ForexFactory HTML
        Returns: (timezone_name, utc_offset_hours)
        Example: ("GMT", 0), ("EST", -5), ("IST", 5.5)
        """
        try:
            # Method 1: Search for timezone text in page
            timezone_patterns = [
                r'Times are in (\w+)',
                r'Timezone[:\s]+(\w+)',
                r'displayed in (\w+)',
                r'(\w+)\s*time',
                r'([A-Z]{3})\s*\(UTC([+-]\d+(?::\d+)?)\)',
            ]

            for pattern in timezone_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches and self.verbose:
                    logger.debug(f"Found timezone pattern: {matches}")

            # Method 2: Check HTML for explicit timezone indicators
            footer = soup.find('footer')
            header = soup.find('header')

            for section in [footer, header]:
                if section:
                    text = section.get_text().lower()
                    if 'gmt' in text:
                        return "GMT", 0
                    elif 'est' in text or 'edt' in text:
                        return "EST", -5
                    elif 'utc' in text:
                        return "UTC", 0
                    elif 'ist' in text:
                        return "IST", 5.5

            # Method 3: Look for meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').lower()
                if 'timezone' in content or 'gmt' in content or 'utc' in content:
                    if 'ist' in content:
                        return "IST", 5.5
                    elif 'est' in content:
                        return "EST", -5
                    elif 'gmt' in content or 'utc' in content:
                        return "GMT", 0

            # Method 4: Check for JavaScript timezone variable
            if 'timezone:' in page_source.lower():
                for pattern in [r"timezone['\"]?\s*[:=]\s*['\"]?(\w+)",
                               r"TZ\s*=\s*['\"]?(\w+)"]:
                    match = re.search(pattern, page_source, re.IGNORECASE)
                    if match:
                        tz_name = match.group(1).upper()
                        if tz_name in ["GMT", "UTC"]:
                            return "GMT", 0
                        elif tz_name == "EST":
                            return "EST", -5
                        elif tz_name == "IST":
                            return "IST", 5.5

            # Default: ForexFactory defaults to GMT
            if self.verbose:
                logger.warning("Could not detect explicit timezone, assuming GMT (ForexFactory default)")

            return "GMT", 0

        except Exception as e:
            logger.error(f"Error detecting timezone: {e}")
            return "GMT", 0

    def convert_to_utc(self, time_str, source_tz_offset):
        """
        Convert time from source timezone to UTC
        Args:
            time_str: Time string like "1:30am", "13:30", or special values
            source_tz_offset: Hours from UTC (e.g., -5 for EST, 5.5 for IST, 0 for GMT)
        Returns:
            utc_time_str: Time in UTC in 24-hour format (HH:MM)
        """
        if not time_str or time_str in ['All Day', 'Tentative', 'Day', 'off']:
            return time_str

        try:
            parsed_time = None

            if 'am' in time_str.lower() or 'pm' in time_str.lower():
                clean_time = re.sub(r'\s+', '', time_str.lower())
                parsed_time = datetime.strptime(clean_time, "%I:%M%p")
            else:
                parsed_time = datetime.strptime(time_str.strip(), "%H:%M")

            utc_time = parsed_time - timedelta(hours=source_tz_offset)
            return utc_time.strftime("%H:%M")

        except Exception as e:
            logger.error(f"Error converting time '{time_str}' to UTC: {e}")
            return time_str

    def extract_impact(self, impact_cell):
        """Extract impact from <td class="calendar__impact">"""
        if not impact_cell:
            return ""

        try:
            # Method 1: Count span elements
            spans = impact_cell.find_all('span', class_='calendar__impact-icon')
            if spans:
                span_count = len(spans)
                if span_count >= 3:
                    return "high"
                elif span_count == 2:
                    return "medium"
                elif span_count == 1:
                    return "low"

            # Method 2: Check for CSS classes with color names
            classes_str = " ".join(impact_cell.get('class', []))

            if 'red' in classes_str or 'high' in classes_str:
                return "high"
            elif 'orange' in classes_str or 'medium' in classes_str:
                return "medium"
            elif 'yellow' in classes_str or 'low' in classes_str:
                return "low"

            # Method 3: Check span title attribute
            span = impact_cell.find('span')
            if span and span.get('title'):
                title = span['title'].lower()
                if 'high' in title:
                    return "high"
                elif 'medium' in title:
                    return "medium"
                elif 'low' in title:
                    return "low"

        except Exception as e:
            logger.error(f"Error extracting impact: {e}")

        return ""

    def extract_time(self, time_cell, last_time):
        """Extract time from <td class="calendar__time"> with forward-fill"""
        if not time_cell:
            return last_time

        try:
            time_text = time_cell.get_text(strip=True)

            if not time_text:
                return last_time

            if time_text in ['All Day', 'Tentative', 'Day', 'off']:
                return time_text

            return time_text

        except Exception as e:
            logger.error(f"Error extracting time: {e}")
            return last_time

    def extract_actual(self, actual_cell):
        """Extract actual value + status from <td class="calendar__actual">"""
        if not actual_cell:
            return "", ""

        try:
            span = actual_cell.find('span')
            if not span:
                text = actual_cell.get_text(strip=True)
                return text if text and text != "--" else "", ""

            actual_value = span.get_text(strip=True)
            classes = span.get('class', [])
            classes_str = " ".join(classes)

            status = ""
            if 'better' in classes_str:
                status = "better"
            elif 'worse' in classes_str:
                status = "worse"
            elif 'unchanged' in classes_str:
                status = "unchanged"

            return actual_value if actual_value and actual_value != "--" else "", status

        except Exception as e:
            logger.error(f"Error extracting actual: {e}")
            return "", ""

    def extract_date(self, date_cell):
        """Extract and clean date from <td>"""
        if not date_cell:
            return ""

        try:
            date_text = date_cell.get_text(strip=True)

            day_names = ['Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            for day in day_names:
                if date_text.startswith(day):
                    return day + " " + date_text[len(day):]

            return date_text

        except Exception as e:
            logger.error(f"Error extracting date: {e}")
            return ""

    def parse_date_to_iso(self, date_str, period_param="day=today"):
        """
        Parse date string like 'Wed Oct 1' and convert to YYYY-MM-DD format.
        Infers year based on current date and period.

        Args:
            date_str: Date string like "Wed Oct 1" or "Mon Nov 8"
            period_param: Period string (day=today, week=this, month=last|this|next)

        Returns:
            YYYY-MM-DD format string or original if parse fails
        """
        if not date_str or len(date_str.strip()) == 0:
            return date_str

        try:
            from datetime import datetime, timedelta
            import calendar as cal_module

            # Extract month and day from string like "Wed Oct 1"
            parts = date_str.split()
            if len(parts) < 2:
                return date_str

            # Get month and day
            month_str = parts[1]
            day_str = parts[2] if len(parts) > 2 else ""

            if not day_str or not month_str:
                return date_str

            # Parse day
            day = int(day_str)

            # Parse month
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month_str_lower = month_str.lower()
            if month_str_lower not in month_map:
                return date_str

            month = month_map[month_str_lower]

            # Determine year based on period
            now = datetime.now()
            current_year = now.year
            current_month = now.month

            # Infer year based on period
            if 'month=last' in period_param:
                # Last month - if current month is Jan, then last month was Dec of previous year
                if current_month == 1:
                    year = current_year - 1
                    month_of_period = 12
                else:
                    year = current_year
                    month_of_period = current_month - 1

                # If the month we're looking at doesn't match the last month, adjust year
                if month > month_of_period:
                    year = current_year - 1
                elif month < month_of_period:
                    year = current_year

            elif 'month=this' in period_param:
                year = current_year

            elif 'month=next' in period_param:
                # Next month - if current month is Dec, then next month is Jan of next year
                if current_month == 12:
                    year = current_year + 1
                else:
                    year = current_year

                # If month is earlier in calendar year, we might be in next year
                if month < current_month:
                    year = current_year + 1

            elif 'week=' in period_param or 'day=' in period_param:
                year = current_year

            else:
                year = current_year

            # Create date and validate
            try:
                parsed_date = datetime(year, month, day)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                # Invalid day for this month
                return date_str

        except Exception as e:
            logger.debug(f"Error parsing date '{date_str}': {e}")
            return date_str

    def generate_event_uid(self, date, currency, event_title):
        """Generate unique event ID from date, currency, and title"""
        try:
            content = f"{date}|{currency}|{event_title}".encode('utf-8')
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception as e:
            logger.error(f"Error generating event_uid: {e}")
            return None

    def get_driver(self):
        """Create undetected Chrome driver with Cloudflare bypass"""
        import os

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        # CI/CD environments use Xvfb virtual display instead of headless mode
        # This helps bypass Cloudflare detection
        if os.getenv('CI') or os.getenv('GITHUB_ACTIONS'):
            logger.info("Running with virtual display (CI/CD detected, using Xvfb on DISPLAY={})".format(os.getenv('DISPLAY', ':99')))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver = uc.Chrome(options=options, version_main=None, use_subprocess=False)
                logger.info("Chrome driver created successfully")
                return driver
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # Wait before retry
                else:
                    logger.error(f"Failed to create driver after {max_retries} attempts: {e}")
                    return None

    def scrape_period(self, period="day=today"):
        """
        Scrape ForexFactory calendar for a specific period

        Args:
            period: One of:
                - "day=today"
                - "week=this"
                - "month=last"
                - "month=this"
                - "month=next"

        Returns:
            bool: True if successful, False otherwise
        """
        self.period_param = period
        url = f"{self.base_url}?{period}"

        logger.info("\n" + "="*70)
        logger.info("FOREXFACTORY SCRAPER")
        logger.info("="*70)
        logger.info(f"Period: {period}")
        logger.info(f"URL: {url}")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*70 + "\n")

        driver = self.get_driver()
        if not driver:
            logger.error("Failed to create driver")
            return False

        try:
            logger.info("Loading page...")
            driver.get(url)

            logger.info("Waiting for Cloudflare challenge...")
            time.sleep(3)

            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "calendar__row")) > 0 or
                              "Just a moment" not in d.page_source
                )
                logger.info("Page loaded successfully")
            except Exception as e:
                logger.warning(f"Timeout waiting for content: {e}")

            time.sleep(2)

            # Scroll down to load all lazy-loaded events
            # Use SPACE key for natural page-by-page scrolling
            logger.info("Scrolling page to load all events...")
            from selenium.webdriver.common.keys import Keys

            body = driver.find_element("tag name", "body")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 15  # Increased to handle more content

            while scroll_attempts < max_scrolls:
                # Press SPACE to scroll down one page
                body.send_keys(Keys.SPACE)
                time.sleep(0.8)  # Wait for content to load

                # Check if we've reached the bottom
                current_position = driver.execute_script("return window.pageYOffset + window.innerHeight")
                new_height = driver.execute_script("return document.body.scrollHeight")

                if current_position >= new_height - 100:  # Near bottom (within 100px)
                    # Try scrolling once more to be sure
                    body.send_keys(Keys.SPACE)
                    time.sleep(0.8)
                    final_height = driver.execute_script("return document.body.scrollHeight")

                    if final_height == new_height:
                        # No more content, we're done
                        break

                last_height = new_height
                scroll_attempts += 1

                if self.verbose:
                    logger.debug(f"Scroll {scroll_attempts}: Position {current_position}/{new_height}px")

            logger.info(f"Scrolled {scroll_attempts} times to load all content")

            # Scroll back to top for cleaner parsing
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)

            logger.info("Parsing HTML with semantic selectors...")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            rows = soup.find_all('tr', class_='calendar__row')
            logger.info(f"Found {len(rows)} calendar rows")

            logger.info("\nDetecting timezone...")
            detected_tz, utc_offset = self.detect_timezone(soup, driver.page_source)
            logger.info(f"Timezone: {detected_tz} (UTC{utc_offset:+.1f})\n")

            current_date = self.today_date
            last_time = ""

            for row_idx, row in enumerate(rows):
                try:
                    if 'calendar__row--day-breaker' in row.get('class', []):
                        date_cell = row.select_one('td.calendar__cell')
                        if date_cell:
                            current_date = self.extract_date(date_cell)
                        if self.verbose:
                            logger.debug(f"Date header: {current_date}")
                        continue

                    if not row.select_one('td.calendar__event'):
                        continue

                    impact_cell = row.select_one('td.calendar__impact')
                    time_cell = row.select_one('td.calendar__time')
                    currency_cell = row.select_one('td.calendar__currency')
                    event_cell = row.select_one('td.calendar__event')
                    actual_cell = row.select_one('td.calendar__actual')
                    forecast_cell = row.select_one('td.calendar__forecast')
                    previous_cell = row.select_one('td.calendar__previous')

                    impact = self.extract_impact(impact_cell)
                    current_time = self.extract_time(time_cell, last_time)
                    currency = currency_cell.get_text(strip=True) if currency_cell else ""
                    event_title = event_cell.get_text(strip=True) if event_cell else ""
                    actual, actual_status = self.extract_actual(actual_cell)
                    forecast = forecast_cell.get_text(strip=True) if forecast_cell else ""
                    previous = previous_cell.get_text(strip=True) if previous_cell else ""

                    if not currency or not event_title:
                        continue

                    if current_time:
                        last_time = current_time

                    time_utc = self.convert_to_utc(current_time, utc_offset) if current_time else ""

                    # Convert date to ISO format (YYYY-MM-DD)
                    date_iso = self.parse_date_to_iso(current_date, period)
                    event_uid = self.generate_event_uid(date_iso, currency, event_title)

                    event = {
                        'event_uid': event_uid,
                        'date': date_iso,
                        'time': current_time,
                        'time_zone': detected_tz,
                        'time_utc': time_utc,
                        'currency': currency,
                        'impact': impact,
                        'event': event_title,
                        'actual': actual,
                        'actual_status': actual_status,
                        'forecast': forecast,
                        'previous': previous,
                        'source_scope': period.split('=')[0]
                    }

                    self.events.append(event)

                    if self.verbose:
                        tz_note = f"({current_time}→{time_utc}UTC)" if current_time else ""
                        logger.debug(f"✓ {event_title[:40]:40} | {current_time:8} | {currency} | Impact={impact} {tz_note} | Actual={actual} ({actual_status})")

                except Exception as e:
                    logger.error(f"Error parsing row {row_idx}: {e}")
                    continue

            logger.info(f"\n✓ Extracted {len(self.events)} events\n")
            return True

        except Exception as e:
            logger.error(f"Error scraping: {e}")
            return False

        finally:
            try:
                driver.quit()
            except:
                pass

    def get_events(self):
        """Return scraped events"""
        return self.events

    def clear_events(self):
        """Clear events list for next scrape"""
        self.events = []
