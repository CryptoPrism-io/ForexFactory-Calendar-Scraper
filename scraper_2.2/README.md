# ForexFactory Calendar Database Pipeline

A robust and efficient ForexFactory Calendar ingestion pipeline that keeps a PostgreSQL database continuously updated with economic event data (Actual, Forecast, and Previous values).

## Overview

This is an **enterprise-grade implementation** of the ForexFactory economic calendar scraper, featuring:
- **UPSERT-based database integration** - Intelligent insert/update with no duplicates
- **Multi-period scraping** - Support for `?day=today`, `?week=this`, `?month=last|this|next`
- **Automated scheduling** - GitHub Actions + local cron support
- **Dual output** - PostgreSQL database + CSV files
- **Semantic HTML parsing** - Robust CSS selector-based extraction
- **Comprehensive logging** - Full audit trail in sync_log table

## 📁 Folder Structure

```
scraper_2.2/
├── README.md                      # This file (UPDATED)
├── requirements.txt               # Python dependencies (ENHANCED)
├── .env.example                   # Environment template (NEW)
│
├── src/                           # Core modules (NEW STRUCTURE)
│   ├── scraper.py                 # Modular scraper with multi-period support
│   ├── database.py                # Enhanced DB manager with UPSERT logic
│   └── config.py                  # Configuration management
│
├── jobs/                          # Automated job scripts (NEW)
│   ├── realtime_15min.py          # 15-minute updates (day=today)
│   ├── daily_sync.py              # Daily sync (week=this)
│   └── monthly_backfill.py        # One-time backfill (month=*)
│
├── migrations/                    # Database schema (NEW)
│   ├── 001_extend_schema.sql      # Schema extension
│   └── run_migration.py           # Migration runner
│
├── today/
│   ├── script/                    # Legacy scraper (maintained for reference)
│   └── csv_output/                # Generated CSV files
│
├── csv_output/
│   ├── realtime/                  # 15-min job output
│   ├── daily/                     # Daily job output
│   └── backfill/                  # Backfill job output
│
└── .github/workflows/             # GitHub Actions (NEW)
    ├── forexfactory-realtime-15min.yml
    ├── forexfactory-daily-sync.yml
    └── forexfactory-monthly-backfill.yml
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+ (tested on 3.11)
- PostgreSQL 12+ with `Economic_Calendar_FF` and `sync_log` tables
- Chrome/Chromium browser

### 1. Environment Setup

```bash
cd scraper_2.2

# Copy environment template
cp .env.example .env

# Edit with your PostgreSQL credentials
nano .env
```

**Required environment variables:**
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=forexfactory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
```

> ⚠️ Copy `.env.example` to `.env` (or `env.template.yaml` to `env.yaml` if another service consumes YAML) and keep the populated files out of source control. In CI/CD, provide the same values via repository secrets—never hard-code real credentials in documentation.

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install packages
pip install -r requirements.txt
```

### 3. Run Database Migration

```bash
# Extend Economic_Calendar_FF schema with new columns
python migrations/run_migration.py
```

This adds: `event_uid`, `time_zone`, `time_utc`, `actual_status`, `source_scope`, `last_updated`

### 4. Initial Backfill (One-Time)

```bash
# Populate database with last/this/next months
python jobs/monthly_backfill.py
```

Expected time: 5-15 minutes

### 5. Run Manual Jobs (Testing)

```bash
# Update today's events
python jobs/realtime_15min.py

# Update this week's events
python jobs/daily_sync.py
```

---

## 🤖 Automated Scheduling

### GitHub Actions (Recommended)

Three workflows run automatically:

#### 1. **Realtime Updates** - Every 15 minutes
```yaml
# .github/workflows/forexfactory-realtime-15min.yml
Cron: */15 * * * *
Purpose: Update today's Actual values
```

#### 2. **Daily Sync** - Every day at 02:00 UTC
```yaml
# .github/workflows/forexfactory-daily-sync.yml
Cron: 0 2 * * *
Purpose: Update this week's events
```

#### 3. **Monthly Backfill** - Manual trigger
```yaml
# .github/workflows/forexfactory-monthly-backfill.yml
Trigger: workflow_dispatch (button in GitHub UI)
Purpose: Full backfill of all months
```

**Setup:**
1. Add to GitHub Secrets:
   - `POSTGRES_HOST`
   - `POSTGRES_PORT`
   - `POSTGRES_DB`
   - `POSTGRES_USER`
   - `POSTGRES_PASSWORD`
2. Workflows auto-run on schedule

### Local Cron/Scheduler

```bash
# Edit crontab
crontab -e

# Add these lines:

# Every 15 minutes
*/15 * * * * cd /path/to/scraper_2.2 && python jobs/realtime_15min.py >> realtime.log 2>&1

# Daily at 02:00 UTC
0 2 * * * cd /path/to/scraper_2.2 && python jobs/daily_sync.py >> daily.log 2>&1

# Weekly backfill (Sunday at 03:00 UTC)
0 3 * * 0 cd /path/to/scraper_2.2 && python jobs/monthly_backfill.py >> backfill.log 2>&1
```

---

## 📊 API Reference

### ForexFactoryScraper

```python
from src.scraper import ForexFactoryScraper

scraper = ForexFactoryScraper(verbose=True)

# Scrape different periods
scraper.scrape_period("day=today")      # Today's events
scraper.scrape_period("week=this")      # This week
scraper.scrape_period("month=last")     # Last month
scraper.scrape_period("month=this")     # This month
scraper.scrape_period("month=next")     # Next month

# Get results
events = scraper.get_events()  # List of dicts
scraper.clear_events()         # Reset for next scrape
```

### DatabaseManager

```python
from src.database import get_db_manager
from src.config import get_config

config = get_config()
db = get_db_manager(config.get_db_config())

# UPSERT events (insert new, update changed)
inserted, updated, processed = db.upsert_events(
    events,
    source_scope='day'  # 'day', 'week', or 'month'
)

# Query events
events = db.get_events_by_date_range('2024-11-01', '2024-11-30')
events = db.get_events_by_currency_and_impact('USD', 'high')

# Logging
log_id = db.log_sync_start('daily_sync', 'daily')
db.log_sync_complete(log_id, processed, inserted, updated)
```

---

## 💾 Database Schema

### Economic_Calendar_FF Table

**New columns added by migration:**
- `event_uid` (TEXT, UNIQUE) - Unique event identifier
- `time_zone` (VARCHAR) - Detected timezone (GMT, EST, IST, etc.)
- `time_utc` (VARCHAR) - UTC-converted time
- `actual_status` (VARCHAR) - Status: better/worse/unchanged
- `source_scope` (VARCHAR) - Source: day/week/month
- `last_updated` (TIMESTAMPTZ) - Last update timestamp

**Unique constraint:**
```sql
ON CONFLICT (event_uid) DO UPDATE SET
    actual = EXCLUDED.actual,
    actual_status = EXCLUDED.actual_status,
    forecast = EXCLUDED.forecast,
    previous = EXCLUDED.previous,
    ...
```

### sync_log Table

Tracks all job executions:
- `id` - Unique execution ID
- `job_name` - realtime_15min, daily_sync, monthly_backfill
- `job_type` - realtime, daily, backfill
- `start_time` - Job start timestamp
- `end_time` - Job completion timestamp
- `events_processed` - Total events scraped
- `events_added` - New records inserted
- `events_updated` - Existing records updated
- `errors` - Error count
- `status` - running/success/failed

---

## 🔧 Configuration

All settings in `.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=forexfactory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=***
POSTGRES_POOL_SIZE=5

# Scraper
SCRAPER_TIMEOUT=30              # Page load timeout (seconds)
SCRAPER_RETRIES=3               # Retry attempts
SCRAPER_VERBOSE=false           # Debug logging

# Output
OUTPUT_MODE=both                # csv, db, or both
CSV_OUTPUT_DIR=csv_output

# Logging
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
LOG_FILE=forexfactory.log
```

---

## 🔍 Troubleshooting

| Issue | Solution |
|-------|----------|
| Chrome driver not found | `sudo apt-get install chromium-browser` or download from google.com/chrome |
| Database connection refused | Check PostgreSQL is running, verify `.env` credentials |
| Missing columns error | Run `python migrations/run_migration.py` |
| Script times out | Increase `SCRAPER_TIMEOUT` in `.env` |
| No events scraped | Check ForexFactory HTML structure hasn't changed |
| "ON CONFLICT" error | Normal - means event already exists, no action needed |

---

## 📈 Performance Notes

- **Scraping speed**: ~2-5 seconds per page (Cloudflare challenge)
- **Database UPSERT**: ~100-500 rows/second
- **Memory usage**: ~50-100 MB per scraper instance
- **Database pool**: 5 connections (configurable)

---

## ✅ Best Practices

1. Always run migration first
2. Start with monthly backfill to populate database
3. Monitor sync_log table for issues
4. Test locally before deploying to GitHub Actions
5. Use `OUTPUT_MODE=db` in production for speed
6. Set `SCRAPER_VERBOSE=false` for scheduled jobs
7. Review CSV output periodically for quality

---

## 📚 Reference

**Key files:**
- `src/scraper.py` - Semantic HTML parser (670+ lines)
- `src/database.py` - PostgreSQL manager with UPSERT
- `src/config.py` - Configuration management
- `jobs/*.py` - Job orchestration
- `migrations/001_extend_schema.sql` - Schema extension

**Legacy reference:**
- `today/script/scrape_today.py` - Original scraper
- `../old_structure/FINAL_TOOLS_OUTPUT/` - Old system patterns

---

**Last Updated:** 2025-11-08
**Status:** Complete implementation with GitHub Actions support
**Tested on:** Python 3.11, PostgreSQL 12+, Chrome/Chromium
