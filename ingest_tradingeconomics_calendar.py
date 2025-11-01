#!/usr/bin/env python3
# See chat for docstring. TradingEconomics adapter.
import argparse, sqlite3, json, re
from urllib.request import urlopen, Request
import pandas as pd

def fetch(url, ua="Mozilla/5.0"):
    with urlopen(Request(url, headers={"User-Agent": ua}), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_number(s):
    if s is None: return None, None
    t = str(s).strip()
    if not t or t.lower() in {"n/a","na","--"}: return None, None
    kind = "pct" if "%" in t else "level"
    t = t.replace('%',' ').replace('\xa0',' ')
    import re
    t = re.sub(r'[^\w\.\-\+\sKMBT]', '', t).replace(',','').replace(' ','')
    m = re.match(r'^([+-]?\d*\.?\d+)([KMBT])?$', t, flags=re.I)
    if not m:
        m2 = re.search(r'([+-]?\d*\.?\d+)', t)
        if not m2: return None, kind
        return float(m2.group(1)), kind
    num = float(m.group(1)); mult = {'K':1e3,'M':1e6,'B':1e9,'T':1e12}.get((m.group(2) or '').upper(),1.0)
    return num*mult, kind

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--db", default="outputs/ff_calendar.sqlite")
    ap.add_argument("--countries", default="")
    args = ap.parse_args()

    base = f"https://api.tradingeconomics.com/calendar?d1={args.start}&d2={args.end}&format=json"
    if args.countries: base += f"&c={args.countries}"
    base += f"&c=all&client={args.key}"
    data = fetch(base)
    if not isinstance(data, list): print("[warn] unexpected response"); return

    rows = []
    for it in data:
        ccy = (it.get("Currency") or it.get("Country") or "").upper()
        impact = str(it.get("Importance") or it.get("Impact") or "").lower()
        impact_num = {"low":1,"medium":2,"high":3}.get(impact, 0)
        title = it.get("Event") or it.get("Category") or ""
        when_iso = it.get("Date") or it.get("DateUtc") or ""
        actual = it.get("Actual"); forecast = it.get("Forecast"); previous = it.get("Previous")
        av, ak = parse_number(actual); fv, fk = parse_number(forecast); pv, pk = parse_number(previous)
        same = (ak == fk) and (ak is not None)
        surprise = (av - fv) if (same and av is not None and fv is not None) else None
        rows.append({
            "event_id": f"te:{ccy}:{title}:{when_iso}",
            "currency": ccy, "impact": impact, "impact_num": impact_num, "title": title,
            "actual": actual or "", "forecast": forecast or "", "previous": previous or "",
            "actual_val": av, "forecast_val": fv, "previous_val": pv,
            "surprise_kind": ak if same else None, "surprise_raw": surprise,
            "when_iso": when_iso, "has_specific_time": 1 if when_iso else 0,
            "source": "tradingeconomics"
        })
    import pandas as pd
    df = pd.DataFrame(rows)
    df["when_dt_utc"] = pd.to_datetime(df["when_iso"], utc=True, errors="coerce")
    for freq, col in [("1min","ts_1m"), ("5min","ts_5m"), ("15min","ts_15m"), ("60min","ts_1h")]:
        df[col] = df["when_dt_utc"].dt.floor(freq)
    con = sqlite3.connect(args.db)
    con.execute("""CREATE TABLE IF NOT EXISTS events_te (
        event_id TEXT PRIMARY KEY,
        currency TEXT, impact TEXT, impact_num INTEGER, title TEXT,
        actual TEXT, forecast TEXT, previous TEXT,
        actual_val REAL, forecast_val REAL, previous_val REAL,
        surprise_kind TEXT, surprise_raw REAL,
        when_iso TEXT, has_specific_time INTEGER,
        when_dt_utc TEXT, ts_1m TEXT, ts_5m TEXT, ts_15m TEXT, ts_1h TEXT,
        source TEXT
    )""")
    cur = con.cursor()
    for rec in df.to_dict(orient="records"):
        cols = ",".join(rec.keys()); ph = ",".join(["?"]*len(rec))
        cur.execute("INSERT OR REPLACE INTO events_te ("+cols+") VALUES ("+ph+")", tuple(rec.values()))
    con.commit(); con.close()
    print(f"[upserted] {len(df)} rows into {args.db}::events_te")

if __name__ == "__main__":
    main()
