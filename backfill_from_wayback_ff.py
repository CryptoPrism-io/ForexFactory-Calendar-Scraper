#!/usr/bin/env python3
# Wayback backfill for ForexFactory calendar with robust + fuzzy fallback.
from __future__ import annotations

import argparse, os, time, json, ssl, certifi
from datetime import date, timedelta
from urllib.parse import quote
from urllib.request import urlopen, Request

SSL_CTX = ssl.create_default_context(cafile=certifi.where())

MONTHS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
def monabbr(d: date) -> str: return MONTHS[d.month-1]
def mmmdd_y(d: date, zero_pad: bool=False) -> str:
    dd = f"{d.day:02d}" if zero_pad else str(d.day)
    return f"{monabbr(d)}{dd}.{d.year}"
def mmm_dot_dd_y(d: date, zero_pad: bool=False) -> str:
    dd = f"{d.day:02d}" if zero_pad else str(d.day)
    return f"{monabbr(d)}.{dd}.{d.year}"
def mmmdd_yy(d: date, zero_pad: bool=False) -> str:
    dd = f"{d.day:02d}" if zero_pad else str(d.day)
    return f"{monabbr(d)}{dd}.{str(d.year)[2:]}"
def mmm_dot_dd_yy(d: date, zero_pad: bool=False) -> str:
    dd = f"{d.day:02d}" if zero_pad else str(d.day)
    return f"{monabbr(d)}.{dd}.{str(d.year)[2:]}"

def mondays_between(d1: date, d2: date):
    cur = d1
    while cur.weekday() != 0:  # snap to Monday
        cur += timedelta(days=1)
    while cur <= d2:
        yield cur
        cur += timedelta(days=7)

def cdx(url: str, from_yyyymmdd: str | None = None, to_yyyymmdd: str | None = None):
    q = f"https://web.archive.org/cdx/search/cdx?url={quote(url)}&output=json&filter=statuscode:200&collapse=digest"
    if from_yyyymmdd: q += f"&from={from_yyyymmdd}"
    if to_yyyymmdd:   q += f"&to={to_yyyymmdd}"
    with urlopen(Request(q, headers={"User-Agent":"Mozilla/5.0"}), timeout=30, context=SSL_CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not data or len(data) <= 1:
        return []
    # header: ["urlkey","timestamp","original","mimetype","statuscode","digest","length"]
    return [(row[1], row[2]) for row in data[1:]]

def fetch_snapshot(ts: str, original_url: str) -> str:
    snap = f"https://web.archive.org/web/{ts}id_/{original_url}"
    with urlopen(Request(snap, headers={"User-Agent":"Mozilla/5.0"}), timeout=30, context=SSL_CTX) as r:
        return r.read().decode("utf-8", errors="ignore")

def candidates_for_monday(monday: date) -> list[str]:
    # Known legacy shapes
    iso = monday.isoformat()                     # 2012-01-02
    ymd_nopad = f"{monday.year}-{monday.month}-{monday.day}"  # 2012-1-2
    dot_iso = f"{monday.year}.{monday.month:02d}.{monday.day:02d}"  # 2012.01.02

    m = mmmdd_y(monday, False)                   # jan2.2012
    m0 = mmmdd_y(monday, True)                   # jan02.2012
    mdot = mmm_dot_dd_y(monday, False)           # jan.2.2012
    mdot0 = mmm_dot_dd_y(monday, True)           # jan.02.2012
    m_yy = mmmdd_yy(monday, False)               # jan2.12
    m0_yy = mmmdd_yy(monday, True)               # jan02.12
    mdot_yy = mmm_dot_dd_yy(monday, False)       # jan.2.12
    mdot0_yy = mmm_dot_dd_yy(monday, True)       # jan.02.12

    sun, tue = monday - timedelta(days=1), monday + timedelta(days=1)
    s, s0 = mmmdd_y(sun, False), mmmdd_y(sun, True)
    t, t0 = mmmdd_y(tue, False), mmmdd_y(tue, True)

    nxt = monday + timedelta(days=7)
    m_to, m0_to = mmmdd_y(nxt, False), mmmdd_y(nxt, True)

    bases = [
        "https://www.forexfactory.com/calendar",
        "http://www.forexfactory.com/calendar",
        "https://www.forexfactory.com/calendar.php",
        "http://www.forexfactory.com/calendar.php",
    ]
    qs = [
        f"?day={iso}", f"?day={ymd_nopad}", f"?day={dot_iso}",
        f"?day={m}", f"?day={m0}", f"?day={mdot}", f"?day={mdot0}",
        f"?day={m_yy}", f"?day={m0_yy}", f"?day={mdot_yy}", f"?day={mdot0_yy}",
        f"?day={s}", f"?day={s0}", f"?day={t}", f"?day={t0}",
        f"?week={m}", f"?week={m0}", f"?week={mdot}", f"?week={mdot0}",
        f"?week={m_yy}", f"?week={m0_yy}", f"?week={mdot_yy}", f"?week={mdot0_yy}",
        f"?week={s}", f"?week={s0}", f"?week={t}", f"?week={t0}",
        f"?range={m}-{m_to}", f"?range={m0}-{m0_to}",
        f"?month={monabbr(monday)}.{monday.year}", f"?month={monabbr(monday)}.{str(monday.year)[2:]}",
    ]
    return [b+q for b in bases for q in qs]

def fuzzy_week_capture(monday: date) -> tuple[str,str] | None:
    """
    If exact variants fail, search ANY calendar* capture during [Mon-2d, Mon+9d],
    prefer ?week=, then ?day=, then ?range=, then ?month=.
    Returns (timestamp, original_url) or None.
    """
    start = (monday - timedelta(days=2)).strftime("%Y%m%d")
    end   = (monday + timedelta(days=9)).strftime("%Y%m%d")
    rows = cdx("www.forexfactory.com/calendar*", start, end)
    if not rows:
        return None
    # Preferential pick
    prefs = ["?week=", "?day=", "?range=", "?month="]
    for p in prefs:
        for ts, orig in rows:
            if p in orig:
                return ts, orig
    # otherwise just return the first
    return rows[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--out", default="raw_wayback")
    ap.add_argument("--delay", type=float, default=0.7)
    args = ap.parse_args()

    d1 = date.fromisoformat(args.start); d2 = date.fromisoformat(args.end)
    os.makedirs(args.out, exist_ok=True)
    saved = misses = 0

    for monday in mondays_between(d1, d2):
        hit_ts = hit_url = None
        # 1) try explicit variants
        for url in candidates_for_monday(monday):
            try:
                rows = cdx(url)
            except Exception:
                continue
            if rows:
                hit_ts, _ = rows[0]
                hit_url = url
                break

        # 2) fuzzy fallback over the week window
        if not hit_ts:
            fw = fuzzy_week_capture(monday)
            if fw:
                hit_ts, hit_url = fw

        if not hit_ts:
            print(f"[miss] {monday} (tried many variants + fuzzy)")
            misses += 1
            continue

        try:
            html = fetch_snapshot(hit_ts, hit_url)
            fn = os.path.join(args.out, f"ff_{monday.isoformat()}_{hit_ts}.html")
            with open(fn, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[saved] {fn}  ← {hit_url}")
            saved += 1
            time.sleep(args.delay)
        except Exception as e:
            print(f"[error] {monday} {hit_url}: {e}")

    print(f"[done] saved={saved}, misses={misses}")

if __name__ == "__main__":
    main()
