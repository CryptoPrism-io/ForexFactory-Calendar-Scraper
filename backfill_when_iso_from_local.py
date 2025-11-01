#!/usr/bin/env python3
# See previous cell for full description.
import argparse, sqlite3, re
from datetime import datetime
from zoneinfo import ZoneInfo

TIME_RE = re.compile(r'^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$', re.I)
CCY_TZ = {
    "USD": "America/New_York",
    "CAD": "America/Toronto",
    "EUR": "Europe/Berlin",
    "GBP": "Europe/London",
    "CHF": "Europe/Zurich",
    "JPY": "Asia/Tokyo",
    "AUD": "Australia/Sydney",
    "NZD": "Pacific/Auckland",
}

def parse_local_time(t: str):
    m = TIME_RE.match((t or ""))
    if not m: return None
    hh = int(m.group(1)); mm = int(m.group(2) or 0); ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hh != 12: hh += 12
    if ampm == "am" and hh == 12: hh = 0
    if 0 <= hh <= 23 and 0 <= mm <= 59: return hh, mm
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="outputs/ff_calendar.sqlite")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    con = sqlite3.connect(args.db); cur = con.cursor()
    q = """
    SELECT rowid, currency, date_local, time_local, COALESCE(NULLIF(when_tz,''), '') as tz
    FROM events
    WHERE (when_iso IS NULL OR when_iso='')
      AND date_local IS NOT NULL AND date_local!=''
      AND time_local IS NOT NULL AND time_local!=''
    """
    if args.limit > 0: q += f" LIMIT {int(args.limit)}"
    rows = cur.execute(q).fetchall()
    print(f"[scan] candidates: {len(rows)}")

    updated = 0
    for rowid, ccy, d, t, tz in rows:
        hm = parse_local_time(t)
        if not hm: continue
        try:
            hh, mm = hm
            tzname = tz or CCY_TZ.get((ccy or '').upper(), 'UTC')
            z = ZoneInfo(tzname)
            y, m, day = map(int, d.split('-'))
            dt_local = datetime(y, m, day, hh, mm, 0, tzinfo=z)
            dt_utc = dt_local.astimezone(ZoneInfo('UTC'))
            when_iso = dt_utc.isoformat().replace('+00:00', 'Z')
        except Exception:
            continue
        cur.execute("UPDATE events SET when_iso=?, has_specific_time=1 WHERE rowid=?", (when_iso, rowid))
        updated += 1
        if updated % 1000 == 0:
            con.commit(); print(f"[update] {updated}...")
    con.commit(); con.close()
    print(f"[done] updated {updated} rows")

if __name__ == "__main__": main()
