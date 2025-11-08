# ForexFactory Scraper Architecture Analysis

## Executive Summary

The current scraper system is a **3-tier job orchestration pipeline** that:
1. **Bulk imports** historical data monthly
2. **Daily syncs** forward-looking data (past 3 days + next 7 days)
3. **Real-time updates** actual values every 5 minutes (for today's events)

---

## Core Architecture

### 1. **Scraper Core** (`scraper_core.py`)
The heart of the system - handles all web scraping logic.

**Key Class:** `ForexFactoryScraperCore`

**Methods:**
- `scrape_date(target_date)` - Scrapes events for a single date
  - Uses: Undetected Chrome + Selenium for Cloudflare bypass
  - Returns: List of dicts with event data

- `scrape_date_range(start_date, end_date)` - Scrapes multiple dates sequentially
  - Iterates day-by-day with rate limiting (2s between requests, 5s every 5 requests)
  - Returns: Pandas DataFrame

- `scrape_week(monday_date)` - Scrapes all events for a week
  - Internally calls `scrape_date(monday_date)`

- `scrape_year(year)` - Full year scrape
  - Calls `scrape_date_range(Jan1, Dec31)`

- `classify_impact(title)` - ML-like classification based on keywords
  - Returns: 'high', 'medium', 'low', 'unknown'

**HTML Parsing Structure:**
```
<tr class="calendar__row">
  <td[0]> Date (e.g., "Nov 7" or full YYYY-MM-DD)
  <td[1]> Time (e.g., "13:30")
  <td[2]> Currency (e.g., "USD")
  <td[3]> Impact (⭐ indicator - usually overridden by classification)
  <td[4]> Event Title
  <td[5]> Actual Value (or "--" if not released)
  <td[6]> Forecast
  <td[7]> Previous
</tr>
```

---

### 2. **Database Layer** (`database.py`)
PostgreSQL connection management with pooling.

**Key Class:** `DatabaseManager`

**Tables:**
- `Economic_Calendar_FF` - Main events table
  - Columns: date, time, currency, impact, event, actual, forecast, previous, created_at, updated_at
  - Primary key: Composite (date, currency, event) - prevents duplicates

- `sync_log` - Job tracking table
  - Tracks start time, end time, events_processed, events_added, events_updated, errors

**Core Operations:**
- `insert_events(events_list)` - Insert or skip duplicates
- `update_actual_values(updates_list)` - Update only when actual value changes
- `get_events_by_date_range(start, end)` - Query events
- `log_sync_start()` / `log_sync_complete()` - Job logging

---

### 3. **Three Job Pipelines**

#### Pipeline 1: **Monthly Updater** (`monthly_updater.py`)
**When:** 1st day of month, 12:00 UTC
**What:** Backfill previous month + next 3 months
**Data Source:** Full scrape of 4-month window
**DB Action:** Insert only (skip duplicates)
**Frequency:** Once per month

**Flow:**
```
1. Calculate date range (prev month through next 3 months)
2. Call scraper_core.scrape_date_range()
3. Add impact classification
4. Insert into DB with deduplication
5. Log results
```

#### Pipeline 2: **Daily Sync** (`daily_sync.py`)
**When:** 6:00 AM UTC daily
**What:** Keep near-term data fresh (past 3 days + next 7 days)
**Data Source:** Scrape this 10-day window
**DB Action:** Insert new events + Update actual values
**Frequency:** Every 24 hours

**Flow:**
```
1. Calculate date range (now - 3 days to now + 7 days)
2. Scrape data
3. Get existing records from DB
4. Reconcile using DataReconciler:
   - New events → Insert
   - Existing events with new actual values → Update
5. Log results
```

**Reconciliation Logic:**
- Compares scraped data against DB records
- Identifies: New events, Updated actuals, No changes
- Only updates events where actual was NULL/empty previously

#### Pipeline 3: **Real-Time Fetcher** (`realtime_fetcher.py`)
**When:** Every 5 minutes throughout trading day
**What:** Update actual values for today's events only
**Data Source:** Scrape today (`?day=today`)
**DB Action:** Update actuals only
**Frequency:** Every 5 minutes

**Flow:**
```
1. Get today's date
2. Scrape today only using scraper_core.scrape_date(today)
3. Extract events with non-empty actual values
4. Update DB with new actuals
5. Log what was updated
```

---

## Data Flow Diagram

```
ForexFactory Website
    ↓
scraper_core.py (Selenium + BeautifulSoup)
    ├─ scrape_date() → Single date
    ├─ scrape_date_range() → Multiple dates (sequential)
    └─ scrape_year() → Full year
    ↓
Pandas DataFrame (events)
    ├─ classify_impact() → Add impact column
    ├─ reconcile() → Compare with DB → (new_events, updates)
    ↓
database.py (PostgreSQL)
    ├─ insert_events() → New records
    ├─ update_actual_values() → Update actuals
    └─ log_sync_*() → Job tracking
    ↓
Economic_Calendar_FF table
```

---

## Workflows Configuration

### GitHub Actions Automation

**File:** `.github/workflows/`

1. **monthly-updater.yml** → Triggers monthly_updater.py
2. **daily-sync.yml** → Triggers daily_sync.py
3. **realtime-fetcher.yml** → Triggers realtime_fetcher.py

Each workflow:
- Sets up Python environment
- Installs dependencies
- Runs the job script
- Logs results to sync_log table

---

## Configuration Management

**File:** `config.yaml` (referenced but not in codebase)

Expected structure:
```yaml
scraper:
  browser_timeout: 30
  page_load_wait: 3
  cloudflare_wait: 5
  request_delay: 2
  daily_days_back: 3
  daily_days_forward: 7

database:
  host: localhost
  port: 5432
  database: forexfactory
  user: postgres
  password: ***
  pool_size: 5

forexfactory:
  impact_keywords:
    high: [fomc, fed, ecb, ...]
    medium: [pmi, ism, ...]
    low: [speaks, speech, ...]
```

Environment variables override config:
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `GITHUB_RUN_ID` (for job tracking)

---

## Key Design Decisions

### ✅ Advantages
1. **Cloudflare Bypass** - Uses undetected_chromedriver (reliable anti-detection)
2. **Rate Limiting** - Respects server load (2s between requests, 5s pauses every 5 requests)
3. **Deduplication** - Database composite key prevents duplicate insertions
4. **Incremental Updates** - Real-time fetcher only updates actuals for today
5. **Job Tracking** - sync_log table records all job runs
6. **Modular Design** - Separate classes for scraping, database, reconciliation

### ⚠️ Current Inefficiencies
1. **Daily Sync:** Re-scrapes past 3 days (already in DB) to check for updates
2. **Real-Time Fetcher:** Full page load every 5 minutes (could cache if only checking today)
3. **No Caching:** Each job starts fresh browser instance
4. **Sequential Scraping:** Date-by-date requests (could batch by week/month parameter)

---

## Entry Points & Dependencies

### Main Entry Points
```
monthly_updater.py    → Backfill historical data
daily_sync.py         → Keep near-term data fresh
realtime_fetcher.py   → Update today's actuals
```

### Core Dependencies
```
scraper_core.py       ← Required by all job scripts
database.py           ← Required by all job scripts
data_reconciliation.py ← Required by daily_sync.py only
```

### Python Packages
```
selenium
undetected-chromedriver
beautifulsoup4
pandas
psycopg2
pyyaml
python-dotenv
```

---

## Data Quality Notes

### What Gets Stored
- **Date** - Event date (parsed from page)
- **Time** - Event time in UTC
- **Currency** - Currency code (USD, EUR, GBP, etc.)
- **Impact** - Classified as high/medium/low/unknown
- **Event** - Event name/title
- **Actual** - Actual released value (empty until event occurs)
- **Forecast** - Expected value before release
- **Previous** - Value from previous period

### When Data Updates
- **Insert:** Monthly updater (backfill) + Daily sync (new events)
- **Actual Update:** Daily sync (if new actual appears) + Real-time fetcher (every 5 min)
- **Never Overwrites:** Forecast, Previous (immutable once scraped)

### Potential Data Issues
- Empty strings stored as empty (should be NULL in DB)
- No timezone handling (assumes UTC)
- Impact classification relies on keyword matching (can be inaccurate)

---

## Recommended Next Steps for Optimization

### Your Proposed Approach
**Cache bulk data → Update specific fields every 5 minutes**

This would:
1. ✅ Reduce API calls
2. ✅ Decrease browser startup overhead
3. ✅ Make real-time updates faster

### Suggested Architecture
```
Bulk Fetcher (Once every 4 hours):
  - Fetch ?day=today + ?week=this + ?week=next
  - Cache to JSON/SQLite
  - Insert new events to DB

Real-Time Updater (Every 5 minutes):
  - Query cached data for today's events
  - Check ForexFactory for actual value changes
  - Update DB if changed

Benefit:
  - Only 1 browser instance per 4 hours (vs 288 per day)
  - 97% reduction in overhead
  - Faster 5-minute updates (no full page load)
```

---

## Files in Current System

### Core System Files
- `scraper_core.py` - Core scraper class
- `database.py` - Database operations
- `data_reconciliation.py` - Reconciliation logic

### Job Scripts
- `monthly_updater.py` - Monthly backfill
- `daily_sync.py` - Daily incremental sync
- `realtime_fetcher.py` - Real-time actual updates

### Alternative Job Scripts (CSV versions)
- `monthly_updater_csv.py`
- `daily_sync_csv.py`
- `realtime_fetcher_csv.py`

### Utility/Historical Scripts
- `scrape_forexfactory.py` - Standalone year scraper
- Various other scripts (add_impact_levels.py, export_ff_csv.py, etc.)

### Configuration
- `.github/workflows/` - GitHub Actions automation

---

## Summary

**Current System:** Multi-stage job pipeline with 3 frequencies (monthly, daily, 5-min)

**Main File to Understand:** `scraper_core.py` (all scraping logic)

**Supporting Files:** `database.py` (storage), `daily_sync.py` / `realtime_fetcher.py` (orchestration)

**Best Entry Point for Learning:** Start with `realtime_fetcher.py` (simplest) → `daily_sync.py` → `scraper_core.py`

