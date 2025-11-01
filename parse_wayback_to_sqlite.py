#!/usr/bin/env python3
# parse_wayback_to_sqlite.py
# Parse archived ForexFactory calendar HTML saved by backfill_from_wayback_ff.py
# and insert events into your existing SQLite DB (table: events).
# Safe column intersection so it won't break if your `events` schema has extra cols.
#
# Usage (cmd):
#   .\.venv\Scripts\python.exe parse_wayback_to_sqlite.py --in_dir raw_wayback --db outputs\ff_calendar.sqlite --tz America/New_York
#
# Dependencies:
#   pip install beautifulsoup4 python-dateutil

from __future__ import annotations

import argparse, os, re, sqlite3, sys
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import List, Optional

from bs4 import BeautifulSoup
from dateutil import tz

WEEKDAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([ap]m)\s*$", re.I)

def parse_time_local_to_utc(date_local: date, time_local: str, tz_name: str) -> Optional[str]:
    m = TIME_RE.match(time_local or "")
    if not m:
        return None
    hh = int(m.group(1)) % 12
    mm = int(m.group(2))
    if m.group(3).lower() == "pm":
        hh += 12
    try:
        local_tz = tz.gettz(tz_name)
        dt_local = datetime(date_local.year, date_local.month, date_local.day, hh, mm, tzinfo=local_tz)
        dt_utc = dt_local.astimezone(tz.UTC)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except Exception:
        return None

@dataclass
class EventRow:
    event_id: str
    currency: str
    impact: str
    impact_num: int
    title: str
    actual: str
    forecast: str
    previous: str
    date_local: str
    time_local: str
    when_tz: str
    when_iso: Optional[str]
    has_specific_time: int
    url: Optional[str]
    is_major: int
    impact_included: int
    source: str = "ff_wayback"

def clean_txt(s: Optional[str]) -> str:
    if s is None: return ""
    return re.sub(r"\s+", " ", s).strip()

def impact_from_cell(td) -> (str, int):
    cls = " ".join(td.get("class") or [])
    for key, num in [("high",3), ("medium",2), ("low",1)]:
        if key in cls.lower():
            return key, num
    img = td.find("img")
    if img is not None:
        alt = (img.get("alt") or img.get("title") or "").lower()
        if "high" in alt: return "high", 3
        if "medium" in alt: return "medium", 2
        if "low" in alt: return "low", 1
    txt = clean_txt(td.get_text())
    for key, num in [("high",3), ("medium",2), ("low",1)]:
        if key in txt.lower():
            return key, num
    return "unknown", 0

def detect_day_header(tr) -> Optional[str]:
    txt = clean_txt(tr.get_text(" "))
    if not txt:
        return None
    for wd in WEEKDAYS:
        if wd.lower() in txt.lower():
            return txt
    if re.search(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", txt, re.I):
        return txt
    return None

def parse_date_from_header(header_txt: str, week_monday: date) -> Optional[date]:
    lower = header_txt.lower()
    idx = None
    for i, wd in enumerate(WEEKDAYS):
        if wd.lower() in lower:
            idx = i
            break
    if idx is None:
        m = re.search(r"\b(mon|tue|wed|thu|fri|sat|sun)\b", lower)
        if m:
            idx = ["mon","tue","wed","thu","fri","sat","sun"].index(m.group(1))
    if idx is None:
        return None
    d = week_monday + timedelta(days=idx)
    return d

def extract_rows_from_html(html: str, week_monday: date, tz_name: str) -> List[EventRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[EventRow] = []
    current_day: Optional[date] = None
    table = soup.find("table")
    trs = table.find_all("tr") if table else soup.find_all("tr")

    for tr in trs:
        hdr = detect_day_header(tr)
        if hdr:
            d = parse_date_from_header(hdr, week_monday)
            if d: current_day = d
            continue

        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        def find_cell(name_parts):
            for td in tds:
                cls = " ".join(td.get("class") or [])
                if any(part in cls for part in name_parts):
                    return td
            return None

        td_time = find_cell(["calendar__time", "time"])
        td_ccy = find_cell(["calendar__currency", "currency"])
        td_impact = find_cell(["calendar__impact", "impact"])
        td_title = find_cell(["calendar__event", "event", "calendar__event-title"])
        td_actual = find_cell(["actual", "calendar__actual"])
        td_forecast = find_cell(["forecast", "calendar__forecast"])
        td_previous = find_cell(["previous", "calendar__previous"])

        if td_title is None or td_ccy is None:
            continue

        time_local = clean_txt(td_time.get_text()) if td_time else ""
        currency = clean_txt(td_ccy.get_text())
        a = td_title.find("a")
        title = clean_txt(a.get_text() if a else td_title.get_text())
        url = a.get("href") if a and a.has_attr("href") else None

        impact, impact_num = ("unknown", 0)
        if td_impact:
            impact, impact_num = impact_from_cell(td_impact)

        actual = clean_txt(td_actual.get_text()) if td_actual else ""
        forecast = clean_txt(td_forecast.get_text()) if td_forecast else ""
        previous = clean_txt(td_previous.get_text()) if td_previous else ""

        day_for_row = current_day or week_monday
        has_specific = 1 if TIME_RE.match(time_local or "") else 0
        when_iso = parse_time_local_to_utc(day_for_row, time_local, tz_name) if has_specific else None

        base_title = re.sub(r"[^A-Za-z0-9]+", "_", title.lower()).strip("_")
        eid = f"wbff:{day_for_row.strftime('%Y%m%d')}:{time_local or 'na'}:{currency}:{base_title}"

        rows.append(EventRow(
            event_id=eid,
            currency=currency,
            impact=impact,
            impact_num=impact_num,
            title=title,
            actual=actual,
            forecast=forecast,
            previous=previous,
            date_local=day_for_row.isoformat(),
            time_local=time_local,
            when_tz=tz_name,
            when_iso=when_iso,
            has_specific_time=has_specific,
            url=url,
            is_major=1 if impact_num>=2 else 0,
            impact_included=1 if impact_num>0 else 0,
        ))

    return rows

def upsert_events(db_path: str, events: List[EventRow]):
    if not events:
        return 0
    con = sqlite3.connect(db_path)
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            currency TEXT, impact TEXT, impact_num INTEGER, title TEXT,
            actual TEXT, forecast TEXT, previous TEXT,
            date_local TEXT, time_local TEXT, when_tz TEXT, when_iso TEXT,
            has_specific_time INTEGER, url TEXT, is_major INTEGER, impact_included INTEGER,
            source TEXT
        )""")
        cols = {row[1] for row in con.execute("PRAGMA table_info(events)").fetchall()}
        for ev in events:
            rec = asdict(ev)
            filtered = {k:v for k,v in rec.items() if k in cols}
            col_list = ",".join(filtered.keys())
            ph = ",".join(["?"]*len(filtered))
            con.execute(f"INSERT OR REPLACE INTO events ({col_list}) VALUES ({ph})", tuple(filtered.values()))
        con.commit()
    finally:
        con.close()
    return len(events)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_dir", required=True, help="Directory with Wayback HTML files (*.html)")
    ap.add_argument("--db", required=True, help="SQLite path (e.g., outputs\\ff_calendar.sqlite)")
    ap.add_argument("--tz", default="America/New_York", help="Assumed local time zone for FF times")
    args = ap.parse_args()

    html_files = [os.path.join(args.in_dir, f) for f in os.listdir(args.in_dir) if f.lower().endswith(".html")]
    if not html_files:
        print("[error] No .html files found in", args.in_dir)
        sys.exit(2)

    total_upsert = 0
    for fp in sorted(html_files):
        m = re.search(r"ff_(\d{4}-\d{2}-\d{2})_", os.path.basename(fp))
        if not m:
            print("[skip] cannot infer week from", fp)
            continue
        week_monday = date.fromisoformat(m.group(1))
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        events = extract_rows_from_html(html, week_monday, args.tz)
        n = upsert_events(args.db, events)
        print(f"[parsed] {os.path.basename(fp)} -> {len(events)} rows (upserted {n})")
        total_upsert += n
    print(f"[done] total upserted: {total_upsert}")

if __name__ == "__main__":
    main()
