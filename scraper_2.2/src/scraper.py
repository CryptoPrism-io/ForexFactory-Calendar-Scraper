#!/usr/bin/env python3
"""
ForexFactory Calendar Scraper - Semantic Structure-Aware Version
Scrapes ForexFactory calendar for different periods (today, week, month)
Uses CSS selectors to read HTML semantic structure, not text guessing
Supports URL parameter: ?day=today, ?week=this, ?month=last|this|next
"""

import os
import time
import re
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
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
        self.forced_timezone = os.getenv('SCRAPER_FORCE_TIMEZONE', 'America/Los_Angeles').strip()
        if self.forced_timezone.lower() in ('', 'auto'):
            self.forced_timezone = ""
        self.forced_zoneinfo = None
        self.active_zoneinfo = None
        if self.forced_timezone:
            try:
                self.forced_zoneinfo = ZoneInfo(self.forced_timezone)
            except Exception as exc:
                logger.warning(f"Unable to load timezone {self.forced_timezone}: {exc}")
                self.forced_timezone = ""

    # ===== HELPER FUNCTIONS: Semantic HTML Extraction =====

    def detect_timezone(self, soup, page_source):
        """
        Detect timezone from ForexFactory HTML
        Returns: (timezone_name, utc_offset_hours)
        Example: ("GMT", 0), ("EST", -5), ("IST", 5.5)
        """
        try:
            if self.forced_zoneinfo:
                now_local = datetime.now(self.forced_zoneinfo)
                self.active_zoneinfo = self.forced_zoneinfo
                offset_hours = now_local.utcoffset().total_seconds() / 3600
                tz_label = now_local.tzname() or self.forced_timezone
                logger.info(f"Using forced timezone {self.forced_timezone} ({tz_label})")
                return tz_label, offset_hours

            self.active_zoneinfo = None
            tz_label, tz_offset = self.extract_timezone_from_settings(page_source)
            if tz_label is not None and tz_offset is not None:
                return tz_label, tz_offset

            # Method 1: Search for timezone text in page
            timezone_patterns = [
                r'Times are in (\w+)',
                r'Timezone[:\s]+(\w+)',
                r'displayed in (\w+)',
                r'(\w+)\s*time',
                r'([A-Z]{3})\s*\(UTC([+-]\d+(?::\d+)?)\)',
            ]

            for pattern in timezone_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    tz_candidate = match.group(1).upper()
                    offset_val = self.lookup_offset_from_label(tz_candidate)
                    if offset_val is None and match.lastindex and match.lastindex >= 2:
                        offset_val = self.parse_offset_string(match.group(2))
                    if offset_val is not None:
                        return tz_candidate, offset_val

            # Method 2: Check HTML for explicit timezone indicators
            footer = soup.find('footer')
            header = soup.find('header')

            for section in [footer, header]:
                if section:
                    text = section.get_text().lower()
                    if re.search(r'\bgmt\b', text):
                        return "GMT", 0
                    elif re.search(r'\best\b', text):
                        return "EST", -5
                    elif re.search(r'\bedt\b', text):
                        return "EDT", -4
                    elif re.search(r'\butc\b', text):
                        return "UTC", 0
                    elif re.search(r'\bist\b', text):
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

    def extract_timezone_from_settings(self, page_source):
        """Parse timezone info from embedded FF settings scripts"""
        try:
            timezone_match = re.search(r"timezone:\s*'([^']+)'", page_source)
            tz_name_match = re.search(r"timezone_name:\s*'([^']+)'", page_source)
            user_tz_match = re.search(r"'User Timezone':\s*'([^']+)'", page_source)

            tz_offset = None
            if timezone_match:
                offset_str = timezone_match.group(1).strip()
                offset_str = offset_str.replace('+', '')
                offset_str = re.sub(r'[^0-9\.\-]', '', offset_str)
                if offset_str:
                    tz_offset = float(offset_str)

            tz_name = None
            if tz_name_match:
                tz_name = tz_name_match.group(1).strip()
            elif user_tz_match:
                tz_name = user_tz_match.group(1).strip()

            if tz_offset is not None:
                tz_label = self.format_timezone_label(tz_name, tz_offset)
                return tz_label, tz_offset
        except Exception as e:
            logger.debug(f"Unable to parse timezone from scripts: {e}")

        return None, None

    def lookup_offset_from_label(self, label):
        """Map known timezone abbreviations to offsets"""
        label = label.upper()
        lookup = {
            "GMT": 0,
            "UTC": 0,
            "IST": 5.5,
            "BST": 1,
            "CET": 1,
            "CEST": 2,
            "EET": 2,
            "EEST": 3,
            "EST": -5,
            "EDT": -4,
            "CST": -6,
            "CDT": -5,
            "MST": -7,
            "MDT": -6,
            "PST": -8,
            "PDT": -7,
            "JST": 9,
            "AEST": 10,
            "AEDT": 11,
            "NZT": 12,
        }
        return lookup.get(label)

    def format_timezone_label(self, tz_name, offset):
        """Generate friendly label for timezone"""
        name_map = {
            "Asia/Kolkata": "IST",
            "Asia/Calcutta": "IST",
            "Etc/UTC": "UTC",
            "UTC": "UTC",
            "Europe/London": "GMT",
            "Europe/Berlin": "CET",
            "America/New_York": "EST",
            "America/Chicago": "CST",
            "America/Denver": "MST",
            "America/Los_Angeles": "PST",
            "Asia/Tokyo": "JST",
            "Australia/Sydney": "AEST",
            "Australia/Melbourne": "AEST",
        }

        rounded_offset = round(offset, 2)
        offset_map = {
            0.0: "UTC",
            5.5: "IST",
            -5.0: "EST",
            -4.0: "EDT",
            -6.0: "CST",
            -7.0: "MST",
            -8.0: "PST",
            1.0: "CET",
            2.0: "EET",
            9.0: "JST",
            10.0: "AEST",
            11.0: "AEDT",
        }

        if tz_name:
            normalized = tz_name.strip()
            if normalized in name_map:
                return name_map[normalized]
            if '/' in normalized:
                candidate = normalized.split('/')[-1]
                if len(candidate) <= 5:
                    return candidate.upper()

        if rounded_offset in offset_map:
            return offset_map[rounded_offset]

        sign = "+" if rounded_offset >= 0 else "-"
        return f"UTC{sign}{abs(rounded_offset):g}"

    def parse_offset_string(self, offset_str):
        """Convert textual UTC offset (e.g., +5:30) into float hours"""
        if not offset_str:
            return None
        cleaned = offset_str.strip().replace('UTC', '').replace('+', '')
        sign = -1 if offset_str.strip().startswith('-') else 1
        cleaned = cleaned.lstrip('-')
        parts = cleaned.split(':')
        try:
            hours = float(parts[0]) if parts[0] else 0
            minutes = float(parts[1]) / 60 if len(parts) > 1 else 0
            return sign * (abs(hours) + minutes)
        except ValueError:
            return None

    def convert_to_utc(self, time_str, source_tz_offset, date_iso=None, return_date=False, zoneinfo_obj=None):
        """
        Convert time from source timezone to UTC
        Args:
            time_str: Time string like "1:30am", "13:30", or special values
            source_tz_offset: Hours from UTC (e.g., -5 for EST, 5.5 for IST, 0 for GMT)
        Returns:
            utc_time_str: Time in UTC in 24-hour format (HH:MM)
        """
        if not time_str:
            return (time_str, date_iso) if return_date else time_str

        normalized = time_str.strip()
        lowered = normalized.lower()

        special_tokens = {'all day', 'tentative', 'day', 'off'}
        if lowered in special_tokens:
            return (time_str, date_iso) if return_date else time_str

        # Ignore session labels like "Day 1" or ranges like "19th-24th"
        non_clock_patterns = [
            r'^\d+(st|nd|rd|th)(\s*-\s*\d+(st|nd|rd|th))?$',
            r'^day\s+\d+',
        ]
        for pattern in non_clock_patterns:
            if re.match(pattern, lowered):
                return (time_str, date_iso) if return_date else time_str

        parsed_time = None

        try:
            cleaned = lowered.replace(" ", "")

            if re.match(r'^\d{1,2}:\d{2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I:%M%p")
            elif re.match(r'^\d{1,2}:\d{2}$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%H:%M")
            elif re.match(r'^\d{1,2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I%p")
            else:
                # Not a standard clock time, keep the original value
                return (time_str, date_iso) if return_date else time_str

            if zoneinfo_obj and date_iso:
                try:
                    base_date = datetime.strptime(date_iso, "%Y-%m-%d")
                    local_dt = base_date.replace(hour=parsed_time.hour, minute=parsed_time.minute, tzinfo=zoneinfo_obj)
                    utc_dt = local_dt.astimezone(timezone.utc)
                    utc_time_str = utc_dt.strftime("%H:%M")
                    date_utc = utc_dt.strftime("%Y-%m-%d")
                    tz_label = local_dt.tzname()
                    if return_date:
                        result = (utc_time_str, date_utc, tz_label)
                        return result
                    return utc_time_str
                except Exception as inner_ex:
                    logger.debug(f"ZoneInfo conversion failed for '{time_str}': {inner_ex}")

            utc_time = parsed_time - timedelta(hours=source_tz_offset)
            utc_time_str = utc_time.strftime("%H:%M")

            if return_date and date_iso and parsed_time:
                try:
                    base_date = datetime.strptime(date_iso, "%Y-%m-%d")
                    local_dt = base_date.replace(hour=parsed_time.hour, minute=parsed_time.minute)
                    utc_dt = local_dt - timedelta(hours=source_tz_offset)
                    date_utc = utc_dt.strftime("%Y-%m-%d")
                except Exception as inner_ex:
                    logger.debug(f"Unable to convert '{time_str}' date context: {inner_ex}")
                    date_utc = date_iso
                return utc_time_str, date_utc

            return utc_time_str if not return_date else (utc_time_str, date_iso)

        except Exception as e:
            logger.debug(f"Skipping UTC conversion for '{time_str}': {e}")
            return (time_str, date_iso) if return_date else time_str

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

    def is_cloudflare_challenge(self, page_source):
        """Detect Cloudflare challenge markers in HTML"""
        if not page_source:
            return False

        lowered = page_source.lower()
        challenge_markers = [
            "cf-browser-verification",
            "cf-chl-bypass",
            "challenge-form",
            "cf-please-wait",
            "just a moment",
            "cloudflare",
        ]
        return any(marker in lowered for marker in challenge_markers)

    def wait_for_calendar_ready(self, driver, timeout=120, poll_interval=3):
        """
        Wait for the ForexFactory calendar table to appear while handling Cloudflare challenge pages.
        Returns True when rows are detected, False if timeout is reached.
        """
        end_time = time.time() + timeout
        challenge_logged = False

        while time.time() < end_time:
            page_source = driver.page_source

            if self.is_cloudflare_challenge(page_source):
                if not challenge_logged:
                    logger.info("Cloudflare challenge detected, waiting for clearance...")
                    challenge_logged = True
                time.sleep(poll_interval)
                continue

            try:
                WebDriverWait(driver, poll_interval).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.calendar__table"))
                )
                WebDriverWait(driver, poll_interval).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "calendar__row")) > 0
                )
                logger.info("Calendar table detected with rows present")
                return True
            except TimeoutException:
                if self.verbose:
                    logger.debug("Calendar not ready yet, retrying...")
                time.sleep(poll_interval)

        logger.warning("Cloudflare challenge/ calendar rendering did not finish before timeout")
        return False

    def get_driver(self):
        """Create undetected Chrome driver with Cloudflare bypass"""
        import os

        options = uc.ChromeOptions()
        options.headless = False  # Force real browser window to avoid Cloudflare headless blocking
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        running_ci = os.getenv('CI') or os.getenv('GITHUB_ACTIONS')
        if running_ci:
            display = os.getenv('DISPLAY')
            if not display:
                os.environ['DISPLAY'] = ':99'
                display = ':99'
                logger.info("DISPLAY not set, defaulting to virtual display :99 for CI environment")

            # CI/CD environments use Xvfb virtual display instead of headless mode
            # This helps bypass Cloudflare detection
            logger.info(f"Running with virtual display (CI/CD detected, using Xvfb on DISPLAY={display})")

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

            logger.info("Waiting for Cloudflare challenge / calendar readiness...")
            if not self.wait_for_calendar_ready(driver):
                logger.warning("Page never confirmed calendar readiness; proceeding with whatever HTML is available")

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
            zoneinfo_obj = self.active_zoneinfo
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

                    # Convert date to ISO format (YYYY-MM-DD)
                    date_iso = self.parse_date_to_iso(current_date, period)
                    time_utc = ""
                    date_utc = date_iso
                    event_time_zone = detected_tz

                    if current_time:
                        utc_result = self.convert_to_utc(
                            current_time,
                            utc_offset,
                            date_iso=date_iso,
                            return_date=True,
                            zoneinfo_obj=zoneinfo_obj
                        )
                        if isinstance(utc_result, tuple):
                            if len(utc_result) == 3:
                                maybe_time, maybe_date, maybe_label = utc_result
                                if maybe_time:
                                    time_utc = maybe_time
                                if maybe_date:
                                    date_utc = maybe_date
                                if maybe_label:
                                    event_time_zone = maybe_label
                            elif len(utc_result) == 2:
                                maybe_time, maybe_date = utc_result
                                if maybe_time:
                                    time_utc = maybe_time
                                if maybe_date:
                                    date_utc = maybe_date
                        else:
                            time_utc = utc_result

                    event_uid = self.generate_event_uid(date_iso, currency, event_title)

                    event = {
                        'event_uid': event_uid,
                        'date': date_iso,
                        'time': current_time,
                        'time_zone': event_time_zone,
                        'time_utc': time_utc,
                        'date_utc': date_utc,
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
