#!/usr/bin/env python3
import argparse, pandas as pd

def pct(n, d): return 0 if d==0 else 100.0*n/d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events_csv", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--pairs_csv",  default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--out_dir",    default=r"outputs")
    args = ap.parse_args()

    e = pd.read_csv(args.events_csv)
    p = pd.read_csv(args.pairs_csv)

    print("[events]", len(e), "rows")
    print("[pairs ]", len(p), "rows")

    # coverage
    e["year"] = e["date_local"].str.slice(0,4)
    g_year = e.groupby("year").size().rename("rows")
    g_ccy  = e.groupby("currency").size().rename("rows").sort_values(ascending=False)
    g_imp  = e.groupby("impact_num").size().rename("rows").sort_values(ascending=False)

    # quality
    both = e["num_actual"].notna() & e["num_forecast"].notna()
    print("[quality] both actual&forecast:", both.sum(), f"({pct(both.sum(), len(e)):.1f}%)")

    # surprise stats by title
    e2 = e[both].copy()
    s_title = (e2.groupby("title")["surprise"]
                 .agg(["count","mean","median","std"])
                 .sort_values("count", ascending=False))
    # direction distribution
    d_cc   = e["cc_strength_sign"].value_counts(dropna=False).rename("currency_dir_dist")
    d_pair = p["direction_sign"].value_counts(dropna=False).rename("pair_dir_dist")

    # write reports
    g_year.to_csv(f"{args.out_dir}/audit_by_year.csv")
    g_ccy.to_csv(f"{args.out_dir}/audit_by_currency.csv")
    g_imp.to_csv(f"{args.out_dir}/audit_by_impact.csv")
    s_title.to_csv(f"{args.out_dir}/audit_surprise_by_title.csv")
    d_cc.to_csv(f"{args.out_dir}/audit_cc_direction_dist.csv")
    d_pair.to_csv(f"{args.out_dir}/audit_pair_direction_dist.csv")

    # top titles quick peek
    print("\n[top titles by count]\n", s_title.head(15))

if __name__ == "__main__":
    raise SystemExit(main())
