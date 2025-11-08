# ForexFactory Automation - Quick Reference

## 🚀 Current Status

```
✓ PostgreSQL Database:     34.55.195.199:5432 (dbcp)
✓ Schema Initialized:      3 tables, indexes, triggers
✓ Configuration:           Updated with actual credentials
✓ All Scripts:             Ready to execute
✓ GitHub Actions:          Ready to deploy
✓ Monthly Updater:         RUNNING (fetching 3 months)
```

---

## 📊 What's Running Now

**Monthly Updater** - Fetching economic events for:
- November 2025 (remaining events)
- December 2025 (full month)
- January 2026 (full month)

**Expected:**
- Runtime: 30-45 minutes
- Events: ~1500-2000
- Will insert into database automatically

**Check Progress:**
```bash
cd FINAL_TOOLS_OUTPUT
tail -f automation.log
```

---

## 🎯 Three-Tier Automation

### 1️⃣ Monthly Updater (happens on 1st of month)
```bash
python monthly_updater.py
```
- Fetches 3 months ahead
- Inserts into database
- ~1500-2000 events per run

### 2️⃣ Daily Sync (happens at 6am UTC daily)
```bash
python daily_sync.py
```
- Fetches last 3 + next 7 days
- Reconciles with database
- Adds new, updates actual values

### 3️⃣ Real-Time Fetcher (every 5 minutes)
```bash
python realtime_fetcher.py
```
- Captures released values
- Updates actual fields
- Continues 24/7

---

## 🗄️ Database Info

**Connection:**
- Host: 34.55.195.199
- Port: 5432
- Database: dbcp
- User: yogass09

**Tables:**
```
forex_events           - Main event data (date, time, currency, impact, event, actual, forecast, previous)
forex_events_audit     - Track all changes to actual values
sync_log               - Track job executions
```

**Query Examples:**
```bash
# Count events
psql -h 34.55.195.199 -U yogass09 -d dbcp -c "SELECT COUNT(*) FROM forex_events;"

# By currency
psql -h 34.55.195.199 -U yogass09 -d dbcp -c "SELECT currency, COUNT(*) FROM forex_events GROUP BY currency;"

# Job logs
psql -h 34.55.195.199 -U yogass09 -d dbcp -c "SELECT * FROM sync_log ORDER BY start_time DESC LIMIT 5;"
```

---

## 📋 Files Created

**Automation Scripts (3):**
- `monthly_updater.py` - 3-month fetcher
- `daily_sync.py` - Incremental daily sync
- `realtime_fetcher.py` - 5-minute updates

**Support Files (3):**
- `scraper_core.py` - Web scraper (Cloudflare bypass)
- `database.py` - Database manager
- `data_reconciliation.py` - Data diff/merge

**Configuration (3):**
- `config.yaml` - Main config
- `.env` - Your database credentials
- `.env.example` - Template

**GitHub Actions (3):**
- `.github/workflows/monthly-updater.yml` - 1st of month @ 00:00 UTC
- `.github/workflows/daily-sync.yml` - Every day @ 06:00 UTC
- `.github/workflows/realtime-fetcher.yml` - Every 5 minutes 24/7

**Documentation (3):**
- `README_AUTOMATION.md` - Complete guide
- `SETUP_GUIDE.md` - Setup instructions
- `QUICK_REFERENCE.md` - This file

---

## 🔧 GitHub Actions Setup (Final Step)

1. **Go to your GitHub repository**

2. **Add Secrets** (Settings → Secrets and variables → Actions):
   ```
   POSTGRES_HOST = 34.55.195.199
   POSTGRES_PORT = 5432
   POSTGRES_DB = dbcp
   POSTGRES_USER = yogass09
   POSTGRES_PASSWORD = [your password]
   ```

3. **Push this directory to GitHub:**
   ```bash
   git add .
   git commit -m "Add ForexFactory automation system"
   git push
   ```

4. **Enable Workflows** (Actions tab):
   - Click each workflow
   - Click "Enable workflow"

5. **Verify** (manually trigger):
   - Monthly Updater → Run workflow
   - Daily Sync → Run workflow
   - Real-Time Fetcher → Run workflow

---

## 📈 Data Flow

```
Tier 1: Monthly (1st of month, 00:00 UTC)
  ↓
  Scrape next 3 months
  ↓
  Insert ~1500 events to database
  ↓

Tier 2: Daily (Every day, 06:00 UTC)
  ↓
  Scrape last 3 + next 7 days
  ↓
  Compare with database
  ↓
  Add new events + update actuals
  ↓

Tier 3: Real-Time (Every 5 minutes, 24/7)
  ↓
  Scrape today's events
  ↓
  Find actual values released
  ↓
  Update database fields
  ↓

Database (PostgreSQL)
  ↓
  Persistent storage with audit trail
```

---

## 🔍 Monitoring

### Check Database Size
```python
from database import get_db_manager
db = get_db_manager()
print(f"Events: {db.count_events()}")
```

### View Sync History
```python
from database import get_db_manager
db = get_db_manager()
logs = db.get_latest_sync_log(limit=10)
for log in logs:
    print(f"{log['job_name']}: {log['status']} - {log['events_added']} added, {log['events_updated']} updated")
```

### Check Logs
```bash
tail -100 automation.log | grep -E "INFO|ERROR"
```

---

## ⚠️ Important Notes

1. **First Run Time**
   - Monthly updater will take 30-45 minutes
   - It scrapes multiple weeks with rate limiting
   - Don't interrupt the process

2. **Daily Sync**
   - Runs after monthly updater completes
   - Incremental sync (only new/changed data)
   - Takes ~10-15 minutes

3. **Real-Time Updates**
   - Only updates if actual value is released
   - Runs every 5 minutes automatically
   - Silent on non-release days

4. **Data Integrity**
   - Unique constraint prevents duplicates
   - Audit log tracks all changes
   - Old data preserved

---

## ✅ Verification Checklist

- [ ] Database connected and schema created
- [ ] Monthly updater completed (check event count)
- [ ] Daily sync tested successfully
- [ ] Real-time fetcher tested successfully
- [ ] GitHub Secrets configured (5 secrets)
- [ ] Workflows visible in Actions tab
- [ ] Workflows are enabled
- [ ] Manual workflow trigger successful

---

## 📞 Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Check .env file, verify IP 34.55.195.199 accessible |
| "Table does not exist" | Run database_schema.sql |
| No events after 1 hour | Check automation.log for errors |
| Workflow not running | Verify GitHub Secrets are set correctly |
| Actual values not updating | Check if events released during 5-min window |

---

## 🎓 Learning Resources

- Full guide: `README_AUTOMATION.md`
- Database schema: `database_schema.sql`
- Config options: `config.yaml`
- Workflow definitions: `.github/workflows/*.yml`

---

## 🚀 Next Actions

1. **Wait for monthly updater to complete** (~30-45 min)
2. **Verify data in database**
3. **Set up GitHub Secrets**
4. **Push to GitHub**
5. **Enable workflows**
6. **Test each workflow manually**

---

**Everything is ready to go!** 🎉

The system is designed to run completely automatically once GitHub Actions is set up.

