#!/usr/bin/env python3
"""
Comprehensive timezone verification tests for ForexFactory Scraper

These tests verify all 5 layers of timezone handling:
- Layer 1: Chrome timezone forcing and JavaScript verification
- Layer 2: ForexFactory timezone extraction and validation
- Layer 3: Simplified UTC conversion
- Layer 4: Per-event validation
- Layer 5: End-to-end integration

Tests ensure that timezone handling is bulletproof and data is always correct.
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scraper import ForexFactoryScraper


class TestLayer1ChromeTimezoneVerification(unittest.TestCase):
    """Test Layer 1: Chrome timezone forcing and verification"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    @patch('scraper.uc.Chrome')
    def test_chrome_timezone_verification_success(self, mock_chrome):
        """Test successful UTC timezone verification"""
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = "UTC"
        mock_driver.execute_cdp_cmd.return_value = None
        mock_chrome.return_value = mock_driver

        driver = self.scraper.get_driver()

        # Verify CDP command was called
        mock_driver.execute_cdp_cmd.assert_called_once_with(
            "Emulation.setTimezoneOverride",
            {"timezoneId": "UTC"}
        )

        # Verify JavaScript timezone check was called
        self.assertTrue(mock_driver.execute_script.called)
        self.assertIsNotNone(driver)

    @patch('scraper.uc.Chrome')
    def test_chrome_timezone_verification_failure(self, mock_chrome):
        """Test timezone verification fails with non-UTC timezone"""
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = "America/New_York"
        mock_driver.execute_cdp_cmd.return_value = None
        mock_chrome.return_value = mock_driver

        # Should raise RuntimeError due to timezone mismatch
        with self.assertRaises(RuntimeError) as context:
            self.scraper.get_driver()

        self.assertIn("CRITICAL TIMEZONE VERIFICATION FAILED", str(context.exception))
        self.assertIn("America/New_York", str(context.exception))

        # Verify driver was quit on failure
        mock_driver.quit.assert_called_once()

    @patch('scraper.uc.Chrome')
    def test_chrome_timezone_cdp_command_fails(self, mock_chrome):
        """Test handling of CDP command failure"""
        mock_driver = MagicMock()
        mock_driver.execute_cdp_cmd.side_effect = Exception("CDP not available")
        mock_chrome.return_value = mock_driver

        # Should raise RuntimeError due to CDP failure
        with self.assertRaises(RuntimeError) as context:
            self.scraper.get_driver()

        self.assertIn("Timezone verification failed", str(context.exception))
        mock_driver.quit.assert_called()


class TestLayer2ForexFactoryTimezoneValidation(unittest.TestCase):
    """Test Layer 2: ForexFactory timezone extraction and validation"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    def test_verify_forexfactory_timezone_from_js_settings(self):
        """Test timezone extraction from JavaScript settings"""
        page_source = """
        <script>
        var settings = {
            timezone_name: 'UTC',
            timezone: '0'
        };
        </script>
        """
        soup = Mock()

        detected_tz = self.scraper.verify_forexfactory_timezone(soup, page_source)
        self.assertEqual(detected_tz, "UTC")

    def test_verify_forexfactory_timezone_from_offset(self):
        """Test timezone detection from offset value"""
        page_source = "timezone: '0', other: 'data'"
        soup = Mock()

        detected_tz = self.scraper.verify_forexfactory_timezone(soup, page_source)
        self.assertEqual(detected_tz, "UTC")

    def test_verify_forexfactory_timezone_gmt_normalized(self):
        """Test that GMT is normalized to UTC"""
        page_source = "Times are in GMT"
        soup = Mock()

        detected_tz = self.scraper.verify_forexfactory_timezone(soup, page_source)
        self.assertEqual(detected_tz, "UTC")

    def test_verify_forexfactory_timezone_rejects_pst(self):
        """Test that non-UTC timezones are rejected"""
        page_source = "timezone_name: 'America/Los_Angeles'"
        soup = Mock()

        with self.assertRaises(RuntimeError) as context:
            self.scraper.verify_forexfactory_timezone(soup, page_source)

        self.assertIn("ForexFactory is NOT displaying UTC times", str(context.exception))
        self.assertIn("America/Los_Angeles", str(context.exception))

    def test_verify_forexfactory_timezone_rejects_ist(self):
        """Test that IST timezone is rejected"""
        page_source = "timezone_name: 'Asia/Kolkata'"
        soup = Mock()

        with self.assertRaises(RuntimeError) as context:
            self.scraper.verify_forexfactory_timezone(soup, page_source)

        self.assertIn("CRITICAL", str(context.exception))


class TestLayer3SimplifiedUTCConversion(unittest.TestCase):
    """Test Layer 3: Simplified UTC conversion"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    def test_convert_to_utc_simple_12h_am(self):
        """Test conversion of 12-hour AM time"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("8:30am", "2025-12-03")

        self.assertEqual(time_utc, "08:30")
        self.assertEqual(date_utc, "2025-12-03")
        self.assertEqual(tz, "UTC")

    def test_convert_to_utc_simple_12h_pm(self):
        """Test conversion of 12-hour PM time"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("2:45pm", "2025-12-03")

        self.assertEqual(time_utc, "14:45")
        self.assertEqual(date_utc, "2025-12-03")
        self.assertEqual(tz, "UTC")

    def test_convert_to_utc_simple_24h(self):
        """Test conversion of 24-hour time"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("13:30", "2025-12-03")

        self.assertEqual(time_utc, "13:30")
        self.assertEqual(date_utc, "2025-12-03")
        self.assertEqual(tz, "UTC")

    def test_convert_to_utc_simple_special_values(self):
        """Test handling of special time values"""
        special_values = ["All Day", "Tentative", "Day", "off"]

        for value in special_values:
            time_utc, date_utc, tz = self.scraper.convert_to_utc_simple(value, "2025-12-03")

            self.assertEqual(time_utc, value)
            self.assertEqual(date_utc, "2025-12-03")
            self.assertEqual(tz, "N/A")

    def test_convert_to_utc_simple_no_conversion_needed(self):
        """Test that no actual timezone conversion occurs (already UTC)"""
        # Input time should equal output time (just formatted)
        test_cases = [
            ("1:30am", "01:30"),
            ("11:45pm", "23:45"),
            ("12:00pm", "12:00"),
            ("12:00am", "00:00"),
        ]

        for input_time, expected_output in test_cases:
            time_utc, _, tz = self.scraper.convert_to_utc_simple(input_time, "2025-12-03")

            self.assertEqual(time_utc, expected_output)
            self.assertEqual(tz, "UTC")

    def test_convert_to_utc_simple_invalid_time(self):
        """Test handling of invalid time formats"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("invalid", "2025-12-03")

        self.assertEqual(time_utc, "invalid")
        self.assertEqual(tz, "N/A")

    def test_convert_to_utc_simple_date_range(self):
        """Test handling of date ranges (not actual times)"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("19th-24th", "2025-12-03")

        self.assertEqual(time_utc, "19th-24th")
        self.assertEqual(tz, "N/A")


class TestLayer4EventValidation(unittest.TestCase):
    """Test Layer 4: Per-event timezone validation"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    def test_validate_event_timezone_valid_utc(self):
        """Test validation passes for valid UTC event"""
        event = {
            'event_uid': 'test123',
            'date': '2025-12-03',
            'time': '14:30',
            'time_zone': 'UTC',
            'time_utc': '14:30',
            'date_utc': '2025-12-03',
            'currency': 'USD',
            'event': 'Test Event'
        }

        # Should not raise exception
        self.assertTrue(self.scraper.validate_event_timezone(event))

    def test_validate_event_timezone_valid_na(self):
        """Test validation passes for N/A timezone (special times)"""
        event = {
            'event_uid': 'test123',
            'date': '2025-12-03',
            'time': 'All Day',
            'time_zone': 'N/A',
            'time_utc': 'All Day',
            'date_utc': '2025-12-03',
            'currency': 'USD',
            'event': 'Test Event'
        }

        self.assertTrue(self.scraper.validate_event_timezone(event))

    def test_validate_event_timezone_rejects_pst(self):
        """Test validation rejects PST timezone"""
        event = {
            'event_uid': 'test123',
            'date': '2025-12-03',
            'time': '14:30',
            'time_zone': 'PST',  # INVALID!
            'time_utc': '22:30',
            'date_utc': '2025-12-03',
            'currency': 'USD',
            'event': 'Test Event'
        }

        with self.assertRaises(ValueError) as context:
            self.scraper.validate_event_timezone(event)

        self.assertIn("invalid timezone", str(context.exception))
        self.assertIn("PST", str(context.exception))

    def test_validate_event_timezone_rejects_ist(self):
        """Test validation rejects IST timezone"""
        event = {
            'event_uid': 'test123',
            'date': '2025-12-03',
            'time': '14:30',
            'time_zone': 'IST',  # INVALID!
            'time_utc': '09:00',
            'date_utc': '2025-12-03',
            'currency': 'USD',
            'event': 'Test Event'
        }

        with self.assertRaises(ValueError) as context:
            self.scraper.validate_event_timezone(event)

        self.assertIn("CRITICAL", str(context.exception))

    def test_validate_event_timezone_missing_field(self):
        """Test validation catches missing required fields"""
        event = {
            'event_uid': 'test123',
            'date': '2025-12-03',
            # Missing 'time_zone' field
            'currency': 'USD',
            'event': 'Test Event'
        }

        with self.assertRaises(ValueError) as context:
            self.scraper.validate_event_timezone(event)

        self.assertIn("missing required field", str(context.exception))


class TestLayer5IntegrationTests(unittest.TestCase):
    """Test Layer 5: End-to-end integration tests"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    def test_end_to_end_utc_flow(self):
        """Test complete flow: Chrome UTC -> ForexFactory UTC -> Event validation"""
        # This would be a full integration test requiring actual browser
        # For now, we test the logical flow

        # Step 1: Simulate Chrome timezone verification
        with patch.object(self.scraper, 'get_driver') as mock_get_driver:
            mock_driver = MagicMock()
            mock_driver.execute_script.return_value = "UTC"
            mock_get_driver.return_value = mock_driver

            # Step 2: Simulate ForexFactory showing UTC
            page_source = "timezone_name: 'UTC'"
            soup = Mock()
            verified_tz = self.scraper.verify_forexfactory_timezone(soup, page_source)
            self.assertEqual(verified_tz, "UTC")

            # Step 3: Convert time (should be passthrough)
            time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("14:30", "2025-12-03")
            self.assertEqual(time_utc, "14:30")
            self.assertEqual(tz, "UTC")

            # Step 4: Validate event
            event = {
                'event_uid': 'test123',
                'date': date_utc,
                'time': '14:30',
                'time_zone': tz,
                'time_utc': time_utc,
                'date_utc': date_utc,
                'currency': 'USD',
                'event': 'Test Event'
            }
            self.assertTrue(self.scraper.validate_event_timezone(event))

    def test_audit_summary_generation(self):
        """Test timezone audit summary generation"""
        # Add some test events
        self.scraper.events = [
            {'time_zone': 'UTC', 'event': 'Event 1'},
            {'time_zone': 'UTC', 'event': 'Event 2'},
            {'time_zone': 'N/A', 'event': 'Event 3'},
        ]

        summary = self.scraper._generate_timezone_audit_summary("UTC")

        self.assertIn("Scraper Version: 2.3", summary)
        self.assertIn("Chrome timezone forced to: UTC", summary)
        self.assertIn("ForexFactory verified timezone: UTC", summary)
        self.assertIn("Total events: 3", summary)
        self.assertIn("UTC: 2 events", summary)
        self.assertIn("N/A: 1 events", summary)
        self.assertIn("DATA INTEGRITY: ✓ VERIFIED", summary)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""

    def setUp(self):
        self.scraper = ForexFactoryScraper(verbose=False)

    def test_midnight_time_conversion(self):
        """Test midnight (00:00) handling"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("12:00am", "2025-12-03")

        self.assertEqual(time_utc, "00:00")
        self.assertEqual(date_utc, "2025-12-03")
        self.assertEqual(tz, "UTC")

    def test_noon_time_conversion(self):
        """Test noon (12:00pm) handling"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("12:00pm", "2025-12-03")

        self.assertEqual(time_utc, "12:00")
        self.assertEqual(date_utc, "2025-12-03")
        self.assertEqual(tz, "UTC")

    def test_empty_time_handling(self):
        """Test empty/None time handling"""
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("", "2025-12-03")

        self.assertEqual(time_utc, "")
        self.assertEqual(tz, "N/A")

    def test_malformed_date_handling(self):
        """Test handling of malformed dates"""
        # Should still process but log error
        time_utc, date_utc, tz = self.scraper.convert_to_utc_simple("14:30", "invalid-date")

        self.assertEqual(time_utc, "14:30")
        self.assertEqual(tz, "UTC")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
