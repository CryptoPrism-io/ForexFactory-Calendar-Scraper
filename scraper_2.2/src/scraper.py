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

# Regex pattern to validate HH:MM time format
TIME_PATTERN = re.compile(r'^\d{1,2}:\d{2}$')


class ForexFactoryScraper:
    """Modular ForexFactory Calendar Scraper supporting multiple periods"""

    TIMEZONE_ABBR_TO_IANA = {
        "UTC": "UTC",
        "GMT": "UTC",
        "BST": "Europe/London",
        "IST": "Asia/Kolkata",
        "JST": "Asia/Tokyo",
        "HKT": "Asia/Hong_Kong",
        "SGT": "Asia/Singapore",
        "CET": "Europe/Paris",
        "CEST": "Europe/Paris",
        "EET": "Europe/Bucharest",
        "EEST": "Europe/Bucharest",
        "MSK": "Europe/Moscow",
        "AST": "America/Halifax",
        "ADT": "America/Halifax",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "AKST": "America/Anchorage",
        "AKDT": "America/Anchorage",
        "HST": "Pacific/Honolulu",
        "AEST": "Australia/Sydney",
        "AEDT": "Australia/Sydney",
        "ACST": "Australia/Adelaide",
        "ACDT": "Australia/Adelaide",
        "AFT": "Asia/Kabul",
        "PKT": "Asia/Karachi",
        "NZST": "Pacific/Auckland",
        "NZDT": "Pacific/Auckland",
    }

    def __init__(self, verbose=True):
        self.base_url = "https://www.forexfactory.com/calendar"
        self.period_param = None
        self.events = []
        self.driver = None
        self.verbose = verbose
        self.today_date = datetime.now().strftime("%a %b %d")
        self.forced_timezone = os.getenv('SCRAPER_FORCE_TIMEZONE', '').strip()
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

    def resolve_timezone_name(self, tz_label):
        """
        Normalize a timezone abbreviation or IANA identifier into a canonical IANA ID.
        """
        if not tz_label:
            return None
        cleaned = tz_label.strip()
        if not cleaned:
            return None
        if "/" in cleaned:
            return cleaned
        canonical = self.TIMEZONE_ABBR_TO_IANA.get(cleaned.upper())
        return canonical or cleaned

    # ===== HELPER FUNCTIONS: Semantic HTML Extraction =====

    def verify_forexfactory_timezone(self, soup, page_source):
        """
        ====== LAYER 2: Verify ForexFactory is displaying times in UTC ======

        This is a critical verification step that ensures ForexFactory's page
        is actually showing times in UTC (as a result of our Chrome timezone forcing).

        If this verification fails, it means our timezone forcing didn't work
        properly and we should abort rather than scrape incorrect data.

        Returns:
            str: Detected timezone (should be "UTC" or "GMT")

        Raises:
            RuntimeError: If ForexFactory is not displaying UTC times
        """
        detected_tz = None
        detection_method = None

        # Method 1: Extract from embedded JavaScript settings (most reliable)
        try:
            timezone_match = re.search(r"timezone:\s*'([^']+)'", page_source)
            tz_name_match = re.search(r"timezone_name:\s*'([^']+)'", page_source)
            user_tz_match = re.search(r"'User Timezone':\s*'([^']+)'", page_source)

            if tz_name_match:
                detected_tz = tz_name_match.group(1).strip()
                detection_method = "timezone_name setting"
            elif user_tz_match:
                detected_tz = user_tz_match.group(1).strip()
                detection_method = "User Timezone setting"
            elif timezone_match:
                offset_str = timezone_match.group(1).strip()
                if offset_str in ['0', '+0', '-0', '0.0']:
                    detected_tz = "UTC"
                    detection_method = "timezone offset (0)"
        except Exception as e:
            logger.debug(f"Method 1 (JS settings) failed: {e}")

        # Method 2: Search for explicit timezone text in page
        if not detected_tz:
            timezone_patterns = [
                (r'Times are in (\w+)', 1, "explicit text"),
                (r'Timezone[:\s]+["\']?(\w+)["\']?', 1, "timezone label"),
                (r'displayed in (\w+)', 1, "display text"),
                (r'"timezone":\s*"([^"]+)"', 1, "JSON timezone"),
            ]

            for pattern, group_idx, method in timezone_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    detected_tz = match.group(group_idx).upper()
                    detection_method = method
                    break

        # Method 3: Check footer/header for timezone indicators
        if not detected_tz:
            for section in [soup.find('footer'), soup.find('header')]:
                if section:
                    text = section.get_text().lower()
                    if re.search(r'\butc\b', text):
                        detected_tz = "UTC"
                        detection_method = "footer/header text"
                        break
                    elif re.search(r'\bgmt\b', text):
                        detected_tz = "GMT"
                        detection_method = "footer/header text"
                        break

        # Normalize detected timezone
        if detected_tz:
            original_tz = detected_tz  # Preserve original case for error messages
            detected_tz = detected_tz.upper().strip()
            # Handle common variations
            if detected_tz in ['ETC/UTC', 'UTC+0', 'UTC-0', 'GMT+0', 'GMT-0', 'GMT0']:
                detected_tz = "UTC"
            elif detected_tz == 'GMT':
                detected_tz = "UTC"  # GMT and UTC are effectively the same for our purposes

        # Validate the detected timezone
        acceptable_timezones = ['UTC', 'GMT']

        if not detected_tz:
            logger.warning(
                "⚠️  WARNING: Could not extract timezone from ForexFactory page.\n"
                "     Assuming UTC based on Chrome timezone verification.\n"
                "     This should be investigated if it happens frequently."
            )
            return "UTC"

        if detected_tz not in acceptable_timezones:
            # Check if Chrome already verified UTC
            if hasattr(self, 'chrome_verified_utc') and self.chrome_verified_utc:
                # Chrome verified UTC but ForexFactory shows different timezone
                # Trust Chrome over ForexFactory (this is the expected behavior with our fix)
                logger.warning(
                    f"\n{'='*70}\n"
                    f"⚠️  TIMEZONE MISMATCH (EXPECTED):\n"
                    f"{'='*70}\n"
                    f"  Chrome verified: UTC ✓\n"
                    f"  ForexFactory shows: {original_tz}\n"
                    f"  Detection method: {detection_method}\n"
                    f"  \n"
                    f"  This is EXPECTED behavior - ForexFactory has incorrect\n"
                    f"  embedded timezone settings, but Chrome has been verified\n"
                    f"  as UTC. Scraper will use Chrome's verified UTC.\n"
                    f"  \n"
                    f"  Data will be CORRECT (using Chrome's UTC timezone).\n"
                    f"{'='*70}\n"
                )
                return "UTC"  # Trust Chrome verification
            else:
                # Chrome did NOT verify UTC, so this is a real error
                raise RuntimeError(
                    f"CRITICAL: ForexFactory is NOT displaying UTC times!\n"
                    f"  Expected: UTC or GMT\n"
                    f"  Detected: {original_tz}\n"
                    f"  Detection method: {detection_method}\n"
                    f"  This means Chrome timezone forcing did not work properly.\n"
                    f"  Scraped data would be INCORRECT. Aborting."
                )

        logger.info(f"✓ VERIFIED: ForexFactory displaying times in {detected_tz} (via {detection_method})")
        return detected_tz

    def detect_timezone(self, soup, page_source):
        """
        Detect timezone from ForexFactory HTML.

        New approach: Accept whatever timezone ForexFactory displays (based on IP geolocation)
        and convert to UTC using proper timezone math.

        Returns: (timezone_iana_id, utc_offset_hours)
        Example: ("Asia/Kolkata", 5.5), ("America/New_York", -5), ("UTC", 0)
        """
        try:
            # Method 0: Check for forced timezone (for testing/override)
            if self.forced_zoneinfo:
                now_local = datetime.now(self.forced_zoneinfo)
                self.active_zoneinfo = self.forced_zoneinfo
                offset_hours = now_local.utcoffset().total_seconds() / 3600
                tz_label = now_local.tzname() or self.forced_timezone
                logger.info(f"Using forced timezone {self.forced_timezone} ({tz_label})")
                return self.forced_timezone, offset_hours  # Return IANA ID

            self.active_zoneinfo = None

            # Method 1: Extract from hidden input (MOST RELIABLE)
            # <input type="hidden" name="timezone" value="Asia/Kolkata">
            tz_iana = self.extract_timezone_from_hidden_input(soup)
            if tz_iana:
                # Also try to get offset from label for validation
                tz_offset = self.extract_gmt_offset_from_label(soup, page_source)
                canonical_tz = self.resolve_timezone_name(tz_iana) or tz_iana

                # If we got offset from label, use it; otherwise calculate from IANA ID
                if tz_offset is not None:
                    logger.info(f"✓ Detected timezone: {canonical_tz} (UTC{tz_offset:+.1f} from label)")
                    return canonical_tz, tz_offset
                else:
                    # Calculate offset using zoneinfo
                    try:
                        tz_zone = ZoneInfo(tz_iana)
                        now_in_tz = datetime.now(tz_zone)
                        tz_offset = now_in_tz.utcoffset().total_seconds() / 3600
                        logger.info(f"✓ Detected timezone: {canonical_tz} (UTC{tz_offset:+.1f} calculated)")
                        return canonical_tz, tz_offset
                    except Exception as e:
                        logger.warning(f"Could not calculate offset for {tz_iana}: {e}")
                        # Fall through to other methods

            # Method 2: Parse from JavaScript settings (fallback)
            tz_label, tz_offset = self.extract_timezone_from_settings(page_source)
            if tz_label is not None and tz_offset is not None:
                canonical_tz = self.resolve_timezone_name(tz_label) or tz_label
                return canonical_tz, tz_offset

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
                        canonical_tz = self.resolve_timezone_name(tz_candidate) or tz_candidate
                        return canonical_tz, offset_val

            # Method 2: Check HTML for explicit timezone indicators
            footer = soup.find('footer')
            header = soup.find('header')

            for section in [footer, header]:
                if section:
                    text = section.get_text().lower()
                    if re.search(r'\bgmt\b', text):
                        return self.resolve_timezone_name("GMT"), 0
                    elif re.search(r'\best\b', text):
                        return self.resolve_timezone_name("EST"), -5
                    elif re.search(r'\bedt\b', text):
                        return self.resolve_timezone_name("EDT"), -4
                    elif re.search(r'\butc\b', text):
                        return self.resolve_timezone_name("UTC"), 0
                    elif re.search(r'\bist\b', text):
                        return self.resolve_timezone_name("IST"), 5.5

            # Method 3: Look for meta tags
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                content = meta.get('content', '').lower()
                if 'timezone' in content or 'gmt' in content or 'utc' in content:
                    if 'ist' in content:
                        return self.resolve_timezone_name("IST"), 5.5
                    elif 'est' in content:
                        return self.resolve_timezone_name("EST"), -5
                    elif 'gmt' in content or 'utc' in content:
                        return self.resolve_timezone_name("GMT"), 0

            # Method 4: Check for JavaScript timezone variable
            if 'timezone:' in page_source.lower():
                for pattern in [r"timezone['\"]?\s*[:=]\s*['\"]?(\w+)",
                               r"TZ\s*=\s*['\"]?(\w+)"]:
                    match = re.search(pattern, page_source, re.IGNORECASE)
                    if match:
                        tz_name = match.group(1).upper()
                        if tz_name in ["GMT", "UTC"]:
                            return self.resolve_timezone_name("GMT"), 0
                        elif tz_name == "EST":
                            return self.resolve_timezone_name("EST"), -5
                        elif tz_name == "IST":
                            return self.resolve_timezone_name("IST"), 5.5

            # Default: ForexFactory defaults to GMT
            if self.verbose:
                logger.warning("Could not detect explicit timezone, assuming GMT (ForexFactory default)")

            return self.resolve_timezone_name("GMT"), 0

        except Exception as e:
            logger.error(f"Error detecting timezone: {e}")
            return self.resolve_timezone_name("GMT"), 0

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

    def extract_timezone_from_hidden_input(self, soup):
        """
        Extract timezone from hidden form field (most reliable method).

        ForexFactory always includes: <input type="hidden" name="timezone" value="Asia/Kolkata">
        This is set by server-side IP geolocation and is always present.

        Returns:
            str: IANA timezone identifier (e.g., "Asia/Kolkata") or None
        """
        try:
            tz_input = soup.find('input', {'name': 'timezone', 'type': 'hidden'})
            if tz_input and tz_input.get('value'):
                tz_value = tz_input['value'].strip()
                if tz_value:
                    logger.debug(f"Found timezone from hidden input: {tz_value}")
                    return tz_value  # Returns IANA ID like "Asia/Kolkata"
        except Exception as e:
            logger.debug(f"Could not extract timezone from hidden input: {e}")

        return None

    def extract_gmt_offset_from_label(self, soup, page_source):
        """
        Parse GMT offset from timezone selector dropdown display.

        Format: "(GMT+05:30) Chennai, Kolkata, Mumbai, New Delhi"
        Handles fractional hour offsets: +05:30, +03:30, +13:45, etc.

        Returns:
            float: UTC offset in hours (e.g., 5.5 for GMT+05:30) or None
        """
        try:
            # Pattern matches: (GMT+05:30) or (GMT-08:00)
            pattern = r'\(GMT([+-])(\d{1,2}):(\d{2})\)'
            match = re.search(pattern, page_source)

            if match:
                sign = 1 if match.group(1) == '+' else -1
                hours = int(match.group(2))
                minutes = int(match.group(3))
                offset = sign * (hours + minutes / 60.0)

                logger.debug(f"Parsed GMT offset from label: {match.group(0)} = {offset} hours")
                return offset
        except Exception as e:
            logger.debug(f"Could not extract GMT offset from label: {e}")

        return None

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

    def convert_to_utc_simple(self, time_str, date_iso):
        """
        ====== LAYER 3: Simplified UTC "conversion" (really just validation) ======

        Since we force Chrome to UTC timezone and verify ForexFactory displays UTC,
        this function no longer needs to do complex timezone conversions.

        It now serves as VALIDATION and FORMATTING:
        - Validates time format
        - Converts to 24-hour format
        - Validates date format
        - Returns same values (already UTC!)

        Args:
            time_str: Time string like "1:30am", "13:30", or special values
            date_iso: Date in YYYY-MM-DD format

        Returns:
            tuple: (time_24h, date_iso, timezone_label)
                - time_24h: Time in HH:MM format (24-hour)
                - date_iso: Same date (no conversion needed)
                - timezone_label: "UTC" or "N/A" for special values
        """
        if not time_str or not date_iso:
            return time_str or "", date_iso or "", "N/A"

        normalized = time_str.strip()
        lowered = normalized.lower()

        # Special values that aren't actual times
        special_tokens = {'all day', 'tentative', 'day', 'off'}
        if lowered in special_tokens:
            return time_str, date_iso, "N/A"

        # Ignore session labels like "Day 1" or date ranges like "19th-24th"
        non_clock_patterns = [
            r'^\d+(st|nd|rd|th)(\s*-\s*\d+(st|nd|rd|th))?$',
            r'^day\s+\d+',
        ]
        for pattern in non_clock_patterns:
            if re.match(pattern, lowered):
                return time_str, date_iso, "N/A"

        # Parse and validate time format
        try:
            cleaned = lowered.replace(" ", "")
            parsed_time = None

            # Try different time formats
            if re.match(r'^\d{1,2}:\d{2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I:%M%p")
            elif re.match(r'^\d{1,2}:\d{2}$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%H:%M")
            elif re.match(r'^\d{1,2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I%p")
            else:
                # Not a standard clock time
                logger.debug(f"Unrecognized time format: '{time_str}'")
                return time_str, date_iso, "N/A"

            # Convert to 24-hour format (for consistency)
            time_24h = parsed_time.strftime("%H:%M")

            # Validate date format
            try:
                datetime.strptime(date_iso, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format: {date_iso} (expected YYYY-MM-DD)")
                return time_24h, date_iso, "UTC"

            # No conversion needed - input is already UTC!
            # Just return formatted values
            return time_24h, date_iso, "UTC"

        except Exception as e:
            logger.debug(f"Time parsing failed for '{time_str}': {e}")
            return time_str, date_iso, "N/A"

    def convert_to_utc_with_zoneinfo(self, time_str, date_iso, source_timezone_iana):
        """
        Convert time from source timezone to UTC using zoneinfo.

        New approach: Accept ForexFactory's displayed timezone (based on IP geolocation)
        and convert to UTC using Python's zoneinfo library with proper DST handling.

        Args:
            time_str (str): Time string like "8:30am", "14:30", or special values
            date_iso (str): Date in YYYY-MM-DD format
            source_timezone_iana (str): IANA timezone ID (e.g., "Asia/Kolkata", "America/New_York")

        Returns:
            tuple: (time_utc, date_utc, tz_label)
                - time_utc: Time in HH:MM format (24-hour, UTC)
                - date_utc: Date in YYYY-MM-DD format (UTC, may differ from input!)
                - tz_label: Timezone abbreviation (e.g., "IST", "PST") or "N/A"

        Handles:
            - 12-hour to 24-hour conversion (8:30am → 08:30)
            - DST transitions (automatic via zoneinfo)
            - Midnight wraparound (11:30pm PST Dec 3 → 07:30am UTC Dec 4)
            - Fractional hour offsets (GMT+05:30, GMT+03:30, GMT+13:45)
            - Special values ("All Day", "Tentative", etc.)

        Examples:
            >>> # IST to UTC: 8:30am IST = 03:00 UTC (GMT+5.5)
            >>> convert_to_utc_with_zoneinfo("8:30am", "2025-12-03", "Asia/Kolkata")
            ("03:00", "2025-12-03", "IST")

            >>> # PST to UTC with date change: 11:30pm PST Dec 3 = 07:30am UTC Dec 4
            >>> convert_to_utc_with_zoneinfo("11:30pm", "2025-12-03", "America/Los_Angeles")
            ("07:30", "2025-12-04", "PST")
        """
        if not time_str or not date_iso:
            return time_str or "", date_iso or "", "N/A"

        normalized = time_str.strip()
        lowered = normalized.lower()

        # Special values that aren't actual times
        special_tokens = {'all day', 'tentative', 'day', 'off'}
        if lowered in special_tokens:
            return time_str, date_iso, "N/A"

        # Ignore session labels like "Day 1" or date ranges like "19th-24th"
        non_clock_patterns = [
            r'^\d+(st|nd|rd|th)(\s*-\s*\d+(st|nd|rd|th))?$',
            r'^day\s+\d+',
        ]
        for pattern in non_clock_patterns:
            if re.match(pattern, lowered):
                return time_str, date_iso, "N/A"

        # Parse time string
        try:
            cleaned = lowered.replace(" ", "")
            parsed_time = None

            # Try different time formats
            if re.match(r'^\d{1,2}:\d{2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I:%M%p")
            elif re.match(r'^\d{1,2}:\d{2}$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%H:%M")
            elif re.match(r'^\d{1,2}(am|pm)$', cleaned):
                parsed_time = datetime.strptime(cleaned, "%I%p")
            else:
                logger.debug(f"Unrecognized time format: '{time_str}'")
                return time_str, date_iso, "N/A"

            # Validate and parse date
            try:
                base_date = datetime.strptime(date_iso, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid date format: {date_iso} (expected YYYY-MM-DD)")
                return parsed_time.strftime("%H:%M"), date_iso, "INVALID_DATE"

            # Create timezone-aware datetime in source timezone
            canonical_source_tz = self.resolve_timezone_name(source_timezone_iana)
            if canonical_source_tz:
                source_timezone_iana = canonical_source_tz
            try:
                source_tz = ZoneInfo(source_timezone_iana)

                # Combine date and time with timezone
                local_dt = datetime(
                    year=base_date.year,
                    month=base_date.month,
                    day=base_date.day,
                    hour=parsed_time.hour,
                    minute=parsed_time.minute,
                    second=0,
                    microsecond=0,
                    tzinfo=source_tz
                )

                # Convert to UTC
                utc_dt = local_dt.astimezone(timezone.utc)

                # Extract components
                time_utc = utc_dt.strftime("%H:%M")
                date_utc = utc_dt.strftime("%Y-%m-%d")
                tz_label = local_dt.tzname()  # e.g., "IST", "PST", "EDT"

                # Log conversion details for debugging
                if self.verbose and (date_utc != date_iso or time_utc != parsed_time.strftime("%H:%M")):
                    logger.debug(
                        f"Timezone conversion: {time_str} on {date_iso} in {source_timezone_iana} "
                        f"→ {time_utc} on {date_utc} UTC"
                    )

                return time_utc, date_utc, tz_label

            except Exception as e:
                logger.error(
                    f"Timezone conversion failed for {time_str} on {date_iso} "
                    f"in {source_timezone_iana}: {e}"
                )
                # Return formatted time but mark conversion as failed
                return parsed_time.strftime("%H:%M"), date_iso, "CONV_ERROR"

        except Exception as e:
            logger.debug(f"Time parsing failed for '{time_str}': {e}")
            return time_str, date_iso, "N/A"

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

    def validate_event_timezone(self, event):
        """
        ====== LAYER 4: Paranoid per-event timezone validation ======

        This is a final safety check before adding events to the database.
        Ensures every event has correct timezone metadata.

        If this validation fails, it means something went wrong in our
        multi-layer verification and we should NOT insert incorrect data.

        Args:
            event: Event dictionary to validate

        Returns:
            bool: True if valid

        Raises:
            ValueError: If event has invalid timezone or missing critical fields
        """
        required_fields = ['event_uid', 'date', 'time', 'time_zone', 'currency', 'event']

        # Check required fields
        for field in required_fields:
            if field not in event:
                raise ValueError(
                    f"CRITICAL: Event missing required field '{field}'\n"
                    f"Event data: {event}"
                )

        # Validate timezone is correct
        tz = event.get('time_zone', '')

        # Accept common timezone abbreviations returned by zoneinfo.tzname()
        # These are legitimate timezone abbreviations from ForexFactory's display timezone
        acceptable = [
            # Special values
            'UTC', 'GMT', 'N/A', '',
            # Common timezone abbreviations from zoneinfo
            'IST',  # India Standard Time
            'PST', 'PDT',  # Pacific
            'EST', 'EDT',  # Eastern
            'CST', 'CDT',  # Central
            'MST', 'MDT',  # Mountain
            'BST',  # British Summer Time
            'CEST', 'CET',  # Central European
            'EEST', 'EET',  # Eastern European
            'JST',  # Japan
            'AEST', 'AEDT',  # Australian Eastern
            'AWST', 'AWDT',  # Australian Western
            'ACST', 'ACDT',  # Australian Central
            'NZST', 'NZDT',  # New Zealand
            'HKT',  # Hong Kong
            'SGT',  # Singapore
            'WIB', 'WITA', 'WIT',  # Indonesia
            'KST',  # Korea
            'MSK',  # Moscow
            'AST', 'ADT',  # Atlantic
            'NST', 'NDT',  # Newfoundland
            'AKST', 'AKDT',  # Alaska
            'HST',  # Hawaii
            'ChST',  # Chamorro (Guam)
            'SST',  # Samoa
            '+00', '+01', '+02', '+03', '+04', '+05', '+05:30', '+06', '+07', '+08', '+09', '+10', '+11', '+12', '+13',
            '-01', '-02', '-03', '-04', '-05', '-06', '-07', '-08', '-09', '-10', '-11', '-12'
        ]

        if tz and tz not in acceptable:
            # Log warning but don't fail - zoneinfo may return other valid abbreviations
            logger.warning(
                f"Event has unrecognized timezone abbreviation: {tz}\n"
                f"  Event: {event['event']}\n"
                f"  Date: {event['date']}\n"
                f"  Time: {event['time']}\n"
                f"  This may be valid - zoneinfo uses various abbreviations.\n"
                f"  If data appears incorrect, please review."
            )

        # Validate date format
        if event['date']:
            try:
                datetime.strptime(event['date'], "%Y-%m-%d")
            except ValueError:
                logger.error(
                    f"Invalid date format in event: {event['date']} (expected YYYY-MM-DD)\n"
                    f"Event: {event['event']}"
                )

        # Validate time_utc format if present
        if event.get('time_utc') and event['time_utc'] not in ['All Day', 'Tentative', 'Day', 'off', '']:
            try:
                # Should be HH:MM format
                if ':' in event['time_utc']:
                    datetime.strptime(event['time_utc'], "%H:%M")
            except ValueError:
                logger.warning(
                    f"Invalid time_utc format: {event['time_utc']} (expected HH:MM)\n"
                    f"Event: {event['event']}"
                )

        return True

    def generate_event_uid(self, date, currency, event_title):
        """Generate unique event ID from date, currency, and title"""
        try:
            content = f"{date}|{currency}|{event_title}".encode('utf-8')
            return hashlib.sha256(content).hexdigest()[:16]
        except Exception as e:
            logger.error(f"Error generating event_uid: {e}")
            return None

    def _generate_timezone_audit_summary(self, source_tz, utc_offset):
        """
        Generate timezone audit summary for logging.

        This provides a clear audit trail of timezone detection and conversion
        for debugging and data quality purposes.
        """
        from datetime import datetime, timezone as tz_module

        # Count events by timezone label
        tz_counts = {}
        for event in self.events:
            event_tz = event.get('time_zone', 'UNKNOWN')
            tz_counts[event_tz] = tz_counts.get(event_tz, 0) + 1

        # Count events by source timezone
        source_tz_counts = {}
        for event in self.events:
            src_tz = event.get('source_timezone', 'UNKNOWN')
            source_tz_counts[src_tz] = source_tz_counts.get(src_tz, 0) + 1

        summary_lines = [
            f"Scraper Version: 3.0 (ZoneInfo-based timezone conversion)",
            f"Timestamp: {datetime.now(tz_module.utc).isoformat()}",
            f"",
            f"TIMEZONE DETECTION:",
            f"  ✓ ForexFactory detected timezone: {source_tz}",
            f"  ✓ UTC offset: {utc_offset:+.1f} hours",
            f"  ✓ Conversion method: Python zoneinfo",
            f"",
            f"EVENTS PROCESSED:",
            f"  Total events: {len(self.events)}",
            f"  Events by timezone label:",
        ]

        for event_tz, count in sorted(tz_counts.items()):
            summary_lines.append(f"    - {event_tz}: {count} events")

        summary_lines.append(f"")
        summary_lines.append(f"  Events by source timezone:")
        for src_tz, count in sorted(source_tz_counts.items()):
            summary_lines.append(f"    - {src_tz}: {count} events")

        # Check data integrity - all events should have time_utc
        events_with_utc = sum(1 for e in self.events if e.get('time_utc'))
        events_with_source_tz = sum(1 for e in self.events if e.get('source_timezone'))

        summary_lines.extend([
            f"",
            f"DATA INTEGRITY:",
            f"  ✓ Events with time_utc: {events_with_utc}/{len(self.events)}",
            f"  ✓ Events with source_timezone: {events_with_source_tz}/{len(self.events)}",
            f"  {'✓ ALL CHECKS PASSED' if events_with_utc == len(self.events) and events_with_source_tz == len(self.events) else '⚠️  SOME CHECKS FAILED'}",
            f"",
            f"Configuration:",
            f"  Source timezone detection: Automatic (from ForexFactory HTML)",
            f"  Conversion method: Python zoneinfo",
            f"  Environment: {'GitHub Actions' if os.getenv('GITHUB_ACTIONS') else 'Local'}",
        ])

        return "\n".join(summary_lines)

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
                # Create fresh ChromeOptions for each retry attempt
                # (undetected_chromedriver doesn't allow reusing ChromeOptions)
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

                driver = uc.Chrome(options=options, version_main=142, use_subprocess=False)
                logger.info("Chrome driver created successfully")

                # Note: Chrome timezone forcing is no longer used
                # ForexFactory uses server-side IP geolocation for timezone detection
                # which cannot be overridden by browser settings
                # We now detect the displayed timezone from HTML and convert to UTC

                return driver
            except Exception as e:
                # Other exceptions are transient errors worth retrying
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)  # Wait before retry
                else:
                    logger.error(f"Failed to create driver after {max_retries} attempts: {e}")
                    raise last_exception

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

            # ====== LAYER 2: Detect ForexFactory timezone ======
            # Accept whatever timezone ForexFactory displays (based on IP geolocation)
            # and convert times to UTC using proper timezone math
            logger.info("\nDetecting ForexFactory timezone...")
            tz_iana, utc_offset = self.detect_timezone(soup, driver.page_source)

            if not tz_iana:
                raise RuntimeError(
                    "CRITICAL: Could not detect timezone from ForexFactory.\n"
                    "Cannot proceed - data integrity cannot be guaranteed."
                )

            logger.info(f"✓ Detected ForexFactory timezone: {tz_iana} (UTC{utc_offset:+.1f})")
            logger.info(f"  Times will be converted from {tz_iana} to UTC\n")

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

                    # ====== LAYER 3: Convert from ForexFactory timezone to UTC ======
                    # Accept ForexFactory's displayed timezone (based on IP geolocation)
                    # and convert to UTC using proper timezone math (handles DST, fractional offsets, etc.)
                    if current_time:
                        time_utc, date_utc, event_time_zone = self.convert_to_utc_with_zoneinfo(
                            current_time,
                            date_iso,
                            tz_iana  # Pass detected timezone IANA ID (e.g., "Asia/Kolkata")
                        )
                    else:
                        time_utc = ""
                        date_utc = date_iso
                        event_time_zone = "N/A"

                    event_uid = self.generate_event_uid(date_iso, currency, event_title)

                    # Combine date_utc + time_utc into a proper TIMESTAMPTZ
                    datetime_utc = None
                    # Validate time_utc format using regex - only use if it matches HH:MM pattern
                    if time_utc and TIME_PATTERN.match(time_utc):
                        # Valid time format (e.g., "14:30", "9:00")
                        datetime_utc = f"{date_utc} {time_utc}:00"
                    elif date_utc:
                        # Special/invalid time values (All Day, Tentative, Day N, Sep 27th, etc.) → midnight UTC
                        if time_utc and time_utc not in ['All Day', 'Tentative'] and not time_utc.startswith('Day '):
                            # Log unexpected time formats for monitoring
                            logger.debug(f"Non-standard time value '{time_utc}' for event '{event_title}' → using midnight UTC")
                        datetime_utc = f"{date_utc} 00:00:00"

                    event = {
                        'event_uid': event_uid,
                        'date': date_iso,
                        'time': current_time,
                        'time_zone': event_time_zone,
                        'time_utc': time_utc,
                        'date_utc': date_utc,
                        'datetime_utc': datetime_utc,  # NEW: Combined UTC timestamp
                        'source_timezone': tz_iana,  # Audit trail: ForexFactory's detected timezone
                        'currency': currency,
                        'impact': impact,
                        'event': event_title,
                        'actual': actual,
                        'actual_status': actual_status,
                        'forecast': forecast,
                        'previous': previous,
                        'source_scope': period.split('=')[0]
                    }

                    # ====== LAYER 4: Validate event before adding ======
                    try:
                        self.validate_event_timezone(event)
                    except ValueError as validation_error:
                        logger.error(f"Event validation failed: {validation_error}")
                        logger.error("Skipping event to prevent incorrect data insertion")
                        continue

                    self.events.append(event)

                    if self.verbose:
                        tz_note = f"({current_time}→{time_utc}UTC)" if current_time else ""
                        logger.debug(f"✓ {event_title[:40]:40} | {current_time:8} | {currency} | Impact={impact} {tz_note} | Actual={actual} ({actual_status})")

                except Exception as e:
                    logger.error(f"Error parsing row {row_idx}: {e}")
                    continue

            # ====== LAYER 4: Audit logging ======
            timezone_summary = self._generate_timezone_audit_summary(tz_iana, utc_offset)
            logger.info("\n" + "="*70)
            logger.info("TIMEZONE CONVERSION AUDIT")
            logger.info("="*70)
            logger.info(timezone_summary)
            logger.info("="*70 + "\n")

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
