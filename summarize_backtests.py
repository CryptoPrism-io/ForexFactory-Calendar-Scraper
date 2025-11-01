import argparse, glob, os, pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--metrics_glob", default=r"outputs\price_join_metrics_*.csv")
ap.add_argument("--out_dir", default="outputs")
args = ap.parse_args()

rows = []
for path in glob.glob(args.metrics_glob):
    try:
        m = pd.read_csv(path)
    except Exception:
        continue
    tag = os.path.splitext(os.path.basename(path))[0].replace("price_join_metrics_","")
    m["tag"] = tag
    rows.append(m)

if not rows:
    print("[warn] no metrics files found")
    raise SystemExit(0)

allm = pd.concat(rows, ignore_index=True)
os.makedirs(args.out_dir, exist_ok=True)
allm.to_csv(os.path.join(args.out_dir, "all_metrics_summary.csv"), index=False)

# Best titles for 15m per tag (hit-rate then avg return)
best = (allm[allm["window_m"]==15]
        .sort_values(["tag","hit_15m_mean","ret_15m_mean"], ascending=[True,False,False]))
best.head(200).to_csv(os.path.join(args.out_dir, "top20_15m_by_tag.csv"), index=False)

print("[wrote] all_metrics_summary.csv, top20_15m_by_tag.csv")
