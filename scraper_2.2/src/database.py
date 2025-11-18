#!/usr/bin/env python3
"""
Enhanced Database Manager for ForexFactory automation
Handles PostgreSQL connections, UPSERT operations, and data operations
"""

import logging
import os
from datetime import datetime
from contextlib import contextmanager
import psycopg2
from psycopg2 import sql, pool, extras
from config import describe_db_target

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL database manager with connection pooling and UPSERT support"""

    def __init__(self, host, port, database, user, password, pool_size=5):
        """Initialize database connection pool"""
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, pool_size,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            logger.info(
                f"Database connection pool created: "
                f"{describe_db_target(host, port, database, user)}"
            )
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    @contextmanager
    def get_cursor(self, conn=None):
        """Get a cursor, optionally from a specific connection"""
        if conn is None:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                    yield cursor
                    conn.commit()
        else:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                yield cursor

    def close_all(self):
        """Close all connections in the pool"""
        self.pool.closeall()
        logger.info("All database connections closed")

    # ===== CALENDAR EVENTS TABLE OPERATIONS (WITH UPSERT) =====

    def upsert_events(self, events_list, source_scope="unknown"):
        """
        UPSERT events into Economic_Calendar_FF table
        Inserts new events, updates existing ones based on event_uid

        Args:
            events_list: List of dicts with keys:
                event_uid, date, time, time_zone, time_utc, currency, impact,
                event, actual, actual_status, forecast, previous, source_scope
            source_scope: Source of data (day, week, month)

        Returns:
            Tuple: (total_inserted, total_updated, total_processed)
        """
        inserted = 0
        updated = 0
        processed = 0

        query = """
            INSERT INTO Economic_Calendar_FF (
                event_uid, date, time, time_zone, time_utc, currency, impact,
                event, actual, actual_status, forecast, previous, source_scope,
                created_at, last_updated
            )
            VALUES (
                %(event_uid)s, %(date)s, %(time)s, %(time_zone)s, %(time_utc)s,
                %(currency)s, %(impact)s, %(event)s, %(actual)s, %(actual_status)s,
                %(forecast)s, %(previous)s, %(source_scope)s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            ON CONFLICT (event_uid) DO UPDATE SET
                actual = EXCLUDED.actual,
                actual_status = EXCLUDED.actual_status,
                forecast = EXCLUDED.forecast,
                previous = EXCLUDED.previous,
                source_scope = EXCLUDED.source_scope,
                time_zone = EXCLUDED.time_zone,
                time_utc = EXCLUDED.time_utc,
                last_updated = CURRENT_TIMESTAMP
            WHERE (
                EXCLUDED.actual IS DISTINCT FROM Economic_Calendar_FF.actual OR
                EXCLUDED.forecast IS DISTINCT FROM Economic_Calendar_FF.forecast OR
                EXCLUDED.previous IS DISTINCT FROM Economic_Calendar_FF.previous OR
                EXCLUDED.actual_status IS DISTINCT FROM Economic_Calendar_FF.actual_status
            )
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for event in events_list:
                        # Clean empty strings to NULL
                        event = {k: (v if v and str(v).strip() else None) for k, v in event.items()}
                        event['source_scope'] = source_scope

                        try:
                            cursor.execute(query, event)
                            processed += 1

                            # Check if insert or update
                            if cursor.rowcount > 0:
                                # In UPSERT, rowcount > 0 means insert happened
                                inserted += 1
                            else:
                                # rowcount == 0 might mean conflict but no change
                                # Try to count actual updates separately
                                pass

                        except psycopg2.IntegrityError:
                            # Handle constraint violations gracefully
                            logger.warning(f"Constraint violation for event: {event.get('event_uid')}")
                            conn.rollback()

                    conn.commit()
                    logger.info(
                        f"UPSERTED {processed} events: "
                        f"{inserted} inserted, {processed - inserted} skipped/updated "
                        f"(source: {source_scope})"
                    )

        except Exception as e:
            logger.error(f"Error upserting events: {e}")
            raise

        return inserted, processed - inserted, processed

    def insert_events(self, events_list, source="unknown"):
        """
        Insert events into Economic_Calendar_FF table, skip duplicates (legacy method)

        Args:
            events_list: List of dicts with keys: date, time, currency, impact, event, actual, forecast, previous
            source: Source of data (monthly_updater, daily_sync, realtime_fetcher)

        Returns:
            Tuple: (total_inserted, total_skipped)
        """
        inserted = 0
        skipped = 0

        query = """
            INSERT INTO Economic_Calendar_FF (date, time, currency, impact, event, actual, forecast, previous, created_at)
            VALUES (%(date)s, %(time)s, %(currency)s, %(impact)s, %(event)s, %(actual)s, %(forecast)s, %(previous)s, CURRENT_TIMESTAMP)
            ON CONFLICT (date, currency, event) DO NOTHING
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for event in events_list:
                        # Clean empty strings to NULL
                        event = {k: (v if v and str(v).strip() else None) for k, v in event.items()}

                        cursor.execute(query, event)
                        if cursor.rowcount > 0:
                            inserted += 1
                        else:
                            skipped += 1

                conn.commit()
                logger.info(f"Inserted {inserted} events, skipped {skipped} duplicates (source: {source})")
        except Exception as e:
            logger.error(f"Error inserting events: {e}")
            raise

        return inserted, skipped

    def update_actual_values(self, updates_list):
        """
        Update actual values for events only if currently NULL

        Args:
            updates_list: List of dicts with keys: event_uid, actual, actual_status

        Returns:
            Number of rows updated
        """
        updated = 0

        query = """
            UPDATE Economic_Calendar_FF
            SET actual = %(actual)s, actual_status = %(actual_status)s, last_updated = CURRENT_TIMESTAMP
            WHERE event_uid = %(event_uid)s
            AND (actual IS NULL OR actual = '')
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for update in updates_list:
                        cursor.execute(query, update)
                        updated += cursor.rowcount

                conn.commit()
                logger.info(f"Updated {updated} actual values")
        except Exception as e:
            logger.error(f"Error updating actual values: {e}")
            raise

        return updated

    def get_events_by_date_range(self, start_date, end_date):
        """
        Get all events within a date range

        Args:
            start_date: Date string (YYYY-MM-DD) or relative format
            end_date: Date string (YYYY-MM-DD) or relative format

        Returns:
            List of dicts containing event data
        """
        query = """
            SELECT event_uid, date, time, time_zone, time_utc, currency, impact, event,
                   actual, actual_status, forecast, previous, source_scope, last_updated
            FROM Economic_Calendar_FF
            WHERE date >= %(start_date)s AND date <= %(end_date)s
            ORDER BY date, time
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, {'start_date': start_date, 'end_date': end_date})
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            raise

    def get_events_by_currency_and_impact(self, currency=None, impact=None):
        """
        Get events filtered by currency and/or impact

        Args:
            currency: Currency code (e.g., 'USD') or None for all
            impact: Impact level (high/medium/low/unknown) or None for all

        Returns:
            List of dicts containing event data
        """
        query = """
            SELECT event_uid, date, time, time_zone, time_utc, currency, impact, event,
                   actual, actual_status, forecast, previous, source_scope, last_updated
            FROM Economic_Calendar_FF
            WHERE 1=1
        """
        params = {}

        if currency:
            query += " AND currency = %(currency)s"
            params['currency'] = currency

        if impact:
            query += " AND impact = %(impact)s"
            params['impact'] = impact

        query += " ORDER BY date DESC"

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            raise

    def count_events(self):
        """Get total count of events in database"""
        query = "SELECT COUNT(*) as count FROM Economic_Calendar_FF"

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Error counting events: {e}")
            raise

    def get_events_by_source_scope(self, source_scope):
        """Get all events from a specific source scope"""
        query = """
            SELECT event_uid, date, time, time_zone, time_utc, currency, impact, event,
                   actual, actual_status, forecast, previous, source_scope, last_updated
            FROM Economic_Calendar_FF
            WHERE source_scope = %(source_scope)s
            ORDER BY date DESC
        """

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, {'source_scope': source_scope})
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching events by source_scope: {e}")
            raise

    # ===== SYNC_LOG TABLE OPERATIONS =====

    def log_sync_start(self, job_name, job_type, run_id=None):
        """
        Log the start of a sync job
        Returns: log_id for later update
        """
        query = """
            INSERT INTO sync_log (job_name, job_type, start_time, status, run_id)
            VALUES (%(job_name)s, %(job_type)s, CURRENT_TIMESTAMP, 'running', %(run_id)s)
            RETURNING id
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, {
                        'job_name': job_name,
                        'job_type': job_type,
                        'run_id': run_id or ''
                    })
                    log_id = cursor.fetchone()[0]
                    conn.commit()
                    return log_id
        except Exception as e:
            logger.error(f"Error logging sync start: {e}")
            raise

    def log_sync_complete(self, log_id, events_processed, events_added, events_updated, errors=0, error_message=None):
        """Log the completion of a sync job"""
        query = """
            UPDATE sync_log
            SET end_time = CURRENT_TIMESTAMP,
                events_processed = %(events_processed)s,
                events_added = %(events_added)s,
                events_updated = %(events_updated)s,
                errors = %(errors)s,
                error_message = %(error_message)s,
                status = CASE WHEN %(errors)s > 0 THEN 'failed' ELSE 'success' END
            WHERE id = %(log_id)s
        """

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, {
                        'log_id': log_id,
                        'events_processed': events_processed,
                        'events_added': events_added,
                        'events_updated': events_updated,
                        'errors': errors,
                        'error_message': error_message
                    })
                    conn.commit()
                    logger.info(f"Sync job {log_id} logged: {events_added} added, {events_updated} updated")
        except Exception as e:
            logger.error(f"Error logging sync completion: {e}")
            raise

    def get_latest_sync_log(self, job_name=None, limit=10):
        """Get latest sync log entries"""
        query = """
            SELECT id, job_name, job_type, start_time, end_time, events_processed,
                   events_added, events_updated, errors, status
            FROM sync_log
            WHERE 1=1
        """
        params = {}

        if job_name:
            query += " AND job_name = %(job_name)s"
            params['job_name'] = job_name

        query += " ORDER BY start_time DESC LIMIT %(limit)s"
        params['limit'] = limit

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error fetching sync logs: {e}")
            raise


def get_db_manager(config_dict=None):
    """
    Factory function to create DatabaseManager from config dict or environment

    Args:
        config_dict: Optional dict with keys: host, port, database, user, password, pool_size

    Returns:
        DatabaseManager instance
    """
    if config_dict is None:
        config_dict = {}

    db_config = {
        'host': config_dict.get('host') or os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(config_dict.get('port') or os.getenv('POSTGRES_PORT', 5432)),
        'database': config_dict.get('database') or os.getenv('POSTGRES_DB', 'forexfactory'),
        'user': config_dict.get('user') or os.getenv('POSTGRES_USER', 'postgres'),
        'password': config_dict.get('password') or os.getenv('POSTGRES_PASSWORD', 'postgres'),
        'pool_size': int(config_dict.get('pool_size', 5))
    }

    return DatabaseManager(**db_config)
