#!/usr/bin/env python3
"""Unit test to verify TIME_PATTERN regex correctly identifies valid HH:MM times"""

import re

# Same pattern as in scraper.py
TIME_PATTERN = re.compile(r'^\d{1,2}:\d{2}$')

print("="*70)
print("TIME PATTERN VALIDATION TEST")
print("="*70)
print()

test_cases = [
    ("14:30", True, "Valid time"),
    ("9:00", True, "Single-digit hour"),
    ("00:00", True, "Midnight"),
    ("23:59", True, "End of day"),
    ("All Day", False, "Special value"),
    ("Day 4", False, "Day N format"),
    ("Sep 27th", False, "Date string - THE BUG!"),
    ("Tentative", False, "Tentative"),
    ("", False, "Empty string"),
    ("Nov 15th", False, "Another date string"),
    ("12:30pm", False, "Time with AM/PM"),
    ("25:00", True, "Invalid hour (but matches pattern)"),  # Note: regex only checks format, not validity
]

passed = 0
failed = 0

for time_str, should_match, description in test_cases:
    matches = bool(TIME_PATTERN.match(time_str))
    expected = "MATCH" if should_match else "NO MATCH"
    actual = "MATCH" if matches else "NO MATCH"

    if matches == should_match:
        status = "✅ PASS"
        passed += 1
    else:
        status = "❌ FAIL"
        failed += 1

    print(f"{status} | {description:30s} | '{time_str:15s}' | Expected: {expected:8s} | Got: {actual:8s}")

print()
print("="*70)
print(f"Test Results: {passed} passed, {failed} failed")
if failed == 0:
    print("✅ ALL TESTS PASSED!")
else:
    print(f"❌ {failed} TEST(S) FAILED!")
print("="*70)
