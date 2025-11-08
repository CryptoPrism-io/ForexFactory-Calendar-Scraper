-- Migration 001: Extend Economic_Calendar_FF table with new fields for integrated scraper
-- This migration adds columns to support the enhanced ForexFactory data pipeline

-- Add new columns to Economic_Calendar_FF table
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS event_uid TEXT UNIQUE;
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS time_zone VARCHAR(10) DEFAULT 'GMT';
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS time_utc VARCHAR(20);
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS actual_status VARCHAR(20);
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS source_scope VARCHAR(20) DEFAULT 'unknown';
ALTER TABLE Economic_Calendar_FF ADD COLUMN IF NOT EXISTS last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

-- Create index on event_uid for faster lookups
CREATE INDEX IF NOT EXISTS idx_economic_calendar_event_uid ON Economic_Calendar_FF(event_uid);

-- Create index on source_scope for filtering
CREATE INDEX IF NOT EXISTS idx_economic_calendar_source_scope ON Economic_Calendar_FF(source_scope);

-- Create index on date and currency for common queries
CREATE INDEX IF NOT EXISTS idx_economic_calendar_date_currency ON Economic_Calendar_FF(date, currency);

-- Update last_updated trigger (optional, if using triggers)
CREATE OR REPLACE FUNCTION update_economic_calendar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists (using correct PostgreSQL syntax)
DROP TRIGGER IF EXISTS update_economic_calendar_timestamp ON Economic_Calendar_FF;

-- Create trigger
CREATE TRIGGER update_economic_calendar_timestamp
    BEFORE UPDATE ON Economic_Calendar_FF
    FOR EACH ROW
    EXECUTE FUNCTION update_economic_calendar_timestamp();

-- Migration complete
SELECT 'Migration 001 completed: Extended Economic_Calendar_FF schema' AS status;
