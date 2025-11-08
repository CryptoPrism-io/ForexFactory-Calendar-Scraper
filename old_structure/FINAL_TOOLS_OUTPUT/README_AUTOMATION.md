# ForexFactory Automated Data Pipeline

Comprehensive automation system for scraping, syncing, and updating ForexFactory economic calendar data with PostgreSQL backend and GitHub Actions orchestration.

## 📋 Overview

This system implements a three-tier automation strategy:

1. **Monthly Updater** - Fetch 3 months of upcoming events (runs monthly)
2. **Daily Sync** - Incremental sync with last 3 days + next 7 days (runs daily)
3. **Real-Time Fetcher** - Update actual values as events release (runs every 5 minutes)

All data is stored in PostgreSQL with automated logging and error handling.

---

## 🏗️ Architecture

### Components

```
FINAL_TOOLS_OUTPUT/
├── scraper_core.py           # Core scraping logic (Cloudflare bypass)
├── database.py               # PostgreSQL connection & queries
├── data_reconciliation.py     # Pandas DataFrame reconciliation
├── monthly_updater.py         # Monthly 3-month fetch
├── daily_sync.py             # Daily 10-day sync
├── realtime_fetcher.py        # 5-minute actual value updates
├── config.yaml               # Configuration file
├── requirements.txt          # Python dependencies
└── database_schema.sql       # PostgreSQL schema

.github/workflows/
├── monthly-updater.yml       # Monthly cron job
├── daily-sync.yml            # Daily cron job
└── realtime-fetcher.yml      # 5-minute cron job
```

### Data Flow

```
ForexFactory Website
         ↓
    Scraper Core (Selenium + BeautifulSoup)
         ↓
    Data Reconciliation (Pandas diff)
         ↓
    PostgreSQL Database
         ↓
    Sync Log (tracking & monitoring)
```

---

## ⚙️ Setup Instructions

### Prerequisites

- PostgreSQL 12+ server running and accessible
- Python 3.11+
- GitHub repository with Actions enabled
- Chrome/Chromium browser (for Selenium)

### Local Setup

1. **Clone Repository**
   ```bash
   git clone <repo-url>
   cd News-Calendar/FINAL_TOOLS_OUTPUT
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create PostgreSQL Database**
   ```bash
   psql -U postgres -c "CREATE DATABASE forexfactory;"
   ```

4. **Initialize Database Schema**
   ```bash
   psql -U postgres -d forexfactory < database_schema.sql
   ```

5. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your PostgreSQL credentials
   ```

6. **Test Connection**
   ```bash
   python -c "from database import get_db_manager; db = get_db_manager(); print(f'Connected: {db.count_events()} events')"
   ```

### GitHub Actions Setup

1. **Add Repository Secrets**

   In GitHub Settings → Secrets and variables → Actions, add:
   - `POSTGRES_HOST` - Database server address
   - `POSTGRES_PORT` - Database port (usually 5432)
   - `POSTGRES_DB` - Database name (forexfactory)
   - `POSTGRES_USER` - Database user
   - `POSTGRES_PASSWORD` - Database password

2. **Enable Workflows**
   - Push `.github/workflows/` files to repository
   - GitHub Actions will automatically enable them
   - Workflows are initially disabled; enable in Actions tab if needed

3. **Verify Setup**
   - Go to Actions tab
   - Each workflow should appear: Monthly Updater, Daily Sync, Real-Time Fetcher

---

## 🚀 Running Scripts

### Manual Execution (Local)

**Monthly Updater**
```bash
python monthly_updater.py
```
Fetches next 3 months of events and inserts into database.

**Daily Sync**
```bash
python daily_sync.py
```
Fetches last 3 days + next 7 days, reconciles with database, adds/updates entries.

**Real-Time Fetcher**
```bash
python realtime_fetcher.py
```
Updates actual values for today's released economic indicators.

### Scheduled Execution (GitHub Actions)

**Monthly Updater**
- Runs: 1st of every month at 00:00 UTC
- Trigger: `0 0 1 * *`
- Manual trigger: Actions tab → Monthly Updater → Run workflow

**Daily Sync**
- Runs: Every day at 06:00 UTC
- Trigger: `0 6 * * *`
- Manual trigger: Actions tab → Daily Sync → Run workflow

**Real-Time Fetcher**
- Runs: Every 5 minutes (24/7)
- Trigger: `*/5 * * * *`
- Captures actual values within 5 minutes of release
- Continues on errors (network issues won't block workflow)

---

## 📊 Database Schema

### Main Table: `forex_events`

```sql
CREATE TABLE forex_events (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time VARCHAR(20),
    currency VARCHAR(3) NOT NULL,
    impact VARCHAR(20),           -- high, medium, low, unknown
    event TEXT NOT NULL,
    actual VARCHAR(100),          -- Actual released value
    forecast VARCHAR(100),        -- Forecast value
    previous VARCHAR(100),        -- Previous period value
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:** date, currency, impact, event, date+currency

**Uniqueness:** `(date, currency, event)` - prevents duplicate entries

### Audit Table: `forex_events_audit`

Tracks all updates to actual values:
- `event_id` - Reference to forex_events
- `field_changed` - Column that changed
- `old_value` / `new_value` - Before/after values
- `changed_at` - Timestamp
- `source` - Which job made the change

### Log Table: `sync_log`

Tracks all job executions:
- `job_name` - monthly_updater, daily_sync, realtime_fetcher
- `job_type` - monthly, daily, realtime
- `start_time` / `end_time` - Job duration
- `events_processed` / `events_added` / `events_updated`
- `status` - running, success, failed
- `error_message` - If failed

---

## 🔧 Configuration

### config.yaml

Edit `config.yaml` to customize:

```yaml
# Database connection
database:
  host: localhost
  port: 5432
  database: forexfactory

# Scraper settings
scraper:
  monthly_months_ahead: 3        # Months to fetch in monthly job
  daily_days_back: 3             # Days back in daily sync
  daily_days_forward: 7          # Days forward in daily sync
  headless: true                 # Run browser headless
  browser_timeout: 30            # Seconds to wait for page load
  page_load_wait: 3              # Initial page wait
  cloudflare_wait: 5             # Wait for Cloudflare challenge
  request_delay: 2               # Delay between requests
```

---

## 📝 Logging

All jobs write logs to `automation.log` in the same directory:

```
2025-11-08 10:30:45,123 - database - INFO - Database connection pool created: forexfactory@localhost
2025-11-08 10:30:46,456 - scraper_core - INFO - Scraping 2025-11-08...
2025-11-08 10:30:52,789 - scraper_core - INFO - Scraped 12 events
2025-11-08 10:30:54,101 - database - INFO - Inserted 5 new events, skipped 7 duplicates
```

View live logs:
```bash
tail -f automation.log
```

### GitHub Actions Logs

Logs are automatically captured and available:
1. Go to GitHub Actions tab
2. Click the workflow run
3. Click "monthly_updater" (or other job)
4. View real-time logs
5. Artifacts are attached (automation.log file)

---

## 🔍 Monitoring

### Check Database Status

```python
from database import get_db_manager
import pandas as pd

db = get_db_manager()

# Total events
print(f"Total events: {db.count_events()}")

# Recent syncs
logs = db.get_latest_sync_log(limit=10)
df = pd.DataFrame(logs)
print(df)

# Events by currency
events = db.get_events_by_currency_and_impact(currency='USD')
print(f"USD events: {len(events)}")
```

### Query Recent Events

```python
from database import get_db_manager
from datetime import date, timedelta

db = get_db_manager()

# Get next 7 days
start = date.today()
end = date.today() + timedelta(days=7)

events = db.get_events_by_date_range(str(start), str(end))
print(f"Found {len(events)} events for next 7 days")

# Filter by impact
high_impact = [e for e in events if e['impact'] == 'high']
print(f"High impact: {len(high_impact)}")
```

---

## 🚨 Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Solution:**
- Verify PostgreSQL is running: `psql -U postgres`
- Check `config.yaml` host/port match your database
- Verify firewall allows connection
- For GitHub Actions: ensure `POSTGRES_HOST` secret is the public IP/domain, not localhost

### Issue: "No events scraped"

**Solution:**
- Check internet connection
- Verify ForexFactory is accessible: `curl https://www.forexfactory.com`
- Check scraper logs for "Just a moment" (Cloudflare issue)
- Try increasing `cloudflare_wait` in config.yaml

### Issue: Duplicate Events

**Solution:**
- Database has uniqueness constraint `(date, currency, event)`
- Duplicates are automatically skipped (logged as "skipped X duplicates")
- No action needed - this is expected behavior

### Issue: GitHub Actions workflow not running

**Solution:**
- Verify secrets are set: Settings → Secrets → Actions
- Check workflow file syntax: `.yml` must be valid YAML
- Enable Actions: Settings → Actions → Allow all actions and reusable workflows
- Check workflow status: Actions tab → click workflow → enable if disabled

### Issue: Real-Time Fetcher timeout

**Solution:**
- Real-Time Fetcher has `continue-on-error: true`
- Timeouts are silently ignored - job continues
- Check logs for errors (Artifacts tab)
- Try running manually during business hours (when events are releasing)

---

## 📈 Performance

### Expected Data Volume

| Job | Events/Run | Frequency | Annual Events |
|-----|-----------|-----------|----------------|
| Monthly | 1,500-2,000 | 12x/year | ~18,000-24,000 |
| Daily | 0-50 | 365x/year | Net: ~200 (incremental) |
| Real-Time | 0-10 | 2,000+ runs/year | ~5,000 updates |

### Database Performance

- **Indexes:** Optimized for `date`, `currency`, `impact`
- **Unique constraint:** Prevents duplicate entries automatically
- **Connection pooling:** 5 concurrent connections by default
- **Storage:** ~5-10 MB for 1 year of events

---

## 🔐 Security

### Best Practices

1. **Secrets Management**
   - Never commit `.env` or credentials
   - Use GitHub Secrets for sensitive data
   - Rotate database passwords periodically

2. **Database**
   - Use strong password for `POSTGRES_PASSWORD`
   - Restrict database access to GitHub Actions IP range
   - Enable SSL connection if available

3. **Logs**
   - Logs stored locally and in GitHub Artifacts
   - Artifacts auto-delete after retention period (3-30 days)
   - No sensitive data in logs (password never logged)

---

## 📚 API Reference

### scraper_core.ForexFactoryScraperCore

```python
from scraper_core import ForexFactoryScraperCore
import pandas as pd

scraper = ForexFactoryScraperCore(config={...})

# Scrape single date
df = scraper.scrape_date(date(2025, 11, 8))

# Scrape date range
df = scraper.scrape_date_range(date(2025, 11, 1), date(2025, 11, 8))

# Scrape full year
df = scraper.scrape_year(2025)

# Classify impact
impact = scraper.classify_impact("FOMC Member Speaks")  # Returns "high"
```

### database.DatabaseManager

```python
from database import get_db_manager

db = get_db_manager()

# Insert events
inserted, skipped = db.insert_events([{...}], source="daily_sync")

# Query events
events = db.get_events_by_date_range("2025-11-01", "2025-11-08")

# Update actual values
updated = db.update_actual_values([{...}])

# Check database stats
total = db.count_events()
logs = db.get_latest_sync_log(limit=10)
```

### data_reconciliation.DataReconciler

```python
from data_reconciliation import DataReconciler
import pandas as pd

# Compare two DataFrames
df_new = pd.DataFrame([...])
df_existing = pd.DataFrame([...])

df_new_events, df_updates, summary = DataReconciler.reconcile(df_new, df_existing)
# Returns: (new_events, events_with_updates, summary_dict)
```

---

## 🤝 Contributing

To add features or fix bugs:

1. Create a branch: `git checkout -b feature/your-feature`
2. Make changes and test locally
3. Update documentation
4. Create pull request

---

## 📞 Support

For issues:
1. Check troubleshooting section above
2. Review logs in `automation.log`
3. Check GitHub Actions logs for workflow issues
4. Query database directly to verify data

---

## 📜 License

This project is part of the ForexFactory economic calendar tools.

---

## 🔄 Update History

- **2025-11-08** - Initial production release
  - 3-tier automation system
  - PostgreSQL backend
  - GitHub Actions integration
  - Full documentation

---

**Last Updated:** 2025-11-08
**Status:** Production Ready
**Version:** 1.0.0
