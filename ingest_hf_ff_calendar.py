#!/usr/bin/env python3
# ingest_hf_ff_calendar.py
# Load the Hugging Face FF calendar dataset and upsert into outputs\ff_calendar.sqlite
from __future__ import annotations

import argparse, re, sqlite3, sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np
from datasets import load_dataset
from dateutil import tz

def _py(v):
    """Coerce pandas/NumPy scalars/NaN to plain Python types for SQLite."""
    import pandas as _pd
    import numpy as _np
    try:
        if isinstance(v, _pd.Series):
            v = v.iloc[0] if len(v) else None
    except Exception:
        pass
    try:
        if isinstance(v, _pd.Timestamp):
            return v.isoformat()
    except Exception:
        pass
    try:
        if isinstance(v, _np.generic):
            return v.item()
    except Exception:
        pass
    try:
        if _pd.isna(v):
            return None
    except Exception:
        pass
    return v

IMPACT_MAP = {
    "High Impact Expected": ("high", 3),
    "Medium Impact Expected": ("medium", 2),
    "Low Impact Expected": ("low", 1),
}

@dataclass
class EventRow:
    event_id: str
    currency: str
    impact: str
    impact_num: int
    title: str
    actual: Optional[str]
    forecast: Optional[str]
    previous: Optional[str]
    date_local: str
    time_local: str
    when_tz: str
    when_iso: Optional[str]
    has_specific_time: int
    url: Optional[str]
    is_major: int
    impact_included: int
    source: str = "ff_hf_dataset"

def slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "").lower()).strip("_")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help=r"SQLite path, e.g. outputs\ff_calendar.sqlite")
    ap.add_argument("--years", default="2012-2024", help="Range like 2012-2024 or single year like 2015")
    ap.add_argument("--tz", default="America/New_York", help="Target local timezone for date_local/time_local")
    ap.add_argument("--split", default="train", help="HF split (default: train)")
    args = ap.parse_args()

    # Parse years
    if "-" in args.years:
        y1, y2 = [int(x) for x in args.years.split("-", 1)]
    else:
        y1 = y2 = int(args.years)

    print("[load] datasets:Ehsanrs2/Forex_Factory_Calendar (this may take ~10–20s on first run)")
    ds = load_dataset("Ehsanrs2/Forex_Factory_Calendar", split=args.split)
    df = ds.to_pandas()  # ~83k rows total for full dataset
    # Expected cols per dataset card: DateTime, Currency, Impact, Event, Actual, Forecast, Previous, Detail
    # Timezone note: DateTime has an offset (Asia/Tehran) per dataset card.
    # Convert to tz-aware datetime, then to target tz and UTC.
    df["DateTime"] = pd.to_datetime(df["DateTime"], utc=True)  # respects embedded offset like +03:30

    # Filter by year range in target timezone (so weeks match your candle timezone)
    target_tz = tz.gettz(args.tz)
    df["local_dt"] = df["DateTime"].dt.tz_convert(target_tz)
    df["year_local"] = df["local_dt"].dt.year
    df = df[(df["year_local"] >= y1) & (df["year_local"] <= y2)].copy()

    # Map impact
    def map_impact(raw):
        if pd.isna(raw): return ("unknown", 0)
        raw = str(raw).strip()
        return IMPACT_MAP.get(raw, ("unknown", 0))
    imp_pairs = df["Impact"].map(map_impact)
    df["impact"] = imp_pairs.map(lambda x: x[0])
    df["impact_num"] = imp_pairs.map(lambda x: x[1])

    # Build local date/time strings and UTC ISO
    df["date_local"] = df["local_dt"].dt.strftime("%Y-%m-%d")
    df["time_local"] = df["local_dt"].dt.strftime("%-I:%M%p")  # Windows may need %#I for cmd; fallback below
    # Windows strftime quirk: if %-I fails on Windows Python, replace with this:
    try:
        _ = (datetime.now()).strftime("%-I:%M%p")
    except ValueError:
        df["time_local"] = df["local_dt"].dt.strftime("%#I:%M%p")
    df["has_specific_time"] = 1  # HF rows have times; if you want to null times at midnight, adjust here.
    df["when_tz"] = args.tz
    df["when_iso"] = df["DateTime"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Title & event_id
    df["title"] = df["Event"].astype(str)
    df["currency"] = df["Currency"].astype(str)
    df["is_major"] = (df["impact_num"] >= 2).astype(int)
    df["impact_included"] = (df["impact_num"] > 0).astype(int)
    df["event_id"] = (
        "hf:" + df["date_local"].str.replace("-", "") + ":" +
        df["time_local"].str.lower().str.replace(" ", "") + ":" +
        df["currency"].str.upper() + ":" +
        df["title"].map(slugify)
    )

    # Build minimal schema and upsert
    cols_all = [
        "event_id","currency","impact","impact_num","title",
        "Actual","Forecast","Previous",
        "date_local","time_local","when_tz","when_iso",
        "has_specific_time","url","is_major","impact_included","source"
    ]
    df["url"] = None  # not provided by HF dataset
    df.rename(columns={"Actual":"actual","Forecast":"forecast","Previous":"previous"}, inplace=True)
    # Reorder and keep expected names
    df2 = df.rename(columns=str.lower)[[
        "event_id","currency","impact","impact_num","title",
        "actual","forecast","previous",
        "date_local","time_local","when_tz","when_iso",
        "has_specific_time","url","is_major","impact_included"
    ]].copy()
    df2["source"] = "ff_hf_dataset"

    # Upsert to SQLite with safe column intersection
    con = sqlite3.connect(args.db)
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            currency TEXT, impact TEXT, impact_num INTEGER, title TEXT,
            actual TEXT, forecast TEXT, previous TEXT,
            date_local TEXT, time_local TEXT, when_tz TEXT, when_iso TEXT,
            has_specific_time INTEGER, url TEXT, is_major INTEGER, impact_included INTEGER,
            source TEXT
        )""")
        # Intersect with existing columns
        existing = {row[1] for row in con.execute("PRAGMA table_info(events)").fetchall()}
        # Insert in batches
        batch = []
        inserted = 0
        def flush():
    nonlocal batch, inserted
    if not batch: return
    cols = [c for c in batch[0].keys() if c in existing]
    col_list = ",".join(cols)
    ph = ",".join(["?"]*len(cols))
    values = [tuple(_py(rec[c]) for c in cols) for rec in batch]
    con.executemany(
        f"INSERT OR REPLACE INTO events ({col_list}) VALUES ({ph})",
        values
    )
    con.commit()
    inserted += len(batch)
    batch = []

        for _, row in df2.iterrows():
            ev = EventRow(
                event_id = row["event_id"],
                currency = row["currency"],
                impact = row["impact"],
                impact_num = int(row["impact_num"]),
                title = row["title"],
                actual = (None if pd.isna(row["actual"]) else str(row["actual"])),
                forecast = (None if pd.isna(row["forecast"]) else str(row["forecast"])),
                previous = (None if pd.isna(row["previous"]) else str(row["previous"])),
                date_local = row["date_local"],
                time_local = row["time_local"],
                when_tz = row["when_tz"],
                when_iso = row["when_iso"],
                has_specific_time = int(row["has_specific_time"]),
                url = None,
                is_major = int(row["is_major"]),
                impact_included = int(row["impact_included"]),
                source = "ff_hf_dataset",
            )
            batch.append(asdict(ev))
            if len(batch) >= 1000:
                flush()
        flush()
        print(f"[upserted] {inserted} rows into {args.db} (source=ff_hf_dataset)")
    finally:
        con.close()

if __name__ == "__main__":
    sys.exit(main())
