# ForexFactory Calendar Database Pipeline

A robust, production-ready system for automated economic calendar data ingestion from ForexFactory into PostgreSQL.

## Quick Start

**See [scraper_2.2/README.md](scraper_2.2/README.md) for complete setup and usage instructions.**

## What's Included

### Core System: `scraper_2.2/`
- **src/**: Modular production code (scraper, database, config)
- **jobs/**: Automated job scripts (realtime, daily, monthly)
- **migrations/**: Database schema extensions
- **README.md**: Comprehensive setup and API documentation

### Automation: `.github/workflows/`
- `forexfactory-realtime-15min.yml` - Updates every 15 minutes
- `forexfactory-daily-sync.yml` - Daily sync at 02:00 UTC
- `forexfactory-monthly-backfill.yml` - Manual monthly backfill

## Key Features

✅ **Multi-Period Scraping**: Day, week, month views from ForexFactory
✅ **UPSERT Logic**: No duplicates, intelligent updates only when data changes
✅ **Timezone Support**: Auto-detection and UTC conversion
✅ **Audit Trail**: Complete sync_log tracking all operations
✅ **GitHub Actions**: Fully automated scheduling
✅ **Dual Output**: PostgreSQL database + CSV files
✅ **Production-Ready**: Error handling, logging, retry logic

## Architecture

```
ForexFactory HTML
    ↓
[Semantic Parser] (src/scraper.py)
    ↓
[Event Normalization] (date parsing, timezone conversion)
    ↓
[UPSERT to PostgreSQL] (src/database.py)
    ↓
[Sync Logging] (audit trail)
    ↓
PostgreSQL Database + CSV Output
```

## Setup

1. **Copy environment template**:
   ```bash
   cd scraper_2.2
   cp .env.example .env
   # Edit .env with your PostgreSQL credentials
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run database migration**:
   ```bash
   python migrations/run_migration.py
   ```

4. **Run initial backfill**:
   ```bash
   python jobs/monthly_backfill.py
   ```

5. **Test manual jobs**:
   ```bash
   python jobs/realtime_15min.py
   python jobs/daily_sync.py
   ```

For detailed setup instructions, see [scraper_2.2/README.md](scraper_2.2/README.md).

## Environment & Secrets

- Copy `scraper_2.2/.env.example` to `.env` for the Python jobs and fill it with **local** values. Keep `.env` out of git (already ignored).
- Frontend/dashboard consumers can copy `env.template.yaml` to `env.yaml` and populate the same variables (`VITE_API_BASE_URL`, `POSTGRES_*`, `NODE_ENV`, etc.). `env.yaml` is ignored globally so real credentials never end up in commits.
- In CI, provide the same values as GitHub Secrets (`POSTGRES_HOST`, `POSTGRES_DB`, ...). Never check actual hostnames, usernames, or passwords into documentation.
- If a secret value was ever committed, rotate that credential immediately and force-push the scrubbed history.

## Database

The system uses PostgreSQL with these main tables:
- `Economic_Calendar_FF` - Economic events with actual/forecast/previous values
- `sync_log` - Audit trail of all scraping operations

Migration adds deduplication via `event_uid` and timezone tracking.

## GitHub Actions

Enable GitHub Actions and add these secrets to your repository:
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`

Workflows will automatically:
- Update today's events every 15 minutes
- Sync weekly events daily at 02:00 UTC
- Allow manual monthly backfills

## Performance

- **Scraping**: 2-5 seconds per page (includes Cloudflare challenge)
- **UPSERT**: 100-500 rows/second
- **Memory**: ~50-100 MB per scraper instance
- **DB Connections**: 5 (configurable via POSTGRES_POOL_SIZE)

## Troubleshooting

See [scraper_2.2/README.md#troubleshooting](scraper_2.2/README.md#-troubleshooting) for detailed troubleshooting guide.

## Implementation Status

✅ Core scraper with semantic HTML parsing
✅ Database integration with UPSERT logic
✅ Three automated job scripts
✅ GitHub Actions workflows
✅ Database schema migration
✅ Comprehensive documentation
✅ Production testing completed

## Tested Results

- ✅ Database migration: Successful
- ✅ Monthly backfill: 124 events processed (123 inserted, 1 updated)
- ✅ Realtime job: 3 events inserted
- ✅ Daily sync: 42 events processed (0 inserted, 42 updated)

---

**Production Ready** | **Fully Tested** | **Documented** | **Automated**
