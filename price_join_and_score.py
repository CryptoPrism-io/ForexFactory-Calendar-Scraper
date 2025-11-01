#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, glob
import pandas as pd
import numpy as np
from pandas import to_datetime

def load_prices(csv_path: str, ts_col_cli: str = "", prices_tz: str = "UTC") -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # Case-insensitive OHLC detection
    lower = {c.lower(): c for c in df.columns}
    need = ["open","high","low","close"]
    for n in need:
        if n not in lower:
            raise SystemExit(f"Missing '{n}' (case-insensitive) in {csv_path}")
    ohlc_cols = [lower["open"], lower["high"], lower["low"], lower["close"]]

    # Choose timestamp column
    candidates = [ts_col_cli] if ts_col_cli else []
    candidates += ["timestamp","datetime","date","time","Timestamp","Date","Time"]
    ts_col = next((c for c in candidates if c and c in df.columns), None)

    # If no explicit ts col, try index as datetime
    if ts_col is None:
        try:
            df2 = pd.read_csv(csv_path, index_col=0)
            if isinstance(df2.index, pd.DatetimeIndex):
                df = df2.reset_index().rename(columns={df2.index.name or "index":"ts"})
                ts_col = "ts"
        except Exception:
            pass

    if ts_col is None:
        raise SystemExit(f"Could not find a timestamp column in {csv_path}. Try --ts_col datetime (or rename your column).")

    # Parse timestamp
    ts = pd.to_datetime(df[ts_col], utc=False, errors="coerce")
    if ts.isna().all():
        ts = pd.to_datetime(df[ts_col], unit="s", utc=False, errors="coerce")
        if ts.isna().all():
            ts = pd.to_datetime(df[ts_col], unit="ms", utc=False, errors="coerce")

    # Drop rows that failed parsing
    if ts.isna().any():
        mask = ~ts.isna()
        df = df.loc[mask].copy()
        ts = ts.loc[mask]

    # Localize/convert to UTC
    try: tzinfo = ts.dt.tz
    except Exception: tzinfo = None
    if tzinfo is None:
        if prices_tz and prices_tz.upper() != "UTC":
            ts = ts.dt.tz_localize(prices_tz, nonexistent="shift_forward", ambiguous="NaT", errors="coerce").dt.tz_convert("UTC")
        else:
            ts = ts.dt.tz_localize("UTC")
    else:
        ts = ts.dt.tz_convert("UTC")

    df = df.assign(ts=ts).sort_values("ts").reset_index(drop=True)
    return df[["ts", *ohlc_cols]]

def forward_returns(px: pd.DataFrame, entry_ts: pd.Series, minutes: int) -> pd.Series:
    horizon = px[["ts","close"]].rename(columns={"ts":"ts_h", "close":f"close_{minutes}m"})
    target_ts = entry_ts + pd.to_timedelta(minutes, unit="m")
    probe = pd.DataFrame({"ts": entry_ts.values, "ts_h": target_ts.values}).sort_values("ts_h")
    out = pd.merge_asof(probe, horizon, on="ts_h", direction="backward")
    return pd.Series(out[f"close_{minutes}m"].values, index=entry_ts.index)

def find_price_file(prices_dir: str, pair: str, pattern: str, tf: str) -> str | None:
    pairU, pairL = pair.upper(), pair.lower()
    pat = pattern.replace("{PAIR}", pairU).replace("{pair}", pairL).replace("{TF}", tf or "")
    matches = glob.glob(os.path.join(prices_dir, pat))
    if matches: return matches[0]
    # Try without timeframe if none found
    if "{TF}" in pattern and tf:
        pat2 = pattern.replace("{TF}", "*")
        matches = glob.glob(os.path.join(prices_dir, pat2))
        # keep only ones with the same pair token in filename
        matches = [m for m in matches if pairL in os.path.basename(m).lower()]
        if matches: return matches[0]
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs_csv", default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--events_csv", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--prices_dir", required=True)
    ap.add_argument("--windows", default="5,15,60")
    ap.add_argument("--impact_min", type=int, default=2)
    ap.add_argument("--zmin", type=float, default=0.0)
    ap.add_argument("--ts_col", default="", help="Timestamp column name in price CSVs (e.g., datetime).")
    ap.add_argument("--prices_tz", default="UTC", help="Timezone of price timestamps if naive (e.g., America/New_York).")
    ap.add_argument("--file_pattern", default="{pair}_*.csv", help="Glob pattern relative to prices_dir. Use {PAIR}/{pair}/{TF}.")
    ap.add_argument("--tf", default="", help="Timeframe token to plug into {TF} (e.g., M5, M15).")
    ap.add_argument("--out_dir", default="outputs")
    ap.add_argument("--tag", default="", help="Optional tag suffix for output filenames (e.g., m5).")
    args = ap.parse_args()

    pairs_df = pd.read_csv(args.pairs_csv)
    events_df = pd.read_csv(args.events_csv)

    # z-score per title
    mask = events_df["num_actual"].notna() & events_df["num_forecast"].notna()
    events_df["surprise"] = np.where(mask, events_df["num_actual"] - events_df["num_forecast"], np.nan)
    stats = events_df.groupby("title")["surprise"].agg(["mean","std"]).rename(columns={"mean":"mu","std":"sigma"})
    events_df = events_df.join(stats, on="title")
    events_df["surprise_z"] = (events_df["surprise"] - events_df["mu"]) / events_df["sigma"]
    z_lookup = events_df.set_index("event_id")["surprise_z"]

    pairs_df["surprise_z"] = pairs_df["event_id"].map(z_lookup)
    if args.zmin > 0:
        pairs_df = pairs_df[(pairs_df["surprise_z"].abs() >= args.zmin) | (pairs_df["surprise_z"].isna())]

    if args.impact_min > 0:
        pairs_df = pairs_df[pairs_df["impact_num"] >= args.impact_min]

    # Use when_iso if present; else compose from local date/time
    if "when_iso" in pairs_df.columns:
        w = to_datetime(pairs_df["when_iso"], utc=True, errors="coerce")
        pairs_df["when_ts"] = w
    else:
        pairs_df["when_ts"] = to_datetime(pairs_df["date_local"] + " " + pairs_df["time_local"], utc=True, errors="coerce")

    os.makedirs(args.out_dir, exist_ok=True)
    windows = [int(x) for x in args.windows.split(",") if x.strip()]

    tag = f"_{args.tag}" if args.tag else ""
    trades_written = 0
    summaries = []

    for pair, g in pairs_df.groupby("pair"):
        price_path = find_price_file(args.prices_dir, pair, args.file_pattern, args.tf)
        if not price_path or not os.path.exists(price_path):
            print(f"[skip] {pair}: no price file match with pattern '{args.file_pattern}' in {args.prices_dir}")
            continue

        px = load_prices(price_path, ts_col_cli=args.ts_col, prices_tz=args.prices_tz)

        probe = g[["event_id","pair","direction_sign","title","impact_num","when_ts"]].dropna(subset=["when_ts"]).copy()
        probe = probe.sort_values("when_ts").rename(columns={"when_ts":"ts"})

        # Align entry bar (first at/after event)
        entry = pd.merge_asof(probe, px, on="ts", direction="forward")
        entry = entry.dropna(subset=["open"])
        if entry.empty:
            print(f"[warn] {pair}: no aligned entries (timestamps beyond price range?)")
            continue

        entry["ret_0m"] = 0.0
        for m in windows:
            fwd = pd.merge_asof(
                entry[["ts"]].rename(columns={"ts":"ts_h"}).assign(ts=entry["ts"] + pd.to_timedelta(m, unit="m")).sort_values("ts"),
                px[["ts","close"]],
                on="ts", direction="backward"
            )
            entry[f"ret_{m}m"] = (fwd["close"].values / entry["open"].values) - 1.0
            entry[f"hit_{m}m"] = ((np.sign(entry[f"ret_{m}m"].values) * entry["direction_sign"].values) > 0).astype(int)

        out_trades = os.path.join(args.out_dir, f"trades_{pair}{tag}.csv")
        entry.to_csv(out_trades, index=False)
        trades_written += 1

        for m in windows:
            cols = [f"ret_{m}m", f"hit_{m}m"]
            summ = (entry.groupby(["pair","title","impact_num"])[cols]
                    .agg(["count","mean"]))
            summ.columns = [f"{c}_{stat}" for c,stat in summ.columns]
            summ["window_m"] = m
            summaries.append(summ.reset_index())

        print(f"[ok] {pair}: {len(entry)} trades → {out_trades}")

    if summaries:
        out = pd.concat(summaries, ignore_index=True)
        out_csv = os.path.join(args.out_dir, f"price_join_metrics{tag}.csv")
        out.to_csv(out_csv, index=False)
        print(f"[wrote] {out_csv}")
    else:
        print("[warn] no summaries produced; check patterns/paths/ts parsing")

if __name__ == "__main__":
    raise SystemExit(main())
