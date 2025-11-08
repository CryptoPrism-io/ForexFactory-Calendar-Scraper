#!/usr/bin/env python3
"""
Data reconciliation utilities for ForexFactory
Handles Pandas DataFrame comparison and merging
"""

import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class DataReconciler:
    """Handles data reconciliation between old and new datasets"""

    @staticmethod
    def normalize_dataframe(df):
        """
        Normalize DataFrame for comparison

        Args:
            df: Pandas DataFrame with event data

        Returns:
            Normalized DataFrame
        """
        if df.empty:
            return df

        df = df.copy()

        # Ensure date column is proper date type
        if 'date' in df.columns:
            try:
                df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%dT%H:%M:%S', errors='coerce').dt.date
            except:
                try:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
                except:
                    # If all conversions fail, leave as is
                    pass
        elif 'Date' in df.columns:
            try:
                df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%dT%H:%M:%S', errors='coerce').dt.date
            except:
                try:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
                except:
                    # If all conversions fail, leave as is
                    pass
            df.rename(columns={'Date': 'date'}, inplace=True)

        # Filter out rows with invalid dates (NaT or non-date values)
        if 'date' in df.columns:
            # Remove rows where date is null or not a valid date
            df = df[pd.notna(df['date'])]

        # Normalize column names to lowercase
        df.columns = df.columns.str.lower()

        # Fill empty strings with None for consistency
        df = df.where(pd.notna(df), None)
        df = df.applymap(lambda x: None if isinstance(x, str) and x.strip() == "" else x)

        # Standardize impact levels
        if 'impact' in df.columns:
            df['impact'] = df['impact'].str.lower().str.strip()

        return df

    @staticmethod
    def create_event_key(row):
        """
        Create a unique key for an event (for deduplication)

        Args:
            row: Pandas Series representing a row

        Returns:
            Tuple key: (date, currency, event)
        """
        date_val = row.get('date', '')
        currency = row.get('currency', '')
        event = row.get('event', '')

        return (date_val, currency, event)

    @staticmethod
    def find_new_events(df_new, df_existing):
        """
        Find events in df_new that are not in df_existing

        Args:
            df_new: New scraped data (Pandas DataFrame)
            df_existing: Existing database data (Pandas DataFrame)

        Returns:
            DataFrame with only new events (not in existing)
        """
        logger.info(f"Finding new events: {len(df_new)} new vs {len(df_existing)} existing")

        # Normalize both dataframes
        df_new = DataReconciler.normalize_dataframe(df_new)
        df_existing = DataReconciler.normalize_dataframe(df_existing)

        if df_existing.empty:
            logger.info(f"No existing data, all {len(df_new)} are new")
            return df_new

        # Create keys for comparison
        new_keys = set(DataReconciler.create_event_key(row) for _, row in df_new.iterrows())
        existing_keys = set(DataReconciler.create_event_key(row) for _, row in df_existing.iterrows())

        # Find keys only in new
        only_in_new = new_keys - existing_keys

        logger.info(f"Found {len(only_in_new)} new events")

        # Filter df_new to only include new events
        df_result = df_new[df_new.apply(
            lambda row: DataReconciler.create_event_key(row) in only_in_new,
            axis=1
        )].copy()

        return df_result

    @staticmethod
    def find_updates(df_new, df_existing):
        """
        Find events that need actual value updates

        Args:
            df_new: Newly scraped data (with possible new actual values)
            df_existing: Existing database data

        Returns:
            DataFrame with rows that have actual values to update
        """
        logger.info(f"Finding updates: {len(df_new)} new vs {len(df_existing)} existing")

        # Normalize both dataframes
        df_new = DataReconciler.normalize_dataframe(df_new)
        df_existing = DataReconciler.normalize_dataframe(df_existing)

        if df_existing.empty:
            logger.info("No existing data to update")
            return pd.DataFrame()

        # Filter to events that exist in both datasets
        new_keys = set(DataReconciler.create_event_key(row) for _, row in df_new.iterrows())
        existing_keys = set(DataReconciler.create_event_key(row) for _, row in df_existing.iterrows())

        common_keys = new_keys & existing_keys

        # Filter df_new to only include common events
        df_new_common = df_new[df_new.apply(
            lambda row: DataReconciler.create_event_key(row) in common_keys,
            axis=1
        )].copy()

        # Filter df_existing to only include common events
        df_existing_common = df_existing[df_existing.apply(
            lambda row: DataReconciler.create_event_key(row) in common_keys,
            axis=1
        )].copy()

        # Find events with new actual values
        updates = []
        for idx, new_row in df_new_common.iterrows():
            key = DataReconciler.create_event_key(new_row)

            # Find matching row in existing
            matching_existing = df_existing_common[
                (df_existing_common['date'] == new_row['date']) &
                (df_existing_common['currency'] == new_row['currency']) &
                (df_existing_common['event'] == new_row['event'])
            ]

            if not matching_existing.empty:
                existing_row = matching_existing.iloc[0]

                # Check if new actual value exists and is different
                new_actual = new_row.get('actual')
                existing_actual = existing_row.get('actual')

                if new_actual and new_actual.strip() and (not existing_actual or not existing_actual.strip()):
                    updates.append({
                        'date': new_row['date'],
                        'currency': new_row['currency'],
                        'event': new_row['event'],
                        'actual': new_actual
                    })

        logger.info(f"Found {len(updates)} events to update with actual values")

        if updates:
            return pd.DataFrame(updates)
        else:
            return pd.DataFrame()

    @staticmethod
    def reconcile(df_new, df_existing):
        """
        Full reconciliation: find new events and updates

        Args:
            df_new: Newly scraped data
            df_existing: Existing database data

        Returns:
            Tuple: (df_new_events, df_updates, summary_dict)
        """
        logger.info("Starting full reconciliation...")

        # Find new events
        df_new_events = DataReconciler.find_new_events(df_new, df_existing)

        # Find updates
        df_updates = DataReconciler.find_updates(df_new, df_existing)

        # Summary
        summary = {
            'total_new': len(df_new),
            'total_existing': len(df_existing),
            'new_events_found': len(df_new_events),
            'updates_found': len(df_updates),
            'timestamp': datetime.now().isoformat()
        }

        logger.info(f"Reconciliation complete: {summary}")

        return df_new_events, df_updates, summary

    @staticmethod
    def print_summary(df_new_events, df_updates):
        """
        Print a human-readable summary of reconciliation results

        Args:
            df_new_events: DataFrame of new events
            df_updates: DataFrame of updates
        """
        print("\n" + "="*70)
        print("DATA RECONCILIATION SUMMARY")
        print("="*70)

        print(f"\nNew Events Found: {len(df_new_events)}")
        if not df_new_events.empty:
            print("\nNew Events by Currency:")
            print(df_new_events['currency'].value_counts())

        print(f"\n\nActual Values to Update: {len(df_updates)}")
        if not df_updates.empty:
            print("\nUpdates by Currency:")
            print(df_updates['currency'].value_counts())

        print("\n" + "="*70)


def reconcile_and_insert(df_new, db_manager, date_range_desc=""):
    """
    Convenience function: reconcile new data against DB and insert

    Args:
        df_new: Newly scraped DataFrame
        db_manager: DatabaseManager instance
        date_range_desc: Description of date range (for logging)

    Returns:
        Tuple: (new_count, update_count)
    """
    logger.info(f"Reconciling {date_range_desc}...")

    # Get existing data from DB for same dates
    if not df_new.empty and 'date' in df_new.columns:
        df_new = DataReconciler.normalize_dataframe(df_new)
        min_date = df_new['date'].min()
        max_date = df_new['date'].max()

        logger.info(f"Fetching existing data for {min_date} to {max_date}")
        existing_records = db_manager.get_events_by_date_range(
            str(min_date), str(max_date)
        )

        if existing_records:
            df_existing = pd.DataFrame(existing_records)
        else:
            df_existing = pd.DataFrame()
    else:
        df_existing = pd.DataFrame()

    # Reconcile
    df_new_events, df_updates, summary = DataReconciler.reconcile(df_new, df_existing)

    # Insert new events
    new_count = 0
    if not df_new_events.empty:
        events_list = df_new_events.to_dict('records')
        # Rename 'date' to match DB schema
        events_list = [
            {k.replace('date', 'date').replace('event', 'event'): v
             for k, v in event.items()}
            for event in events_list
        ]
        new_count, _ = db_manager.insert_events(events_list, source="daily_sync")

    # Update actual values
    update_count = 0
    if not df_updates.empty:
        updates_list = df_updates.to_dict('records')
        update_count = db_manager.update_actual_values(updates_list)

    # Print summary
    DataReconciler.print_summary(df_new_events, df_updates)

    return new_count, update_count
