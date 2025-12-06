# Database Schema Improvement Plan

## Current Problem

The database stores UTC times as **separate DATE and VARCHAR fields**:
- `date_utc` (DATE): "2025-12-05"
- `time_utc` (VARCHAR): "20:00"

This makes it hard to:
- Query by timestamp
- Use PostgreSQL's built-in time functions
- Convert to other timezones
- Do time-based calculations

## Recommended Solution

Add a **combined TIMESTAMPTZ field** that stores the full UTC timestamp:

```sql
ALTER TABLE economic_calendar_ff
ADD COLUMN datetime_utc TIMESTAMPTZ;

COMMENT ON COLUMN economic_calendar_ff.datetime_utc
IS 'Event date and time in UTC (combined from date_utc + time_utc)';
```

## Schema After Migration

```sql
-- Recommended fields:
datetime_utc     TIMESTAMPTZ    -- PRIMARY: Full UTC timestamp (queryable!)
date_utc         DATE           -- LEGACY: Keep for backward compatibility
time_utc         VARCHAR(20)    -- LEGACY: Keep for debugging
time             VARCHAR(32)    -- ORIGINAL: ForexFactory display time
source_timezone  VARCHAR(50)    -- AUDIT: IANA timezone (e.g., "Asia/Kolkata")
time_zone        VARCHAR(10)    -- AUDIT: TZ abbreviation (e.g., "IST")
```

## Migration Steps

### Step 1: Add Column to Database

```sql
-- Add new column
ALTER TABLE economic_calendar_ff
ADD COLUMN IF NOT EXISTS datetime_utc TIMESTAMPTZ;

-- Add comment
COMMENT ON COLUMN economic_calendar_ff.datetime_utc
IS 'Event date and time in UTC (combined from date_utc + time_utc)';

-- Create index for fast queries
CREATE INDEX IF NOT EXISTS idx_economic_calendar_ff_datetime_utc
ON economic_calendar_ff(datetime_utc);
```

### Step 2: Backfill Existing Data

```sql
-- Combine existing date_utc + time_utc into datetime_utc
UPDATE economic_calendar_ff
SET datetime_utc = (
    CASE
        -- Handle special values
        WHEN time_utc IN ('All Day', 'Tentative', 'Day 1', 'Day 2', 'Day 3')
        THEN date_utc::TIMESTAMPTZ  -- Set to midnight UTC

        -- Parse normal times (format: "HH:MM" or "H:MM")
        WHEN time_utc ~ '^\d{1,2}:\d{2}$'
        THEN (date_utc::TEXT || ' ' || time_utc || ':00')::TIMESTAMPTZ

        -- Fallback: midnight UTC
        ELSE date_utc::TIMESTAMPTZ
    END
)
WHERE datetime_utc IS NULL
  AND date_utc IS NOT NULL;
```

### Step 3: Update Scraper Code

Modify `database.py` to populate `datetime_utc` when inserting events:

```python
# In scraper.py - add to event dictionary:
event = {
    # ... existing fields ...
    'datetime_utc': f"{date_utc} {time_utc}:00" if time_utc not in ['All Day', 'Tentative'] else f"{date_utc} 00:00:00",
}

# In database.py - update INSERT query:
INSERT INTO economic_calendar_ff (
    ...,
    date_utc,
    time_utc,
    datetime_utc,  -- NEW
    ...
) VALUES (
    ...,
    %(date_utc)s,
    %(time_utc)s,
    %(datetime_utc)s::TIMESTAMPTZ,  -- NEW
    ...
)
```

## Usage Examples After Migration

### Query Events in Last 24 Hours
```sql
SELECT * FROM economic_calendar_ff
WHERE datetime_utc >= NOW() - INTERVAL '24 hours'
ORDER BY datetime_utc DESC;
```

### Query Events Between Times
```sql
SELECT * FROM economic_calendar_ff
WHERE datetime_utc BETWEEN '2025-12-05 10:00:00+00'
                      AND '2025-12-06 10:00:00+00'
ORDER BY datetime_utc;
```

### Convert to Different Timezone
```sql
SELECT
    event,
    datetime_utc,
    datetime_utc AT TIME ZONE 'America/New_York' AS "New York Time",
    datetime_utc AT TIME ZONE 'Europe/London' AS "London Time",
    datetime_utc AT TIME ZONE 'Asia/Kolkata' AS "India Time"
FROM economic_calendar_ff
WHERE date_utc = CURRENT_DATE;
```

### Extract Time Components
```sql
SELECT
    event,
    datetime_utc,
    EXTRACT(HOUR FROM datetime_utc) AS hour_utc,
    EXTRACT(DOW FROM datetime_utc) AS day_of_week,
    date_trunc('hour', datetime_utc) AS hour_bucket
FROM economic_calendar_ff
WHERE datetime_utc >= CURRENT_DATE;
```

### Group by Hour
```sql
SELECT
    date_trunc('hour', datetime_utc) AS hour_bucket,
    COUNT(*) AS event_count
FROM economic_calendar_ff
WHERE datetime_utc >= CURRENT_DATE
GROUP BY hour_bucket
ORDER BY hour_bucket;
```

## Benefits After Migration

### 1. Easier Queries ✅
```sql
-- Before (HARD):
WHERE date_utc = '2025-12-06'
  AND time_utc::TIME >= '10:00'::TIME

-- After (EASY):
WHERE datetime_utc >= '2025-12-06 10:00:00+00'
```

### 2. Timezone Conversion ✅
```sql
-- Before (IMPOSSIBLE):
-- Can't convert VARCHAR time to other timezones

-- After (EASY):
SELECT datetime_utc AT TIME ZONE 'America/New_York'
```

### 3. Time Math ✅
```sql
-- Before (HARD):
-- Need complex string parsing

-- After (EASY):
WHERE datetime_utc > NOW() - INTERVAL '1 hour'
```

### 4. Indexing ✅
```sql
-- Before:
-- Can only index date, not time

-- After:
CREATE INDEX idx_datetime ON economic_calendar_ff(datetime_utc);
-- Fast queries by timestamp!
```

## Backward Compatibility

**Keep existing fields** for backward compatibility:
- `date_utc` - Still useful for daily aggregations
- `time_utc` - Still useful for debugging
- `time` - Original ForexFactory time (audit trail)
- `source_timezone` - IANA timezone (audit trail)

**New field** is additive:
- `datetime_utc` - Primary field for time-based queries
- Automatically calculated from `date_utc + time_utc`
- Can be regenerated if needed

## Implementation Order

1. ✅ **Run SQL migration** (add column + backfill)
2. ✅ **Update scraper code** (populate datetime_utc)
3. ✅ **Test queries** (verify datetime_utc is correct)
4. ✅ **Update application** (use datetime_utc in queries)
5. ⏭️ **(Later) Deprecate** old fields (once everything uses datetime_utc)

## Testing the Migration

```sql
-- Verify backfill worked correctly
SELECT
    event,
    date_utc,
    time_utc,
    datetime_utc,
    -- Check they match:
    (date_utc::TEXT || ' ' || time_utc || ':00')::TIMESTAMPTZ AS "Expected",
    CASE
        WHEN datetime_utc = (date_utc::TEXT || ' ' || time_utc || ':00')::TIMESTAMPTZ
        THEN '✅ MATCH'
        ELSE '❌ MISMATCH'
    END AS "Validation"
FROM economic_calendar_ff
WHERE time_utc NOT IN ('All Day', 'Tentative', 'Day 1', 'Day 2', 'Day 3')
LIMIT 10;
```

## Example: Consumer Credit Event

### Before Migration
```
date_utc:  2025-12-05
time_utc:  "20:00"        ← VARCHAR (string!)
```

**Query**:
```sql
-- Awkward!
WHERE date_utc = '2025-12-05' AND time_utc = '20:00'
```

### After Migration
```
datetime_utc: 2025-12-05 20:00:00+00  ← TIMESTAMPTZ (proper type!)
date_utc:     2025-12-05              ← Keep for compatibility
time_utc:     "20:00"                 ← Keep for debugging
```

**Query**:
```sql
-- Clean!
WHERE datetime_utc = '2025-12-05 20:00:00+00'

-- Or range:
WHERE datetime_utc BETWEEN '2025-12-05 00:00:00+00'
                      AND '2025-12-05 23:59:59+00'

-- Or relative:
WHERE datetime_utc >= NOW() - INTERVAL '1 day'
```

---

## Summary

| Aspect | Current (❌) | Recommended (✅) |
|--------|-------------|-----------------|
| **Date Field** | `date_utc` (DATE) | Keep + add `datetime_utc` |
| **Time Field** | `time_utc` (VARCHAR) | Keep + add `datetime_utc` |
| **Combined** | None | `datetime_utc` (TIMESTAMPTZ) |
| **Queryability** | Hard (string parsing) | Easy (native timestamp) |
| **Timezone Conversion** | Impossible | Native support |
| **Time Math** | Complex | Built-in operators |
| **Indexing** | Date only | Full timestamp |

**Recommendation**: Add `datetime_utc TIMESTAMPTZ` field and use it as the primary timestamp field going forward.
