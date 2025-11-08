# Today Scraper - Quick Start Guide

## What This Does

Scrapes ForexFactory economic calendar for **today's events only**.

- URL: `https://www.forexfactory.com/calendar?day=today`
- Output: CSV file with today's events
- Saves to: `../csv_output/today_YYYYMMDD_HHMMSS.csv`

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `selenium` - Web automation
- `undetected-chromedriver` - Cloudflare bypass
- `beautifulsoup4` - HTML parsing
- `pandas` - Data handling
- `python-dotenv` - Environment variables

### 2. Run the Scraper

```bash
python scrape_today.py
```

### 3. Find Your CSV

```
../csv_output/today_YYYYMMDD_HHMMSS.csv
```

Example output:
```
today_20251108_200430.csv
```

## What You Get

A CSV file with columns:
- **Date** - Event date (Nov 8)
- **Time** - Event time (13:30)
- **Currency** - Currency pair (USD, EUR, GBP, etc.)
- **Impact** - ⭐ to ⭐⭐⭐ importance
- **Event** - Event name (CPI Release, NFP, etc.)
- **Actual** - Released value (empty if not released yet)
- **Forecast** - Expected value
- **Previous** - Previous period value

## Example Output

```
Date,Time,Currency,Impact,Event,Actual,Forecast,Previous
Nov 8,13:30,USD,⭐⭐⭐,CPI Release,3.2%,3.1%,3.0%
Nov 8,14:00,EUR,⭐⭐,ECB Decision,4.25%,4.50%,4.50%
Nov 8,15:00,GBP,⭐⭐,Unemployment Rate,4.3%,4.2%,4.2%
```

## Console Output

The script prints:
- ✓ When Chrome driver is created
- ✓ When page loads successfully
- ✓ Number of rows found
- ✓ Number of events extracted
- ✓ CSV file location and size
- 📊 Summary statistics (events by currency, by impact level)

Example:
```
======================================================================
FOREXFACTORY TODAY SCRAPER
======================================================================
URL: https://www.forexfactory.com/calendar?day=today
Time: 2025-11-08 20:04:30
======================================================================

✓ Chrome driver created
Loading page...
Waiting for Cloudflare challenge...
✓ Page loaded successfully
Parsing HTML...
Found 24 event rows
✓ Extracted 22 events

✓ CSV saved: today_20251108_200430.csv
  Location: ../csv_output/today_20251108_200430.csv
  File size: 4.2 KB
  Records: 22

======================================================================
DATA SUMMARY
======================================================================

Total Events: 22

By Currency:
  USD           8 ( 36.4%)
  EUR           7 ( 31.8%)
  GBP           4 ( 18.2%)
  JPY           3 ( 13.6%)

By Impact Level:
  ⭐            8 ( 36.4%)
  ⭐⭐           10 ( 45.5%)
  ⭐⭐⭐         4 ( 18.2%)

First 5 Events:
  1. [13:30] USD - CPI Release
  2. [14:00] EUR - ECB Decision
  3. [15:00] GBP - Unemployment Rate
  4. [16:30] JPY - Bank of Japan Statement
  5. [17:00] USD - Initial Jobless Claims

======================================================================

✓ Done!
```

## Troubleshooting

### Issue: Chrome crashes or hangs

**Solution:** Wait a moment and try again. Cloudflare challenge takes 3-5 seconds.

```bash
python scrape_today.py
```

### Issue: "Missing required packages"

**Solution:** Install dependencies

```bash
pip install -r requirements.txt
```

### Issue: "No events found"

**Solution:** Check if ForexFactory is accessible

```bash
# Try opening in browser
https://www.forexfactory.com/calendar?day=today
```

### Issue: Permission denied saving CSV

**Solution:** Make sure `csv_output` folder exists and is writable

```bash
mkdir -p ../csv_output
```

## Advanced Usage

### Run on a Schedule (Every 5 Minutes)

Use Windows Task Scheduler or cron on Linux/Mac.

**Windows:**
```batch
# Create task that runs every 5 minutes
python C:\path\to\today\script\scrape_today.py
```

**Linux/Mac (crontab):**
```bash
*/5 * * * * cd /path/to/today/script && python scrape_today.py
```

### Multiple URLs (Future Enhancement)

To scrape other dates:
- `?day=yesterday` - Yesterday's events
- `?day=tomorrow` - Tomorrow's events
- `?week=this` - This week
- `?month=next` - Next month

Just modify the URL in the script.

## File Structure

```
today/
├── script/
│   ├── scrape_today.py       # Main script (run this)
│   ├── requirements.txt       # Dependencies
│   └── README.md              # This file
└── csv_output/
    ├── today_20251108_200430.csv
    ├── today_20251108_205015.csv
    └── ... (more CSVs from each run)
```

## Next Steps

Once you have CSV data:
1. ✓ CSV created and saved
2. ⏳ (Future) Push to database
3. ⏳ (Future) Add more URLs
4. ⏳ (Future) Schedule runs automatically

## Notes

- Each run creates a new CSV with a timestamp
- CSVs are not overwritten (you keep historical data)
- Script takes ~5-10 seconds to run (Cloudflare challenge + browser load)
- Events are only for today; empty `Actual` values until event occurs

---

**Created:** November 8, 2025
**Version:** 1.0
**Status:** Ready to use!
