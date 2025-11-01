# save as run_rulebook.py
from __future__ import annotations
import argparse, csv, os, pandas as pd
from pandas import to_datetime
import numpy as np

def load_rules(p):
    out=[]
    with open(p, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({k:v.strip() for k,v in r.items()})
    return out

def matches(row, rule):
    # title substring & pair & impact/z filters
    if row["pair"].upper()!=rule["pair"].upper(): return False
    if rule["title_pattern"].lower() not in str(row["title"]).lower(): return False
    if row["impact_num"] < int(rule["impact_min"]): return False
    z = row.get("surprise_z")
    if pd.notna(z) and abs(float(z)) < float(rule["zmin"]): return False
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs_csv", default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--events_csv", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--prices_dir", required=True)
    ap.add_argument("--file_pattern", default="{pair}_*_M15.csv")
    ap.add_argument("--ts_col", default="datetime")
    ap.add_argument("--prices_tz", default="UTC")
    ap.add_argument("--rules_csv", default="rules_calendar_to_trade.csv")
    ap.add_argument("--out_dir", default="outputs")
    args = ap.parse_args()

    pairs = pd.read_csv(args.pairs_csv)
    events = pd.read_csv(args.events_csv)
    # z scores
    mask = events["num_actual"].notna() & events["num_forecast"].notna()
    events["surprise"] = np.where(mask, events["num_actual"]-events["num_forecast"], np.nan)
    stats = events.groupby("title")["surprise"].agg(["mean","std"]).rename(columns={"mean":"mu","std":"sigma"})
    events = events.join(stats, on="title")
    events["surprise_z"] = (events["surprise"]-events["mu"])/events["sigma"]
    z_map = events.set_index("event_id")["surprise_z"]
    pairs["surprise_z"] = pairs["event_id"].map(z_map)

    rules = load_rules(args.rules_csv)

    # build a filter mask per rule
    picked=[]
    for _,row in pairs.iterrows():
        for r in rules:
            if matches(row, r):
                picked.append({**row.to_dict(), **r})
                break
    sel = pd.DataFrame(picked)
    if sel.empty:
        print("[warn] no rows matched your rules")
        return

    # reuse the robust loader from your scorer
    from price_join_and_score_v2 import load_prices, find_price_file
    os.makedirs(args.out_dir, exist_ok=True)

    # time to ts (prefer when_iso if present)
    if "when_iso" in sel.columns:
        sel["ts"] = to_datetime(sel["when_iso"], utc=True, errors="coerce")
    else:
        sel["ts"] = to_datetime(sel["date_local"]+" "+sel["time_local"], utc=True, errors="coerce")

    all_trades=[]
    for (pair, window_m), g in sel.groupby(["pair","window_m"]):
        price_path = find_price_file(args.prices_dir, pair, args.file_pattern, "")
        if not price_path or not os.path.exists(price_path):
            print(f"[skip] {pair}: no prices for pattern {args.file_pattern}")
            continue
        px = load_prices(price_path, ts_col_cli=args.ts_col, prices_tz=args.prices_tz)

        probe = g[["ts","event_id","pair","direction_sign","title","impact_num","hold_m","session_tz","session_start","session_end"]].dropna(subset=["ts"]).copy()
        probe = probe.sort_values("ts")
        # session filter (optional simple UTC window)
        if all(pd.notna(probe[c]).all() for c in ["session_start","session_end"]):
            hhmm = lambda t: f"{t.hour:02d}:{t.minute:02d}"
            probe = probe[(probe["ts"].dt.strftime("%H:%M")>=probe["session_start"]) &
                          (probe["ts"].dt.strftime("%H:%M")<=probe["session_end"])]

        entry = pd.merge_asof(probe.rename(columns={"ts":"ts0"}), px, left_on="ts0", right_on="ts", direction="forward")
        entry = entry.dropna(subset=["open"])
        if entry.empty: 
            continue

        m = int(window_m)
        # close at t+m
        fut = pd.merge_asof(
            entry[["ts0"]].assign(ts_h=entry["ts0"]+pd.to_timedelta(m, unit="m")).rename(columns={"ts0":"ts"}),
            px[["ts","close"]], on="ts", direction="backward"
        )
        entry["ret_m"] = (fut["close"].values/entry["open"].values)-1.0
        entry["hit"] = ((np.sign(entry["ret_m"].values)*entry["direction_sign"].values)>0).astype(int)
        entry["window_m"]=m
        all_trades.append(entry)

    if not all_trades:
        print("[warn] no trades generated")
        return

    out = pd.concat(all_trades, ignore_index=True)
    out.to_csv(os.path.join(args.out_dir,"rulebook_trades.csv"), index=False)
    summ = (out.groupby(["pair","title","window_m"])
              .agg(count=("hit","count"), hit_rate=("hit","mean"), avg_ret=("ret_m","mean")))
    summ.to_csv(os.path.join(args.out_dir,"rulebook_metrics.csv"))
    print("[wrote] outputs/rulebook_trades.csv, outputs/rulebook_metrics.csv")

if __name__ == "__main__":
    import sys; sys.exit(main())
