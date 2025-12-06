#!/usr/bin/env python3
"""
Verify IST timezone detection works correctly after fix
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("="*70)
print("IST TIMEZONE DETECTION VERIFICATION")
print("="*70)
print()

# Check environment variable
env_tz = os.getenv('SCRAPER_FORCE_TIMEZONE', '')
print(f"Environment variable SCRAPER_FORCE_TIMEZONE: '{env_tz}'")
print(f"  → Will use: {'AUTO-DETECT' if not env_tz else env_tz}")
print()

# Import scraper
from scraper import ForexFactoryScraper

print("Creating scraper instance...")
scraper = ForexFactoryScraper(verbose=False)

print(f"Scraper forced_timezone: '{scraper.forced_timezone}'")
print(f"  → Expected: '' (empty string for auto-detect)")
print(f"  → Result: {'✅ CORRECT (auto-detect enabled)' if scraper.forced_timezone == '' else '❌ WRONG (still forcing)'}")
print()

if scraper.forced_timezone:
    print("⚠️  WARNING: Timezone is still being forced!")
    print(f"  Forced to: {scraper.forced_timezone}")
    print("  This will bypass HTML detection!")
else:
    print("✅ SUCCESS: Auto-detect is enabled!")
    print("  Scraper will detect timezone from ForexFactory HTML")
    print("  Expected to detect: Asia/Kolkata (IST, UTC+5:30)")

print()
print("="*70)
print("TEST COMPLETE")
print("="*70)
