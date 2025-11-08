-- ForexFactory Economic Calendar Database Schema
-- PostgreSQL 12+

-- Create main events table
CREATE TABLE IF NOT EXISTS forex_events (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    time VARCHAR(20),
    currency VARCHAR(3) NOT NULL,
    impact VARCHAR(20),
    event TEXT NOT NULL,
    actual VARCHAR(100),
    forecast VARCHAR(100),
    previous VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint: prevent duplicate events same day/currency/title
    CONSTRAINT unique_event UNIQUE(date, currency, event)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_forex_events_date ON forex_events(date);
CREATE INDEX IF NOT EXISTS idx_forex_events_currency ON forex_events(currency);
CREATE INDEX IF NOT EXISTS idx_forex_events_impact ON forex_events(impact);
CREATE INDEX IF NOT EXISTS idx_forex_events_event ON forex_events(event);
CREATE INDEX IF NOT EXISTS idx_forex_events_date_currency ON forex_events(date, currency);

-- Create audit log table to track updates
CREATE TABLE IF NOT EXISTS forex_events_audit (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES forex_events(id) ON DELETE CASCADE,
    field_changed VARCHAR(50),
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50)  -- 'monthly_updater', 'daily_sync', 'realtime_fetcher'
);

-- Create sync log table for monitoring job runs
CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(50) NOT NULL,
    job_type VARCHAR(20) NOT NULL,  -- 'monthly', 'daily', 'realtime'
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    events_processed INTEGER,
    events_added INTEGER,
    events_updated INTEGER,
    errors INTEGER,
    status VARCHAR(20),  -- 'running', 'success', 'failed'
    error_message TEXT,
    run_id VARCHAR(100)  -- GitHub Actions run ID
);

-- Create index on sync log for quick queries
CREATE INDEX IF NOT EXISTS idx_sync_log_job_name ON sync_log(job_name);
CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status);

-- Create function to auto-update 'updated_at' column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating 'updated_at'
CREATE TRIGGER trigger_update_updated_at
BEFORE UPDATE ON forex_events
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (if needed for application user)
-- GRANT SELECT, INSERT, UPDATE ON forex_events TO forexfactory_app;
-- GRANT SELECT, INSERT ON sync_log TO forexfactory_app;
-- GRANT SELECT, INSERT ON forex_events_audit TO forexfactory_app;
