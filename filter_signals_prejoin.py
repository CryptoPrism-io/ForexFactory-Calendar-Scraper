#!/usr/bin/env python3
from __future__ import annotations
import argparse, pandas as pd, numpy as np
from pandas import to_datetime

SESSIONS_UTC = {
    "Sydney": ("21:00", "06:00"),
    "Tokyo":  ("00:00", "09:00"),
    "London": ("07:00", "16:00"),
    "NewYork":("12:00", "21:00"),
    "NYSE":   ("13:30", "20:00"),
}

def in_any_session(ts_utc: pd.Series, sessions: list[tuple[str,str]]) -> pd.Series:
    """Return mask whether ts (UTC) falls in ANY [start,end) window; supports wrap at midnight."""
    hhmm = ts_utc.dt.strftime("%H:%M")
    mask = pd.Series(False, index=ts_utc.index)
    for start, end in sessions:
        if start <= end:
            mask |= (hhmm >= start) & (hhmm < end)
        else:
            mask |= (hhmm >= start) | (hhmm < end)
    return mask

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs_csv",  default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--events_csv", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--out_csv",    default=r"outputs\calendar_pair_signals_filtered.csv")
    ap.add_argument("--sessions",   default="London,NewYork",
                    help="Comma list: Sydney,Tokyo,London,NewYork,NYSE. Empty=all.")
    ap.add_argument("--custom_utc", default="", help='Optional extra UTC window "HH:MM-HH:MM".')
    ap.add_argument("--impact_min", type=int, default=2)
    ap.add_argument("--zmin",       type=float, default=1.0)
    ap.add_argument("--dedupe_policy", choices=["impact_then_absz","absz_then_impact"], default="impact_then_absz")
    ap.add_argument("--min_gap_min", type=int, default=0, help="Minimum minutes between kept events per currency.")
    args = ap.parse_args()

    pairs = pd.read_csv(args.pairs_csv)
    events = pd.read_csv(args.events_csv)

    # Prefer when_iso; fallback to local date/time
    if "when_iso" in pairs.columns:
        pairs["when_ts"] = to_datetime(pairs["when_iso"], utc=True, errors="coerce")
    else:
        pairs["when_ts"] = to_datetime(pairs["date_local"] + " " + pairs["time_local"], utc=True, errors="coerce")

    # Compute per-title z for ranking magnitude
    mask = events["num_actual"].notna() & events["num_forecast"].notna()
    events["surprise"] = np.where(mask, events["num_actual"] - events["num_forecast"], np.nan)
    stats = events.groupby("title")["surprise"].agg(["mean","std"]).rename(columns={"mean":"mu","std":"sigma"})
    events = events.join(stats, on="title")
    events["surprise_z"] = (events["surprise"] - events["mu"]) / events["sigma"]
    z_map = events.set_index("event_id")["surprise_z"]
    pairs["surprise_z"] = pairs["event_id"].map(z_map)

    # Basic hygiene
    pairs = pairs.dropna(subset=["when_ts","pair"]).copy()

    # Impact/z filters
    if args.impact_min > 0:
        pairs = pairs[pairs["impact_num"] >= args.impact_min]
    if args.zmin > 0:
        pairs = pairs[pairs["surprise_z"].abs() >= args.zmin]

    # Session filter
    sess_list: list[tuple[str,str]] = []
    if args.sessions.strip():
        for name in [s.strip() for s in args.sessions.split(",") if s.strip()]:
            if name not in SESSIONS_UTC:
                raise SystemExit(f"Unknown session name: {name}")
            sess_list.append(SESSIONS_UTC[name])
    else:
        sess_list = list(SESSIONS_UTC.values())

    if args.custom_utc:
        try:
            a, b = args.custom_utc.split("-", 1)
            sess_list.append((a.strip(), b.strip()))
        except Exception:
            raise SystemExit('custom_utc must be "HH:MM-HH:MM"')

    if sess_list:
        in_sess = in_any_session(pairs["when_ts"], sess_list)
        pairs = pairs[in_sess].copy()

    # Dedupe per (currency, minute)
    if pairs.empty:
        print("[warn] no rows after filters; nothing to write")
        pairs.to_csv(args.out_csv, index=False)
        return

    ev = pairs[["event_id","currency","impact_num","surprise_z","when_ts"]].drop_duplicates("event_id").copy()
    ev["minute"] = ev["when_ts"].dt.floor("T")

    if args.dedupe_policy == "impact_then_absz":
        ev = ev.sort_values(["currency","minute","impact_num","surprise_z"], ascending=[True,True,False,False])
    else:
        ev["absz"] = ev["surprise_z"].abs()
        ev = ev.sort_values(["currency","minute","absz","impact_num"], ascending=[True,True,False,False])

    ev_top = ev.drop_duplicates(["currency","minute"], keep="first")

    # Optional min gap
    if args.min_gap_min > 0:
        keep_ids = []
        for ccy, g in ev_top.sort_values("minute").groupby("currency"):
            last = pd.Timestamp.min.tz_localize("UTC")
            gap = pd.Timedelta(minutes=args.min_gap_min)
            for _, r in g.iterrows():
                if r["minute"] >= last + gap:
                    keep_ids.append(r["event_id"])
                    last = r["minute"]
        ev_top = ev_top[ev_top["event_id"].isin(keep_ids)]

    kept = set(ev_top["event_id"])
    filtered = pairs[pairs["event_id"].isin(kept)].copy()
    filtered.to_csv(args.out_csv, index=False, encoding="utf-8")
    print(f"[wrote] {args.out_csv}  (kept {len(ev_top)} unique currency-minute events, {len(filtered)} pair-rows)")

if __name__ == "__main__":
    raise SystemExit(main())