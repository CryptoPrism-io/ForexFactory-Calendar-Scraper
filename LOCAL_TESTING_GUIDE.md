# Local Testing Guide - CSV-Based Automation

## Overview

Before pushing to GitHub Actions with PostgreSQL, we're testing the automation logic locally with CSV files. This validates:

1. ✅ Data scraping from ForexFactory
2. ✅ Reconciliation logic (new vs existing)
3. ✅ Actual value updates
4. ✅ File management and backups

---

## 🚀 Current Test Run

**Started:** Now
**Script:** `daily_sync_csv.py`
**Action:** Scraping last 3 + next 7 days, reconciling with existing data
**Status:** ⏳ Running (30-45 minutes)

---

## 📁 CSV-Based Scripts (Local Testing)

### 1. **monthly_updater_csv.py**
Fetches 3 months of upcoming events and saves to CSV.

```bash
python monthly_updater_csv.py
```

**Output:**
- `forexfactory_events_MONTHLY.csv` - New monthly data

**Purpose:**
- Test monthly fetch logic
- Verify scraper with long date range
- Check impact classification

---

### 2. **daily_sync_csv.py** ← Currently Running
Fetches last 3 + next 7 days, reconciles with existing data.

```bash
python daily_sync_csv.py
```

**Input:**
- `forexfactory_events_FINAL.csv` - Your existing data

**Output:**
- `forexfactory_events_FINAL.csv` - Updated (merged)
- `forexfactory_events_BACKUP.csv` - Backup of original
- `forexfactory_events_DAILY.csv` - New events scraped today
- `sync_summary.txt` - Summary of sync

**Purpose:**
- Test reconciliation logic
- Verify deduplication works
- Check data merge logic
- Validate backup creation

---

### 3. **realtime_fetcher_csv.py**
Updates actual values for today's events.

```bash
python realtime_fetcher_csv.py
```

**Input:**
- `forexfactory_events_FINAL.csv` - Main data

**Output:**
- `forexfactory_events_FINAL.csv` - Updated with actuals
- `forexfactory_events_REALTIME.csv` - Today's events

**Purpose:**
- Test real-time value capture
- Verify selective updates (only empty actuals)
- Check logging

---

## 📊 Files Created During Test

```
FINAL_TOOLS_OUTPUT/
├── forexfactory_events_FINAL.csv       ← Main file (updated)
├── forexfactory_events_BACKUP.csv      ← Backup from last run
├── forexfactory_events_DAILY.csv       ← Today's scraped events
├── forexfactory_events_REALTIME.csv    ← Real-time updates
├── forexfactory_events_MONTHLY.csv     ← Monthly data
├── sync_summary.txt                    ← Summary of last sync
└── automation.log                      ← Execution log
```

---

## 🔍 Monitoring the Test

### Watch Logs in Real-Time
```bash
tail -f automation.log
```

### Check Progress
```bash
# Count current events in main file
python -c "import pandas as pd; df = pd.read_csv('forexfactory_events_FINAL.csv'); print(f'Total events: {len(df)}')"

# Count by currency
python -c "import pandas as pd; df = pd.read_csv('forexfactory_events_FINAL.csv'); print(df['Currency'].value_counts())"

# Count by impact
python -c "import pandas as pd; df = pd.read_csv('forexfactory_events_FINAL.csv'); print(df['Impact'].value_counts())"
```

---

## ✅ Validation Checklist

After each script completes, verify:

### ✓ Daily Sync Validation
- [ ] Execution completed without errors
- [ ] `sync_summary.txt` shows expected numbers
- [ ] `forexfactory_events_FINAL.csv` has more events (or same if no new)
- [ ] `forexfactory_events_BACKUP.csv` created
- [ ] No duplicate entries (check by Date + Currency + Event)
- [ ] Backup is identical to original

**Check duplicates:**
```python
import pandas as pd
df = pd.read_csv('forexfactory_events_FINAL.csv')
duplicates = df.duplicated(subset=['Date', 'Currency', 'Event'])
print(f"Duplicate rows: {duplicates.sum()}")
if duplicates.sum() > 0:
    print(df[duplicates])
```

### ✓ Real-Time Fetcher Validation
- [ ] Actual values updated for today's events
- [ ] Only empty Actual fields were updated
- [ ] Existing actual values not overwritten
- [ ] Main file has correct event count

**Check updates:**
```python
import pandas as pd
df = pd.read_csv('forexfactory_events_FINAL.csv')
df_today = df[df['Date'].str.contains('2025-11-08')]
print(f"Events with actual values today: {(df_today['Actual'] != '').sum()}")
```

### ✓ Monthly Updater Validation
- [ ] Execution completed successfully
- [ ] `forexfactory_events_MONTHLY.csv` created
- [ ] Contains events for next 3 months
- [ ] Impact classification applied
- [ ] No errors in log

---

## 🧪 Manual Test Scenarios

### Scenario 1: Test Reconciliation Logic
```bash
# 1. Check current events
python -c "import pandas as pd; print(f'Current: {len(pd.read_csv(\"forexfactory_events_FINAL.csv\"))} events')"

# 2. Run daily sync
python daily_sync_csv.py

# 3. Check results
tail -20 sync_summary.txt
python -c "import pandas as pd; df = pd.read_csv('forexfactory_events_FINAL.csv'); print(f'After sync: {len(df)} events')"
```

### Scenario 2: Test Actual Value Updates
```bash
# 1. Record current state
python -c "import pandas as pd; df = pd.read_csv('forexfactory_events_FINAL.csv'); df_today = df[df['Date'].str.contains('2025-11-08')]; print(f'Events with actual: {(df_today[\"Actual\"] != \"\").sum()}')"

# 2. Run real-time fetcher
python realtime_fetcher_csv.py

# 3. Check updates
tail -20 automation.log | grep Updated
```

### Scenario 3: Test Data Integrity
```bash
# Check for orphaned rows (events without currency, etc.)
python -c "
import pandas as pd
df = pd.read_csv('forexfactory_events_FINAL.csv')
print(f'Total: {len(df)}')
print(f'Missing dates: {df[\"Date\"].isna().sum()}')
print(f'Missing currency: {df[\"Currency\"].isna().sum()}')
print(f'Missing event: {df[\"Event\"].isna().sum()}')
"
```

---

## 📊 Expected Results

### Daily Sync
```
Scraped: 50-100 events (10-day window)
New Added: 0-20 (depends on existing data)
Updated: 0-5 (only if new actual values)
Total in File: 868+ events
Backup Created: ✓
No Duplicates: ✓
```

### Real-Time Fetcher
```
Processed: 10-30 events (today only)
Updated: 0-10 (only new actual values)
Main File: Unchanged size, updated content
Snapshot Created: ✓
```

### Monthly Updater
```
Scraped: 1500-2000 events (3 months)
Duration: 45+ minutes
File Created: forexfactory_events_MONTHLY.csv
Impact Distribution: high 30-40%, medium 30-40%, low 15-25%
```

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| Script hangs | Check if browser window is open; close it |
| "No events scraped" | Website may be blocking requests; try again later |
| CSV not updated | Check automation.log for errors |
| Duplicates appeared | Run script again; deduplication in next sync |
| Backup not created | Check write permissions in directory |

---

## 📈 Performance Notes

- **Scraping 10 days:** ~15-20 minutes
- **Scraping 3 months:** 45+ minutes
- **Reconciliation:** <1 minute
- **CSV write:** <1 second
- **Rate limiting:** 2 sec between requests, 5 sec every 5 requests

---

## ✨ What We're Validating

| Component | CSV Test | Database Later |
|-----------|----------|-----------------|
| Web scraping | ✓ Daily/monthly | Same code |
| Reconciliation | ✓ CSV merge | Different (DB transactions) |
| Impact classification | ✓ Tested | Same code |
| Logging | ✓ File-based | Same code |
| Data deduplication | ✓ CSV drop_duplicates | DB unique constraint |
| Backup strategy | ✓ CSV copy | DB snapshots |

---

## 🎓 Understanding the Logic

### Reconciliation Process
```
New Data (from scrape)
    ↓
Load Existing Data (from CSV)
    ↓
Find New Events (in new, not in existing)
    ↓
Find Updates (in both, with new actual values)
    ↓
Merge: existing + new_events
    ↓
Update: Set actual values
    ↓
Deduplicate: Remove exact duplicates
    ↓
Save to CSV
    ↓
Create Backup (before changes)
```

### Deduplication Key
Events are considered identical if they have:
- Same Date
- Same Currency
- Same Event Name

---

## 📝 Next Steps After CSV Testing

1. **Verify all three scripts work**
   - Monthly updater completes successfully
   - Daily sync reconciles correctly
   - Real-time fetcher updates values

2. **Check data quality**
   - No unwanted duplicates
   - Backup files intact
   - Summary reports accurate

3. **Review logs**
   - No unexpected errors
   - Correct event counts
   - Proper file handling

4. **Then move to GitHub Actions**
   - Same logic, but with PostgreSQL database
   - Automatic scheduling
   - Cloud-based execution

---

## 💡 Key Points

✓ **CSV testing validates core logic** without database
✓ **Same reconciliation code** used in both versions
✓ **Backup strategy** ensures data safety
✓ **Logging** helps track what's happening
✓ **Scalable** to database later

---

**Status:** ✅ Ready for local testing
**Current Test:** Daily sync running
**Next:** Monitor logs, validate results

