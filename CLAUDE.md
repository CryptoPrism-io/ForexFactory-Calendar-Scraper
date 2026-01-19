# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ForexFactory Calendar Database Pipeline - A production-ready system for automated economic calendar data ingestion from ForexFactory into PostgreSQL. Scrapes event data (dates, times, currencies, impact levels, actual/forecast/previous values) and maintains an audit trail of all sync operations.

**Stack**: Python 3.9+, PostgreSQL, Selenium/Chrome, GitHub Actions

## Development Commands

### Setup

```bash
cd scraper_2.2

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Run database migration (creates tables and indexes)
python migrations/run_migration.py
```

### Running Jobs

```bash
cd scraper_2.2

# Realtime job - scrapes week=this (~118 events)
python jobs/realtime_15min.py

# Daily sync - scrapes month=this (~400+ events)
python jobs/daily_sync.py

# Monthly backfill - scrapes last/this/next months (~1200+ events)
python jobs/monthly_backfill.py

# Test database connection
python test_db_connection.py

# Test complete integration
python test_complete_integration.py
```

### Manual Scraping Scripts

```bash
cd scraper_2.2/scripts

# Fetch specific week
python fetch_weekly_calendar.py

# Fetch specific month
python fetch_monthly_calendar.py
```

## Architecture

### Data Flow

```
ForexFactory HTML (calendar.php)
    ↓
[Selenium + Chrome] (bypass Cloudflare)
    ↓
[Semantic Parser] (src/scraper.py)
    ↓
[Event Normalization] (date parsing, timezone → UTC conversion)
    ↓
[UPSERT to PostgreSQL] (src/database.py)
    ↓
[Sync Logging] (sync_log table)
    ↓
PostgreSQL Database + Optional CSV Output
```

### Key Files

```
scraper_2.2/
├── src/
│   ├── scraper.py        # ForexFactoryScraper class - HTML parsing, event extraction
│   ├── database.py       # DatabaseManager class - UPSERT operations, sync logging
│   └── config.py         # Configuration management, credential masking
├── jobs/
│   ├── realtime_15min.py # Every 5 min: scrapes week=this
│   ├── daily_sync.py     # Daily 02:00 UTC: scrapes month=this
│   └── monthly_backfill.py # Manual: scrapes 3 months
├── migrations/
│   └── run_migration.py  # Schema setup and indexes
└── .env.example          # Environment template
```

### Database Schema

**economic_calendar_ff** (main events table):
- `id` - Primary key
- `event_uid` - ForexFactory unique identifier
- `date`, `date_utc` - Event date (original + UTC)
- `time`, `time_utc`, `datetime_utc` - Event time fields
- `time_zone`, `source_timezone` - Timezone tracking
- `currency` - Currency code (USD, EUR, GBP, etc.)
- `impact` - Impact level (high, medium, low)
- `event` - Event name
- `actual`, `forecast`, `previous` - Economic values
- `actual_status` - Sentiment (better, worse, unchanged)
- `source_scope` - Data source (day, week, month)
- `created_at`, `last_updated` - Timestamps

**sync_log** (audit trail):
- Job name, type, run_id
- Start/end times, status
- Events processed/added/updated
- Error tracking

### UPSERT Logic

The scraper uses `ON CONFLICT (event, currency, date_utc)` for deduplication:
- New events are inserted
- Existing events update only non-null fields (COALESCE pattern)
- Preserves existing actual values if new scrape returns null

```python
ON CONFLICT (event, currency, date_utc) DO UPDATE SET
    actual = COALESCE(EXCLUDED.actual, economic_calendar_ff.actual),
    ...
```

## Configuration

### Environment Variables (.env)

```
POSTGRES_HOST=your_host
POSTGRES_PORT=5432
POSTGRES_DB=fx_global
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_POOL_SIZE=5

OUTPUT_MODE=both        # 'csv', 'db', or 'both'
CSV_OUTPUT_DIR=csv_output
SCRAPER_VERBOSE=true
```

### GitHub Actions Secrets

Required secrets for automated workflows:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`

## GitHub Actions Workflows

Located in `.github/workflows/`:

| Workflow | Schedule | Scrapes | Events |
|----------|----------|---------|--------|
| `forexfactory-realtime-15min.yml` | Every 5 min | `week=this` | ~118 |
| `forexfactory-daily-sync.yml` | Daily 02:00 UTC | `month=this` | ~400+ |
| `forexfactory-monthly-backfill.yml` | Manual trigger | 3 months | ~1200+ |

### Cloudflare Bypass

The workflows use Xvfb (X Virtual Framebuffer) instead of headless Chrome to avoid Cloudflare detection:

```yaml
- name: Start Xvfb
  run: Xvfb :99 -screen 0 1920x1080x24 &

- name: Run scraper
  env:
    DISPLAY: ':99'
  run: python jobs/realtime_15min.py
```

## Important Notes

### Timezone Handling

- ForexFactory displays times in user's detected timezone
- Scraper detects source timezone from page
- All times converted to UTC before storage
- `datetime_utc` is the canonical timestamp field

### Index Strategy

- `unique_event_currency_date_fx` - UNIQUE constraint for UPSERT
- `idx_economic_calendar_ff_event_uid` - Non-unique (query performance only)
- `idx_economic_calendar_ff_datetime_utc` - For time-range queries

### Scraping Performance

- 2-5 seconds per page (includes Cloudflare challenge)
- UPSERT: 100-500 rows/second
- Memory: ~50-100 MB per instance
- Connection pool: 5 connections default

### Error Handling

- Scraping failures logged to `sync_log` with status='failed'
- Constraint violations handled gracefully (rollback + continue)
- All jobs return exit codes (0=success, 1=failure)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 0 events scraped | Cloudflare blocking - ensure Xvfb is running with DISPLAY=:99 |
| Duplicate key errors | Check unique index exists on (event, currency, date_utc) |
| Missing actual values | Normal - actuals populate after event occurs |
| Timezone mismatch | Verify source_timezone detection in logs |

## Integration with Dashboard

This scraper feeds data to the Forex-Session-Dashboard:
- Data stored in `fx_global` database
- Dashboard backend queries `economic_calendar_ff` table
- API endpoints: `/api/calendar/events`, `/api/calendar/today`
