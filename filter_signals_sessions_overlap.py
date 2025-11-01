#!/usr/bin/env python3
from __future__ import annotations
import argparse, os
import pandas as pd
import numpy as np
from pandas import to_datetime

SESSIONS_UTC = {
    # name: list of (start_HH:MM, end_HH:MM). Cross-midnight handled automatically.
    "Sydney": [("21:00","06:00")],
    "Tokyo":  [("00:00","09:00")],
    "London": [("07:00","16:00")],
    "NewYork":[("12:00","21:00")],
    "NYSE":   [("13:30","20:00")],
}

def _hhmm_to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h)*60 + int(m)

def _in_any_session(ts_utc: pd.Series, windows: list[tuple[str,str]]) -> pd.Series:
    # ts_utc is tz-aware UTC timestamps
    mins = ts_utc.dt.hour*60 + ts_utc.dt.minute
    ok = pd.Series(False, index=ts_utc.index)
    for start, end in windows:
        s = _hhmm_to_minutes(start); e = _hhmm_to_minutes(end)
        if s <= e:
            ok = ok | ((mins >= s) & (mins < e))
        else:
            # cross-midnight, e.g., 21:00–06:00
            ok = ok | (mins >= s) | (mins < e)
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs_csv", default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--events_csv", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--out_pairs",  default=r"outputs\calendar_surprises_pair_signals_filtered.csv")
    ap.add_argument("--impact_min", type=int, default=0, help="Keep events with impact_num >= this")
    ap.add_argument("--zmin", type=float, default=0.0, help="Keep events with |z| >= this (computed per title)")
    ap.add_argument("--sessions", default="", help="Comma list of session names to include (e.g., London,NewYork,NYSE). UTC.")
    ap.add_argument("--extra_windows", default="", help="Extra UTC windows; semicolon-separated HH:MM-HH:MM (e.g., 07:00-20:00;12:00-21:00)")
    ap.add_argument("--overlap_min", type=int, default=1, help="Overlap resolution in minutes (1 = per-minute buckets)")
    args = ap.parse_args()

    pairs = pd.read_csv(args.pairs_csv)
    events = pd.read_csv(args.events_csv)

    # Build z-scores per title from events file
    mask = events["num_actual"].notna() & events["num_forecast"].notna()
    events["surprise"] = np.where(mask, events["num_actual"] - events["num_forecast"], np.nan)
    stats = events.groupby("title")["surprise"].agg(["mean","std"]).rename(columns={"mean":"mu","std":"sigma"})
    events = events.join(stats, on="title")
    events["surprise_z"] = (events["surprise"] - events["mu"]) / events["sigma"]

    z_map = events.set_index("event_id")["surprise_z"]
    pairs["surprise_z"] = pairs["event_id"].map(z_map)

    # Parse event time (prefer when_iso)
    if "when_iso" in pairs.columns:
        when_ts = to_datetime(pairs["when_iso"], utc=True, errors="coerce")
    else:
        # fallback to local date/time as UTC (if needed you can enhance)
        when_ts = to_datetime(pairs["date_local"] + " " + pairs["time_local"], utc=True, errors="coerce")
    pairs["when_ts"] = when_ts
    start_rows = len(pairs)

    # Impact filter
    if args.impact_min > 0:
        pairs = pairs[pairs["impact_num"] >= args.impact_min]

    # z-score filter
    if args.zmin > 0:
        pairs = pairs[pairs["surprise_z"].abs() >= args.zmin]

    # Sessions filter (UTC)
    windows: list[tuple[str,str]] = []
    if args.sessions:
        names = [s.strip() for s in args.sessions.split(",") if s.strip()]
        for n in names:
            if n not in SESSIONS_UTC:
                raise SystemExit(f"Unknown session '{n}'. Known: {', '.join(SESSIONS_UTC.keys())}")
            windows += SESSIONS_UTC[n]
    if args.extra_windows:
        for chunk in args.extra_windows.split(";"):
            chunk = chunk.strip()
            if not chunk: continue
            if "-" not in chunk: raise SystemExit(f"Bad extra window '{chunk}', expected HH:MM-HH:MM")
            a,b = chunk.split("-",1)
            windows.append((a.strip(), b.strip()))

    if windows:
        ok = _in_any_session(pairs["when_ts"], windows)
        pairs = pairs[ok]

    # Overlap: one event per currency per <bucket> minutes
    if args.overlap_min and args.overlap_min > 0:
        bucket = (pairs["when_ts"].dt.floor(f"{args.overlap_min}T"))
        pairs = pairs.assign(when_bucket=bucket)
        # rank: higher impact first, then larger |z|
        pairs["abs_z"] = pairs["surprise_z"].abs()
        pairs = pairs.sort_values(["currency","when_bucket","impact_num","abs_z"], ascending=[True, True, False, False])
        pairs = pairs.drop_duplicates(subset=["currency","when_bucket"], keep="first")
        pairs = pairs.drop(columns=["abs_z","when_bucket"])

    os.makedirs(os.path.dirname(args.out_pairs) or ".", exist_ok=True)
    pairs.to_csv(args.out_pairs, index=False, encoding="utf-8")

    print(f"[filtered] {start_rows} -> {len(pairs)} rows")
    print(f"[wrote] {args.out_pairs}")

if __name__ == "__main__":
    raise SystemExit(main())
