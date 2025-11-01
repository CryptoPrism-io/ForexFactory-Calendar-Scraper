import argparse, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--in_csv", required=True)
ap.add_argument("--out_dir", default="outputs")
ap.add_argument("--train_end", default="2018-12-31")
ap.add_argument("--val_end",   default="2021-12-31")
args = ap.parse_args()

df = pd.read_csv(args.in_csv, parse_dates=["when_ts"])
tr = df[df["when_ts"] <=  pd.to_datetime(args.train_end)]
va = df[(df["when_ts"] >  pd.to_datetime(args.train_end)) & (df["when_ts"] <= pd.to_datetime(args.val_end))]
te = df[df["when_ts"] >  pd.to_datetime(args.val_end)]

tr.to_csv(f"{args.out_dir}/pair_signals_LN_train.csv", index=False)
va.to_csv(f"{args.out_dir}/pair_signals_LN_val.csv",   index=False)
te.to_csv(f"{args.out_dir}/pair_signals_LN_test.csv",  index=False)

print(f"[split] train={len(tr)}  val={len(va)}  test={len(te)}")
