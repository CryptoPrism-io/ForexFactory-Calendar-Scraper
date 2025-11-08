# Scraper 2.2 - Fresh Implementation

## Overview

This is a **fresh implementation** of the ForexFactory economic calendar scraper, optimized for:
- Single URL approach: `?day=today`
- Bulk fetch + incremental updates
- Reduced API calls
- Better performance

## 📁 Folder Structure

```
scraper_2.2/
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── config.yaml                    # Configuration (template)
├── .env.example                   # Environment variables template
│
├── src/                           # Core implementation
│   ├── __init__.py
│   ├── scraper.py                 # Main scraper class
│   ├── database.py                # Database operations
│   ├── cache.py                   # Caching layer
│   └── utils.py                   # Utility functions
│
├── jobs/                          # Scheduled job scripts
│   ├── __init__.py
│   ├── bulk_fetcher.py            # Bulk fetch (run once every 4 hours)
│   ├── realtime_updater.py        # Real-time updates (every 5 minutes)
│   └── scheduler.py               # Job orchestration
│
├── tests/                         # Unit tests
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_cache.py
│   └── test_database.py
│
├── logs/                          # Application logs
│   └── .gitkeep
│
└── docs/
    ├── ARCHITECTURE.md            # System design
    └── MIGRATION_GUIDE.md         # How to migrate from old system
```

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Copy example files
cp .env.example .env
cp config.yaml.example config.yaml

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure

Edit `.env`:
```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=forexfactory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=***
```

Edit `config.yaml`:
```yaml
scraper:
  base_url: "https://www.forexfactory.com/calendar"
  request_delay: 2
  browser_timeout: 30

cache:
  enabled: true
  ttl_hours: 4
  storage: "json"  # or "sqlite"

jobs:
  bulk_fetch_interval_hours: 4
  realtime_update_interval_minutes: 5
```

### 3. Run Bulk Fetch

```bash
python jobs/bulk_fetcher.py
```

This:
- Fetches `?day=today` + surrounding days
- Caches results locally
- Inserts new events to database

### 4. Run Real-Time Updates

```bash
python jobs/realtime_updater.py
```

This:
- Checks today's cached data
- Fetches latest actuals
- Updates database only for changed values

### 5. Schedule Jobs

Use the scheduler (or your system's cron/task scheduler):

```bash
# Start scheduler
python jobs/scheduler.py
```

This automatically runs:
- Bulk fetch every 4 hours
- Real-time updates every 5 minutes

---

## 📊 Key Components

### `src/scraper.py`
Main scraper class with Cloudflare bypass.

```python
from src.scraper import ForexFactoryScraper

scraper = ForexFactoryScraper(config)
events = scraper.fetch_date('2025-11-08')  # Single date
events = scraper.fetch_today()             # Today specifically
```

### `src/cache.py`
Caching layer for bulk data.

```python
from src.cache import CacheManager

cache = CacheManager(storage='json')
cache.set('today', events_data)          # Store
cached = cache.get('today')              # Retrieve
cache.invalidate()                        # Clear
```

### `src/database.py`
Database operations (PostgreSQL).

```python
from src.database import DatabaseManager

db = DatabaseManager(config)
db.insert_events(events_list)            # New events
db.update_actual_values(updates_list)    # Update actuals
db.get_events_for_today()                # Query
```

### `jobs/bulk_fetcher.py`
Runs once every 4 hours - fetches bulk data.

**What it does:**
1. Fetch `?day=today`
2. Fetch `?day=yesterday` and `?day=tomorrow`
3. Cache all results
4. Insert new events to DB
5. Log results

**Run manually:**
```bash
python jobs/bulk_fetcher.py
```

### `jobs/realtime_updater.py`
Runs every 5 minutes - updates actuals.

**What it does:**
1. Get today's cached events
2. Re-fetch today's actual values only
3. Compare cached vs fresh
4. Update DB if changed
5. Update cache

**Run manually:**
```bash
python jobs/realtime_updater.py
```

---

## 🔄 Data Flow

```
Initial Run:
┌─────────────────────────────────────┐
│ bulk_fetcher.py                     │
│ - Fetch today + past/future dates   │
│ - Cache to JSON/SQLite              │
│ - Insert to database                │
└────────────┬────────────────────────┘
             ↓
         Cache Layer (today's events)
             ↓
      PostgreSQL Database

Every 5 Minutes:
┌─────────────────────────────────────┐
│ realtime_updater.py                 │
│ - Read cached today's events        │
│ - Fetch latest actuals from FF      │
│ - Compare & detect changes          │
│ - Update DB only if changed         │
│ - Update cache                      │
└─────────────────────────────────────┘
```

---

## 🔧 Configuration Options

### `scraper` section
- `base_url` - ForexFactory calendar URL
- `request_delay` - Seconds between requests
- `browser_timeout` - Selenium timeout in seconds
- `cloudflare_wait` - Extra wait for Cloudflare challenge

### `cache` section
- `enabled` - Enable/disable caching
- `ttl_hours` - Cache expiration time
- `storage` - "json" or "sqlite"
- `path` - Cache file location

### `jobs` section
- `bulk_fetch_interval_hours` - How often to bulk fetch
- `realtime_update_interval_minutes` - How often to update actuals
- `log_level` - "DEBUG", "INFO", "WARNING", "ERROR"

---

## 📝 Logging

Logs are written to:
- `logs/scraper_2.2.log` - All events
- Console - Real-time output

Enable debug logging in `config.yaml`:
```yaml
jobs:
  log_level: "DEBUG"
```

---

## 🧪 Testing

Run unit tests:

```bash
# All tests
python -m pytest tests/

# Specific test
python -m pytest tests/test_scraper.py

# With coverage
python -m pytest --cov=src tests/
```

---

## 🔍 Troubleshooting

### Issue: "Cloudflare challenge"
**Solution:** Increase `cloudflare_wait` in config.yaml
```yaml
scraper:
  cloudflare_wait: 10  # Try 10 seconds
```

### Issue: "No events found"
**Solution:** Check ForexFactory is loading:
```bash
python -c "
from src.scraper import ForexFactoryScraper
scraper = ForexFactoryScraper()
events = scraper.fetch_today()
print(f'Found {len(events)} events')
"
```

### Issue: "Database connection refused"
**Solution:** Verify PostgreSQL connection in `.env`
```bash
python -c "
from src.database import DatabaseManager
db = DatabaseManager()
print('Connected OK')
"
```

---

## 📚 Documentation

- **ARCHITECTURE.md** - System design and rationale
- **MIGRATION_GUIDE.md** - How to migrate from old system
- **../SCRAPER_ARCHITECTURE_ANALYSIS.md** - Analysis of old system

---

## 🎯 Next Steps

1. **Configure** - Edit `.env` and `config.yaml`
2. **Test** - Run bulk_fetcher.py manually and verify output
3. **Schedule** - Set up automated runs (cron, GitHub Actions, etc.)
4. **Monitor** - Check logs and database for data quality

---

## 📞 Support

Reference the old system implementation:
- `../old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py` - Scraping logic
- `../old_structure/FINAL_TOOLS_OUTPUT/database.py` - Database patterns
- `../old_structure/FINAL_TOOLS_OUTPUT/daily_sync.py` - Job orchestration patterns

---

**Last Updated:** 2025-11-08
**Status:** Initial setup complete - Ready for implementation
