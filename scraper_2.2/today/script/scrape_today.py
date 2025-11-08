#!/usr/bin/env python3
"""
ForexFactory Today Scraper - Semantic Structure-Aware Version
Scrapes https://www.forexfactory.com/calendar?day=today
Uses CSS selectors to read HTML semantic structure, not text guessing
Saves to CSV in ../csv_output/
"""

import csv
import time
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Missing required packages")
    print("Install with: pip install -r requirements.txt")
    exit(1)


class ForexFactoryTodayScraper:
    def __init__(self, verbose=True):
        self.base_url = "https://www.forexfactory.com/calendar?day=today"
        self.events = []
        self.driver = None
        self.verbose = verbose
        # Get today's date for fallback
        self.today_date = datetime.now().strftime("%a %b %d")

    # ===== HELPER FUNCTIONS: Semantic HTML Extraction =====

    def detect_timezone(self, soup, page_source):
        """
        Detect timezone from ForexFactory HTML

        Checks multiple indicators:
        1. Settings/footer text mentioning timezone
        2. Meta tags
        3. JavaScript timezone variable
        4. HTML comments with timezone info

        Returns: (timezone_name, utc_offset_hours)
        Example: ("GMT", 0), ("EST", -5), ("IST", 5.5)
        """
        try:
            # Method 1: Search for timezone text in page
            # ForexFactory typically displays "Times are in [TIMEZONE]" somewhere
            timezone_patterns = [
                r'Times are in (\w+)',
                r'Timezone[:\s]+(\w+)',
                r'displayed in (\w+)',
                r'(\w+)\s*time',
                r'([A-Z]{3})\s*\(UTC([+-]\d+(?::\d+)?)\)',
            ]

            for pattern in timezone_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    if self.verbose:
                        print(f"   🔍 Found timezone pattern: {matches}")

            # Method 2: Check HTML for explicit timezone indicators
            # ForexFactory might have timezone in footer or header
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
                # Try to extract from JS
                for pattern in [r"timezone['\"]?\s*[:=]\s*['\"]?(\w+)",
                               r"TZ\s*=\s*['\"]?(\w+)"]:
                    match = re.search(pattern, page_source, re.IGNORECASE)
                    if match:
                        tz_name = match.group(1).upper()
                        if tz_name == "GMT" or tz_name == "UTC":
                            return "GMT", 0
                        elif tz_name == "EST":
                            return "EST", -5
                        elif tz_name == "IST":
                            return "IST", 5.5

            # Default: ForexFactory defaults to GMT
            if self.verbose:
                print("   ⚠️  Could not detect explicit timezone, assuming GMT (ForexFactory default)")

            return "GMT", 0

        except Exception as e:
            if self.verbose:
                print(f"⚠ Error detecting timezone: {e}")
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
            # Parse time - handle both 12-hour and 24-hour formats
            parsed_time = None

            if 'am' in time_str.lower() or 'pm' in time_str.lower():
                # 12-hour format with am/pm
                # Remove extra spaces
                clean_time = re.sub(r'\s+', '', time_str.lower())
                parsed_time = datetime.strptime(clean_time, "%I:%M%p")
            else:
                # 24-hour format
                parsed_time = datetime.strptime(time_str.strip(), "%H:%M")

            # Convert to UTC by subtracting the offset
            # If source is GMT (offset=0), time stays same
            # If source is EST (offset=-5), we add 5 hours to get UTC
            # If source is IST (offset=5.5), we subtract 5.5 hours to get UTC
            utc_time = parsed_time - timedelta(hours=source_tz_offset)

            return utc_time.strftime("%H:%M")

        except Exception as e:
            if self.verbose:
                print(f"⚠ Error converting time '{time_str}' to UTC: {e}")
            return time_str

    def extract_impact(self, impact_cell):
        """
        Extract impact from <td class="calendar__impact">
        Reads span count or CSS color classes (yellow/orange/red)
        Returns: "high", "medium", "low", or ""
        """
        if not impact_cell:
            return ""

        try:
            # Method 1: Count span elements (each represents impact level)
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
            if self.verbose:
                print(f"⚠ Error extracting impact: {e}")

        return ""

    def extract_time(self, time_cell, last_time):
        """
        Extract time from <td class="calendar__time">
        Reads nested <span>, forward-fills if blank
        Keeps special values: "All Day", "Tentative", "Day"
        Returns: time string or last_time for forward-fill
        """
        if not time_cell:
            return last_time

        try:
            time_text = time_cell.get_text(strip=True)

            if not time_text:
                return last_time  # Forward-fill

            # Keep special values
            if time_text in ['All Day', 'Tentative', 'Day', 'off']:
                return time_text

            return time_text

        except Exception as e:
            if self.verbose:
                print(f"⚠ Error extracting time: {e}")
            return last_time

    def extract_actual(self, actual_cell):
        """
        Extract actual value + status from <td class="calendar__actual">
        Reads <span class="better|worse|unchanged">
        Returns: (actual_value, actual_status)
        Status: "better", "worse", "unchanged", ""
        """
        if not actual_cell:
            return "", ""

        try:
            # Look for span with status class
            span = actual_cell.find('span')
            if not span:
                # Fallback: just get cell text
                text = actual_cell.get_text(strip=True)
                return text if text and text != "--" else "", ""

            actual_value = span.get_text(strip=True)

            # Extract status from CSS class
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
            if self.verbose:
                print(f"⚠ Error extracting actual: {e}")
            return "", ""

    def extract_date(self, date_cell):
        """
        Extract and clean date from <td>
        Converts "SatNov 8" → "Sat Nov 8"
        Returns: formatted date string
        """
        if not date_cell:
            return ""

        try:
            date_text = date_cell.get_text(strip=True)

            # Clean up format: "SatNov 8" → "Sat Nov 8"
            day_names = ['Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            for day in day_names:
                if date_text.startswith(day):
                    return day + " " + date_text[len(day):]

            return date_text

        except Exception as e:
            if self.verbose:
                print(f"⚠ Error extracting date: {e}")
            return ""

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
            print("✓ Chrome driver created")
            return driver
        except Exception as e:
            print(f"✗ Error creating driver: {e}")
            return None

    def scrape_today(self):
        """Fetch and parse today's events using semantic structure"""
        print("\n" + "="*70)
        print("FOREXFACTORY TODAY SCRAPER (SEMANTIC STRUCTURE-AWARE)")
        print("="*70)
        print(f"URL: {self.base_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")

        driver = self.get_driver()
        if not driver:
            print("✗ Failed to create driver")
            return False

        try:
            # Navigate to URL
            print("Loading page...")
            driver.get(self.base_url)

            # Wait for page load
            print("Waiting for Cloudflare challenge...")
            time.sleep(3)

            # Wait for content to load
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.CLASS_NAME, "calendar__row")) > 0 or
                              "Just a moment" not in d.page_source
                )
                print("✓ Page loaded successfully")
            except Exception as e:
                print(f"⚠ Timeout waiting for content: {e}")
                pass

            # Extra wait for Cloudflare
            time.sleep(2)

            # Parse HTML
            print("Parsing HTML with semantic selectors...")
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            rows = soup.find_all('tr', class_='calendar__row')
            print(f"Found {len(rows)} calendar rows")

            # Detect timezone
            print("\n🔍 Detecting timezone...")
            detected_tz, utc_offset = self.detect_timezone(soup, driver.page_source)
            print(f"✓ Timezone: {detected_tz} (UTC{utc_offset:+.1f})")
            print()

            # State variables for forward-fill
            current_date = self.today_date
            last_time = ""

            # Extract events using semantic CSS selectors
            for row_idx, row in enumerate(rows):
                try:
                    # Check for day-breaker (date header row)
                    if 'calendar__row--day-breaker' in row.get('class', []):
                        date_cell = row.select_one('td.calendar__cell')
                        if date_cell:
                            current_date = self.extract_date(date_cell)
                        if self.verbose:
                            print(f"   📅 Date header: {current_date}")
                        continue

                    # Skip non-event rows
                    if not row.select_one('td.calendar__event'):
                        continue

                    # Extract using semantic CSS selectors
                    impact_cell = row.select_one('td.calendar__impact')
                    time_cell = row.select_one('td.calendar__time')
                    currency_cell = row.select_one('td.calendar__currency')
                    event_cell = row.select_one('td.calendar__event')
                    actual_cell = row.select_one('td.calendar__actual')
                    forecast_cell = row.select_one('td.calendar__forecast')
                    previous_cell = row.select_one('td.calendar__previous')

                    # Extract values
                    impact = self.extract_impact(impact_cell)
                    current_time = self.extract_time(time_cell, last_time)
                    currency = currency_cell.get_text(strip=True) if currency_cell else ""
                    event_title = event_cell.get_text(strip=True) if event_cell else ""
                    actual, actual_status = self.extract_actual(actual_cell)
                    forecast = forecast_cell.get_text(strip=True) if forecast_cell else ""
                    previous = previous_cell.get_text(strip=True) if previous_cell else ""

                    # Skip if no currency or title
                    if not currency or not event_title:
                        continue

                    # Update last_time for forward-fill
                    if current_time:
                        last_time = current_time

                    # Convert time to UTC
                    time_utc = self.convert_to_utc(current_time, utc_offset) if current_time else ""

                    # Build event dict
                    event = {
                        'Date': current_date,
                        'TimeOriginal': current_time,
                        'TimeZone': detected_tz,
                        'TimeUTC': time_utc,
                        'Currency': currency,
                        'Impact': impact,
                        'Event': event_title,
                        'Actual': actual,
                        'ActualStatus': actual_status,
                        'Forecast': forecast,
                        'Previous': previous
                    }

                    self.events.append(event)

                    # Debug: Print extracted event with UTC conversion
                    if self.verbose:
                        tz_note = f"({current_time}→{time_utc}UTC)" if current_time else ""
                        print(f"   ✓ {event_title[:40]:40} | {current_time:8} | {currency} | Impact={impact} {tz_note} | Actual={actual} ({actual_status})")

                except Exception as e:
                    print(f"⚠ Error parsing row {row_idx}: {e}")
                    continue

            print(f"\n✓ Extracted {len(self.events)} events\n")
            return True

        except Exception as e:
            print(f"✗ Error scraping: {e}")
            return False

        finally:
            try:
                driver.quit()
            except:
                pass

    def save_to_csv(self):
        """Save events to CSV file"""
        if not self.events:
            print("✗ No events to save")
            return False

        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"today_{timestamp}.csv"

        # Get output directory
        output_dir = Path(__file__).parent.parent / "csv_output"
        output_path = output_dir / csv_filename

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write CSV
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Date', 'TimeOriginal', 'TimeZone', 'TimeUTC', 'Currency', 'Impact', 'Event', 'Actual', 'ActualStatus', 'Forecast', 'Previous']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for event in self.events:
                    writer.writerow(event)

            print(f"✓ CSV saved: {csv_filename}")
            print(f"  Location: {output_path}")
            print(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
            print(f"  Records: {len(self.events)}")

            return True

        except Exception as e:
            print(f"✗ Error saving CSV: {e}")
            return False

    def print_summary(self):
        """Print data summary"""
        if not self.events:
            return

        print("\n" + "="*70)
        print("DATA SUMMARY")
        print("="*70)

        # Count by currency
        currencies = {}
        for event in self.events:
            ccy = event.get('Currency', 'Unknown')
            currencies[ccy] = currencies.get(ccy, 0) + 1

        print(f"\nTotal Events: {len(self.events)}")
        print("\nBy Currency:")
        for ccy, count in sorted(currencies.items()):
            pct = (count / len(self.events)) * 100
            print(f"  {ccy:10} {count:5} ({pct:5.1f}%)")

        # Count by impact
        impacts = {}
        for event in self.events:
            imp = event.get('Impact', 'Unknown')
            impacts[imp] = impacts.get(imp, 0) + 1

        print("\nBy Impact Level:")
        for imp, count in sorted(impacts.items()):
            pct = (count / len(self.events)) * 100
            print(f"  {imp:10} {count:5} ({pct:5.1f}%)")

        # Count by actual status
        statuses = {}
        for event in self.events:
            status = event.get('ActualStatus', 'N/A')
            if status:
                statuses[status] = statuses.get(status, 0) + 1

        if statuses:
            print("\nActual Values by Status:")
            for status, count in sorted(statuses.items()):
                pct = (count / len(self.events)) * 100
                print(f"  {status:10} {count:5} ({pct:5.1f}%)")

        # Show first 5 events with timezone info
        print("\nFirst 5 Events (with UTC conversion):")
        for i, event in enumerate(self.events[:5], 1):
            status_str = f" ({event['ActualStatus']})" if event['ActualStatus'] else ""
            tz_info = f"{event['TimeOriginal']} {event['TimeZone']} → {event['TimeUTC']} UTC"
            print(f"  {i}. [{tz_info:25}] {event['Currency']} - {event['Event'][:40]:40} | Actual: {event['Actual']}{status_str}")

        print("\n" + "="*70 + "\n")


def main():
    """Main execution"""
    scraper = ForexFactoryTodayScraper(verbose=True)

    # Scrape
    if not scraper.scrape_today():
        print("✗ Scraping failed")
        return 1

    # Save to CSV
    if not scraper.save_to_csv():
        print("✗ Saving to CSV failed")
        return 1

    # Print summary
    scraper.print_summary()

    print("✓ Done!")
    return 0


if __name__ == '__main__':
    exit(main())
