import argparse, sqlite3, pandas as pd
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="Export ML-friendly slice from ff_calendar.sqlite")
    ap.add_argument("--db", default="outputs/ff_calendar.sqlite")
    ap.add_argument("--out", default="outputs/events_ml_highmed_2012_2024.csv")
    ap.add_argument("--impacts", default="high,medium", help="Comma-separated: high,medium,low")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        raise SystemExit(f"DB not found at {db}. Run the pipeline first.")

    impacts = [x.strip().lower() for x in args.impacts.split(",") if x.strip()]
    con = sqlite3.connect(db.as_posix())
    query = """
        SELECT when_iso AS timestamp_utc, currency, impact, title, actual, forecast, previous, url
        FROM events
        WHERE has_specific_time = 1 AND is_major = 1 AND impact IN ({placeholders})
        ORDER BY when_iso
    """.format(placeholders=",".join(["?"]*len(impacts)))
    df = pd.read_sql_query(query, con, params=impacts)
    con.close()

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[wrote] {out} ({len(df)} rows)")

if __name__ == "__main__":
    main()
