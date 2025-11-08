# Project Structure - Complete Overview

## Directory Organization

```
News-Calendar/                          # Root project directory
│
├── .github/                            # GitHub Actions workflows (KEEP FOR REFERENCE)
│   └── workflows/
│       ├── monthly-updater.yml
│       ├── daily-sync.yml
│       └── realtime-fetcher.yml
│
├── .claude/                            # Claude Code configuration
│
├── old_structure/                      # REFERENCE ONLY - Previous implementation
│   ├── FINAL_TOOLS_OUTPUT/             # All old scraper code
│   │   ├── scraper_core.py             # Core scraping class
│   │   ├── database.py                 # Database operations
│   │   ├── scrape_forexfactory.py      # Year-long scraper
│   │   ├── monthly_updater.py          # Monthly job
│   │   ├── daily_sync.py               # Daily job
│   │   ├── realtime_fetcher.py         # 5-minute job
│   │   ├── data_reconciliation.py      # Reconciliation logic
│   │   └── *.py                        # Other utilities
│   │
│   └── github_workflows/               # Old GitHub Actions (for reference)
│       └── ...
│
├── scraper_2.2/                        # NEW IMPLEMENTATION (Fresh start)
│   ├── README.md                       # Getting started guide
│   ├── requirements.txt                # Python dependencies
│   ├── config.yaml                     # Configuration template
│   ├── .env.example                    # Environment template
│   │
│   ├── src/                            # Core implementation
│   │   ├── __init__.py
│   │   ├── scraper.py                  # Main scraper
│   │   ├── database.py                 # DB operations
│   │   ├── cache.py                    # Caching layer
│   │   └── utils.py                    # Utilities
│   │
│   ├── jobs/                           # Scheduled jobs
│   │   ├── __init__.py
│   │   ├── bulk_fetcher.py             # Bulk fetch (4 hours)
│   │   ├── realtime_updater.py         # Real-time (5 minutes)
│   │   └── scheduler.py                # Job orchestration
│   │
│   ├── tests/                          # Unit tests
│   │   ├── __init__.py
│   │   ├── test_scraper.py
│   │   ├── test_cache.py
│   │   └── test_database.py
│   │
│   ├── logs/                           # Application logs
│   │   └── .gitkeep
│   │
│   └── docs/
│       ├── ARCHITECTURE.md
│       └── MIGRATION_GUIDE.md
│
├── SCRAPER_ARCHITECTURE_ANALYSIS.md    # Analysis of old system (IMPORTANT!)
├── PROJECT_STRUCTURE.md                # This file
│
├── ACTION_PLAN.md                      # Original action plan
├── DELIVERY_COMPLETE.md                # Project completion doc
├── IMPLEMENTATION_SUMMARY.md           # Implementation notes
├── SETUP_GUIDE.md                      # Setup instructions
├── QUICK_REFERENCE.md                  # Quick reference
├── LOCAL_TESTING_GUIDE.md              # Testing guide
└── .git/                               # Git repository

```

---

## What's Where

### 📖 Understanding the System

**START HERE:**
1. Read `SCRAPER_ARCHITECTURE_ANALYSIS.md` - Complete overview of how the old system works
2. Read `scraper_2.2/README.md` - Getting started with new implementation

### 📚 Reference Materials

**Old System (for learning):**
- `old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py` - Scraping logic with Cloudflare bypass
- `old_structure/FINAL_TOOLS_OUTPUT/database.py` - Database patterns and queries
- `old_structure/FINAL_TOOLS_OUTPUT/daily_sync.py` - Job orchestration example
- `old_structure/FINAL_TOOLS_OUTPUT/realtime_fetcher.py` - Real-time update pattern

**GitHub Actions (for reference):**
- `.github/workflows/` - Automation patterns

### 🚀 New Implementation

**Build here:**
- `scraper_2.2/src/` - Core classes (scraper, database, cache)
- `scraper_2.2/jobs/` - Job scripts (bulk_fetcher, realtime_updater)
- `scraper_2.2/tests/` - Unit tests

---

## Implementation Map

### Phase 1: Core Scraper (scraper_2.2/src/)

```
Task: Implement src/scraper.py
├── Import Selenium + BeautifulSoup
├── Reference: old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py
├── Create ForexFactoryScraper class
├── Methods:
│   ├── fetch_date(date)      → Returns list of events
│   ├── fetch_today()         → Shortcut for today
│   └── classify_impact(text) → Categorize event
└── Test: Can fetch today's events?
```

### Phase 2: Caching Layer (scraper_2.2/src/)

```
Task: Implement src/cache.py
├── Create CacheManager class
├── Methods:
│   ├── set(key, data)        → Store to file/DB
│   ├── get(key)              → Retrieve from file/DB
│   ├── invalidate()          → Clear cache
│   └── is_valid(key)         → Check expiration
└── Test: Can cache and retrieve?
```

### Phase 3: Database (scraper_2.2/src/)

```
Task: Implement src/database.py
├── Reference: old_structure/FINAL_TOOLS_OUTPUT/database.py
├── Create DatabaseManager class
├── Methods:
│   ├── insert_events(list)           → New events
│   ├── update_actual_values(list)    → Update actuals
│   ├── get_events_for_today()        → Query today
│   └── log_job(name, status)         → Track runs
└── Test: Can insert/update/query?
```

### Phase 4: Bulk Fetcher Job (scraper_2.2/jobs/)

```
Task: Implement jobs/bulk_fetcher.py
├── Initialize scraper, cache, database
├── Fetch data (today + adjacent days)
├── Cache the results
├── Insert new events to DB
├── Log job completion
└── Test: Does it populate database?
```

### Phase 5: Real-Time Updater (scraper_2.2/jobs/)

```
Task: Implement jobs/realtime_updater.py
├── Read cached today's events
├── Fetch latest actual values
├── Compare against cache
├── Update DB for changed values
├── Update cache
└── Test: Does it update actuals?
```

### Phase 6: Job Scheduler (scraper_2.2/jobs/)

```
Task: Implement jobs/scheduler.py
├── Schedule bulk_fetcher every 4 hours
├── Schedule realtime_updater every 5 minutes
├── Handle logging
├── Error handling
└── Test: Do jobs run automatically?
```

### Phase 7: Tests (scraper_2.2/tests/)

```
Task: Implement unit tests
├── test_scraper.py     → Verify scraping logic
├── test_cache.py       → Verify caching
├── test_database.py    → Verify DB operations
└── Run: pytest
```

---

## Key Files to Study

### Understanding How Scraping Works

**File:** `old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py`

**Key Methods to Understand:**
- `get_driver()` - Creates Chrome instance with Cloudflare bypass
- `scrape_date()` - Single date scraping with HTML parsing
- `scrape_date_range()` - Multiple dates with rate limiting

**HTML Structure:**
```html
<tr class="calendar__row">
  <td>Date</td>
  <td>Time</td>
  <td>Currency</td>
  <td>Impact</td>
  <td>Event Title</td>
  <td>Actual</td>
  <td>Forecast</td>
  <td>Previous</td>
</tr>
```

### Understanding Database Operations

**File:** `old_structure/FINAL_TOOLS_OUTPUT/database.py`

**Key Methods:**
- `insert_events()` - Insert with deduplication (composite key)
- `update_actual_values()` - Update only when value changes
- `get_events_by_date_range()` - Query events

**Database Schema:**
```sql
Economic_Calendar_FF (
  date,
  time,
  currency,
  impact,
  event,
  actual,
  forecast,
  previous,
  created_at,
  updated_at
)
```

### Understanding Job Orchestration

**Files:**
- `old_structure/FINAL_TOOLS_OUTPUT/daily_sync.py` - Shows how to coordinate scraping + DB operations
- `old_structure/FINAL_TOOLS_OUTPUT/realtime_fetcher.py` - Shows real-time update pattern

**Pattern:**
1. Initialize scraper + database
2. Fetch data
3. Process/classify
4. Insert or update DB
5. Log results

---

## Configuration Reference

### Environment Variables (.env)

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=forexfactory
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
GITHUB_RUN_ID=local
```

### Configuration File (config.yaml)

```yaml
scraper:
  base_url: "https://www.forexfactory.com/calendar"
  request_delay: 2
  browser_timeout: 30
  cloudflare_wait: 5

cache:
  enabled: true
  ttl_hours: 4
  storage: "json"
  path: "./cache"

database:
  pool_size: 5

jobs:
  bulk_fetch_interval_hours: 4
  realtime_update_interval_minutes: 5
  log_level: "INFO"
```

---

## Development Workflow

### 1. Start with Old System Understanding

```bash
# Read the architecture analysis
cat SCRAPER_ARCHITECTURE_ANALYSIS.md

# Study old scraper code
cat old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py
cat old_structure/FINAL_TOOLS_OUTPUT/database.py
```

### 2. Set Up New Environment

```bash
cd scraper_2.2/
cp .env.example .env
cp config.yaml.example config.yaml
# Edit .env and config.yaml with your settings
```

### 3. Implement Core Components

```bash
# Create src/scraper.py (referencing old scraper_core.py)
# Create src/database.py (referencing old database.py)
# Create src/cache.py (new component)
```

### 4. Implement Jobs

```bash
# Create jobs/bulk_fetcher.py
# Create jobs/realtime_updater.py
# Create jobs/scheduler.py
```

### 5. Test & Verify

```bash
# Test scraper
python -m pytest tests/test_scraper.py

# Test bulk fetch
python jobs/bulk_fetcher.py

# Test real-time update
python jobs/realtime_updater.py
```

### 6. Integrate with GitHub Actions

```bash
# Update .github/workflows/ if needed
# Deploy to production
```

---

## Quick Reference

### Folder Purposes

| Folder | Purpose | Access |
|--------|---------|--------|
| `old_structure/` | Reference implementation | READ ONLY |
| `scraper_2.2/` | New implementation | WRITE HERE |
| `.github/` | Automation workflows | REFERENCE |
| `logs/` | Application logs | WRITE |

### File Sizes (old_structure)

- `scraper_core.py` - 308 lines (core scraping)
- `database.py` - 321 lines (DB operations)
- `daily_sync.py` - 176 lines (job orchestration)
- `realtime_fetcher.py` - 171 lines (real-time job)

### Key Concepts

| Concept | Old Location | New Location |
|---------|--------------|--------------|
| Scraping | `scraper_core.py` | `scraper_2.2/src/scraper.py` |
| Database | `database.py` | `scraper_2.2/src/database.py` |
| Caching | None | `scraper_2.2/src/cache.py` |
| Bulk Job | `monthly_updater.py` | `scraper_2.2/jobs/bulk_fetcher.py` |
| Real-time Job | `realtime_fetcher.py` | `scraper_2.2/jobs/realtime_updater.py` |

---

## Important Notes

### ⚠️ Don't Delete Old Structure
The `old_structure/` folder is your **reference**. Keep it to:
- Understand how things work
- Copy proven patterns
- Debug issues

### ✅ Start Fresh in scraper_2.2
Build new implementations from scratch:
- Learn from old code
- Improve designs
- Implement your optimization (cache + bulk fetch)

### 📝 Keep Documentation Updated
As you implement:
- Update `scraper_2.2/README.md`
- Create `scraper_2.2/docs/ARCHITECTURE.md`
- Document design decisions

---

## Next Steps

1. **Read** `SCRAPER_ARCHITECTURE_ANALYSIS.md`
2. **Study** `old_structure/FINAL_TOOLS_OUTPUT/` code
3. **Set up** `scraper_2.2/` environment
4. **Implement** Phase 1 (Core Scraper)
5. **Test** with `pytest`
6. **Continue** through remaining phases

---

**Created:** 2025-11-08
**Status:** Initial structure ready - Ready for development
