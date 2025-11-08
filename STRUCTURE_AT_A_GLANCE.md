# Project Structure - At a Glance

## Current Layout

```
News-Calendar/
│
├── 📖 DOCUMENTATION (Start Here)
│   ├── SCRAPER_ARCHITECTURE_ANALYSIS.md    ← System deep dive
│   ├── PROJECT_STRUCTURE.md                ← Development roadmap
│   ├── REORGANIZATION_SUMMARY.md           ← What we did
│   └── STRUCTURE_AT_A_GLANCE.md            ← This file
│
├── 📚 REFERENCE (Learn From This)
│   └── old_structure/
│       ├── FINAL_TOOLS_OUTPUT/
│       │   ├── scraper_core.py             ← Core scraping
│       │   ├── database.py                 ← DB operations
│       │   ├── daily_sync.py               ← Job example
│       │   ├── realtime_fetcher.py         ← Real-time example
│       │   └── ... (other utilities)
│       └── github_workflows/               ← Old automation
│
├── 🚀 NEW IMPLEMENTATION (Build Here)
│   └── scraper_2.2/
│       ├── README.md                       ← Getting started
│       ├── requirements.txt                ← Dependencies
│       ├── config.yaml                     ← Config template
│       ├── .env.example                    ← Env template
│       │
│       ├── src/                            ← Core classes
│       │   ├── scraper.py                  ← (to implement)
│       │   ├── database.py                 ← (to implement)
│       │   ├── cache.py                    ← (to implement)
│       │   └── utils.py                    ← (to implement)
│       │
│       ├── jobs/                           ← Job scripts
│       │   ├── bulk_fetcher.py             ← (to implement)
│       │   ├── realtime_updater.py         ← (to implement)
│       │   └── scheduler.py                ← (to implement)
│       │
│       ├── tests/                          ← Unit tests
│       │   ├── test_scraper.py             ← (to implement)
│       │   ├── test_cache.py               ← (to implement)
│       │   └── test_database.py            ← (to implement)
│       │
│       ├── logs/                           ← Application logs
│       │   └── .gitkeep
│       │
│       └── docs/
│           ├── ARCHITECTURE.md             ← (to implement)
│           └── MIGRATION_GUIDE.md          ← (to implement)
│
└── ⚙️ GITHUB AUTOMATION (Reference)
    └── .github/
        └── workflows/
            ├── monthly-updater.yml
            ├── daily-sync.yml
            └── realtime-fetcher.yml
```

---

## Quick Navigation

### 🎯 I Want To...

**Understand how the scraper works**
→ Read `SCRAPER_ARCHITECTURE_ANALYSIS.md`
→ Study `old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py`

**See the development plan**
→ Read `PROJECT_STRUCTURE.md`
→ Section: "Implementation Map"

**Start building the new system**
→ Read `scraper_2.2/README.md`
→ Follow "Quick Start" section

**Learn from existing code**
→ Open `old_structure/FINAL_TOOLS_OUTPUT/`
→ Read scraper_core.py (308 lines)
→ Read database.py (321 lines)

**Understand the data flow**
→ Read `SCRAPER_ARCHITECTURE_ANALYSIS.md`
→ Section: "Data Flow Diagram"

**See what was reorganized**
→ Read `REORGANIZATION_SUMMARY.md`
→ Section: "What Was Done"

**Reference old job patterns**
→ Study `old_structure/FINAL_TOOLS_OUTPUT/daily_sync.py`
→ Study `old_structure/FINAL_TOOLS_OUTPUT/realtime_fetcher.py`

---

## 📊 System Overview

### Three Job Frequencies

```
┌─────────────────────────────────────────────────────────┐
│ Old System (What Currently Exists)                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ MONTHLY (1st of month, 12:00 UTC)                      │
│ └─ Backfill previous month + next 3 months             │
│    └─ Run: monthly_updater.py                          │
│    └─ Scrape: Full 4-month window                      │
│    └─ Action: Insert to DB                             │
│                                                         │
│ DAILY (6:00 AM UTC)                                    │
│ └─ Refresh past 3 days + next 7 days                   │
│    └─ Run: daily_sync.py                               │
│    └─ Scrape: 10-day window                            │
│    └─ Action: Insert new + Update actuals              │
│                                                         │
│ REAL-TIME (Every 5 minutes)                            │
│ └─ Update actual values for today                      │
│    └─ Run: realtime_fetcher.py                         │
│    └─ Scrape: Today only                               │
│    └─ Action: Update actuals only                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📈 What We're Building

```
┌─────────────────────────────────────────────────────────┐
│ New System (scraper_2.2/)                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ BULK FETCH (Every 4 hours)                             │
│ └─ Fetch today + adjacent days                         │
│    └─ Run: bulk_fetcher.py                             │
│    └─ Cache to JSON/SQLite                             │
│    └─ Insert new events to DB                          │
│                                                         │
│ REAL-TIME (Every 5 minutes)                            │
│ └─ Read cached today's events                          │
│    └─ Run: realtime_updater.py                         │
│    └─ Fetch only actuals                               │
│    └─ Update DB + cache if changed                     │
│                                                         │
│ BENEFIT: 97% fewer browser loads                       │
│          Faster 5-minute updates                       │
│          Smarter caching strategy                      │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔑 Core Concepts

### HTML Parsing (What We're Scraping)

```html
<tr class="calendar__row">
  <td>Date</td>           <!-- Nov 7 -->
  <td>Time</td>           <!-- 13:30 -->
  <td>Currency</td>       <!-- USD -->
  <td>Impact</td>         <!-- ⭐⭐⭐ -->
  <td>Event Title</td>    <!-- CPI Release -->
  <td>Actual</td>         <!-- 3.2% (or empty if not released) -->
  <td>Forecast</td>       <!-- 3.1% -->
  <td>Previous</td>       <!-- 3.0% -->
</tr>
```

### Database Schema

```sql
Economic_Calendar_FF (
  date           DATE,
  time           TEXT,
  currency       TEXT,          -- USD, EUR, GBP, JPY, etc.
  impact         TEXT,          -- high, medium, low, unknown
  event          TEXT,          -- Event name
  actual         TEXT,          -- Released value (empty until event)
  forecast       TEXT,          -- Expected value
  previous       TEXT,          -- Previous period value
  created_at     TIMESTAMP,
  updated_at     TIMESTAMP,
  PRIMARY KEY (date, currency, event)  -- Prevents duplicates
)
```

### Job Execution Pattern

```python
# Pattern used by all jobs
1. Load configuration (config.yaml + .env)
2. Initialize scraper
3. Fetch data from ForexFactory
4. Transform data (parse HTML, classify impact)
5. Connect to database
6. Insert/Update records
7. Log results to sync_log table
8. Handle errors and cleanup
```

---

## 📝 Key Files Summary

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| `SCRAPER_ARCHITECTURE_ANALYSIS.md` | 300+ | System analysis | ✅ Done |
| `PROJECT_STRUCTURE.md` | 400+ | Development roadmap | ✅ Done |
| `REORGANIZATION_SUMMARY.md` | 350+ | What we did | ✅ Done |
| `scraper_2.2/README.md` | 300+ | Getting started | ✅ Done |
| `old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py` | 308 | Core scraper | ✅ Reference |
| `old_structure/FINAL_TOOLS_OUTPUT/database.py` | 321 | DB operations | ✅ Reference |
| `scraper_2.2/src/scraper.py` | TBD | New scraper | ⏳ To build |
| `scraper_2.2/src/cache.py` | TBD | New cache | ⏳ To build |
| `scraper_2.2/src/database.py` | TBD | New database | ⏳ To build |
| `scraper_2.2/jobs/bulk_fetcher.py` | TBD | Bulk fetch job | ⏳ To build |
| `scraper_2.2/jobs/realtime_updater.py` | TBD | Real-time job | ⏳ To build |

---

## 🎯 Development Checklist

### Phase 1: Setup ✅
- [x] Analyze old system
- [x] Organize directories
- [x] Create documentation
- [x] Set up structure

### Phase 2: Core Implementation ⏳
- [ ] Implement scraper.py
- [ ] Implement cache.py
- [ ] Implement database.py
- [ ] Test core components

### Phase 3: Jobs ⏳
- [ ] Implement bulk_fetcher.py
- [ ] Implement realtime_updater.py
- [ ] Implement scheduler.py

### Phase 4: Quality ⏳
- [ ] Write unit tests
- [ ] Test manually
- [ ] Handle edge cases
- [ ] Document architecture

### Phase 5: Deployment ⏳
- [ ] Configure GitHub Actions
- [ ] Deploy to production
- [ ] Monitor job runs
- [ ] Validate data quality

---

## 🚀 Getting Started (TL;DR)

### Step 1: Read Documentation (30 min)
```bash
1. This file (STRUCTURE_AT_A_GLANCE.md) - 5 min
2. SCRAPER_ARCHITECTURE_ANALYSIS.md - 15 min
3. scraper_2.2/README.md - 10 min
```

### Step 2: Study Old Code (45 min)
```bash
1. old_structure/FINAL_TOOLS_OUTPUT/scraper_core.py - 20 min
2. old_structure/FINAL_TOOLS_OUTPUT/database.py - 15 min
3. old_structure/FINAL_TOOLS_OUTPUT/daily_sync.py - 10 min
```

### Step 3: Setup Environment (15 min)
```bash
cd scraper_2.2/
cp .env.example .env
cp config.yaml.example config.yaml
# Edit .env and config.yaml
pip install -r requirements.txt
```

### Step 4: Implement (3-5 days)
```bash
1. src/scraper.py - 1 day
2. src/cache.py - 1 day
3. src/database.py - 1 day
4. jobs/ - 1-2 days
5. tests/ - 1 day
```

### Step 5: Deploy (1 day)
```bash
1. Test manually
2. Configure GitHub Actions
3. Monitor first runs
4. Validate data quality
```

---

## 💾 File Locations Reference

| What | Location |
|------|----------|
| System analysis | `SCRAPER_ARCHITECTURE_ANALYSIS.md` |
| Development plan | `PROJECT_STRUCTURE.md` |
| Organization summary | `REORGANIZATION_SUMMARY.md` |
| This quick ref | `STRUCTURE_AT_A_GLANCE.md` |
| New code | `scraper_2.2/` |
| Old code (ref) | `old_structure/FINAL_TOOLS_OUTPUT/` |
| Workflows | `.github/workflows/` |
| Logs | `scraper_2.2/logs/` |

---

## 📞 Common Questions

**Q: Should I modify old_structure/?**
A: No. Read it to learn, don't modify. Build new code in scraper_2.2/

**Q: Where do I start coding?**
A: Start with scraper_2.2/src/scraper.py (reference old scraper_core.py)

**Q: How do I understand the database?**
A: Read old_structure/FINAL_TOOLS_OUTPUT/database.py (321 lines, well-commented)

**Q: Can I keep using the old system?**
A: Yes! Both systems can coexist. New system improves on old.

**Q: What's the caching optimization?**
A: Bulk fetch every 4 hours, filter for today every 5 minutes (97% fewer page loads)

**Q: How long to implement?**
A: 3-5 days for full implementation + testing

---

## ✨ What's Ready Now

- ✅ Complete architecture analysis
- ✅ Detailed development roadmap
- ✅ Organized file structure
- ✅ Getting started guides
- ✅ Reference materials
- ✅ Documentation

## ⏳ What's Next

- ⏳ Implement scraper_2.2/src/ components
- ⏳ Implement scraper_2.2/jobs/ scripts
- ⏳ Write tests
- ⏳ Deploy and monitor

---

**Last Updated:** November 8, 2025
**Status:** Ready for implementation

Start with: `SCRAPER_ARCHITECTURE_ANALYSIS.md` 📖
