#!/usr/bin/env python3
# ForexFactory pipeline — fixed9
# - Uses Weekly Export ONLY for the *current week* (reliable). Historical weeks use HTML parsing.
# - Accepts comma/space-separated strings for currencies/impacts in config.
# - Keeps 'unknown' impacts; robust string coercion to avoid type errors.
# - Same outputs (raw weekly CSVs, normalized CSV, SQLite).

import argparse
import csv
import dataclasses
import io
import json
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Any

import pandas as pd
import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dtparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def wait_until_times_loaded(driver, timeout=30):
    """Return True when we see non-empty time cells; scrolls as needed."""
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    end = time.time() + float(timeout)
    # First wait until rows exist
    try:
        WebDriverWait(driver, min(10, float(timeout))).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".calendar__row, tr.calendar__row, tr"))
        )
    except Exception:
        pass

    while time.time() < end:
        # Gather candidate time elements
        elems = driver.find_elements(By.CSS_SELECTOR, ".calendar__time, td.time, .time, .calendar__cell--time")
        nonempty = [e for e in elems if e.text and e.text.strip() and e.text.strip() not in ("--","-","N/A")]
        if nonempty:
            return True
        # scroll a bit to trigger lazy loads
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(0.6)
    return False


DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
CAL_BASE = "https://www.forexfactory.com/calendar"
EXPORT_BASE = "https://nfs.faireconomy.media/ff_calendar_thisweek"

session = requests.Session()

@dataclass
class EventRow:
    event_id: Optional[str]
    date_local: str
    time_local: str
    currency: str
    impact: str
    title: str
    actual: Optional[str]
    forecast: Optional[str]
    previous: Optional[str]
    tz_source: str
    url: Optional[str]

# ---------- helpers ----------
def s_text(x: Any) -> str:
    if x is None: return ""
    if isinstance(x, (list, tuple)): x = x[0] if x else ""
    try: return str(x)
    except Exception: return ""

def s_strip(x: Any) -> str: return s_text(x).strip()

def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

def iso_week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}{w:02d}"

def week_bounds(d: date) -> Tuple[date, date]:
    mon = d - timedelta(days=d.weekday())
    return mon, mon + timedelta(days=6)

def is_current_week(d: date) -> bool:
    today = date.today()
    cmon, csun = week_bounds(today)
    return cmon <= d <= csun

def daterange(start: date, end: date) -> Iterable[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def discover_chromium_binary(explicit: Optional[str] = None) -> Optional[str]:
    if explicit and Path(explicit).exists():
        return str(Path(explicit))
    try:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for sub in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
            ):
                try:
                    with winreg.OpenKey(root, sub) as k:
                        val, _ = winreg.QueryValueEx(k, None)
                        if val and Path(val).exists():
                            return str(val)
                except OSError:
                    continue
    except Exception:
        pass
    for c in [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
    ]:
        if c and Path(c).exists():
            return str(c)
    return None

def _impact_from_text(t: Any) -> str:
    s = s_strip(t).lower()
    if not s: return "unknown"
    if s.isdigit():
        n = int(s)
        if n >= 4: return "high"
        if n == 3: return "medium"
        if n in (1,2): return "low"
    if "holiday" in s: return "holiday"
    if "high" in s or "red" in s or "!!!" in s: return "high"
    if "medium" in s or "orange" in s or "yellow" in s or "!!" in s: return "medium"
    if "low" in s or "grey" in s or "gray" in s or "!" in s: return "low"
    return "unknown"

def canonicalize_list(val, upper=True) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        items = [s_strip(x) for x in val]
    else:
        items = [s.strip() for s in re.split(r"[,\s;]+", s_text(val)) if s.strip()]
    if upper:
        items = [x.upper() for x in items]
    return items

# ---------- UC + parsing ----------
def _with_uc_driver(user_agent: str, headless: bool, chrome_binary: Optional[str] = None):
    import undetected_chromedriver as uc
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={user_agent}")
    resolved = discover_chromium_binary(chrome_binary)
    if resolved and not isinstance(resolved, str):
        resolved = str(resolved)
    if resolved:
        driver = uc.Chrome(options=options, browser_executable_path=resolved)
    else:
        driver = uc.Chrome(options=options)
    return driver

def fetch_week_html_uc(week_start: date, user_agent: str, page_wait_seconds: int = 25,
                       headless: bool = True, chrome_binary: Optional[str] = None) -> str:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By

    url = f"{CAL_BASE}?day={week_start.isoformat()}"
    options = uc.ChromeOptions()
    if headless: options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    resolved = discover_chromium_binary(chrome_binary)
    if resolved and not isinstance(resolved, str):
        resolved = str(resolved)
    if resolved:
        driver = uc.Chrome(options=options, browser_executable_path=resolved)
    else:
        driver = uc.Chrome(options=options)

    try:
        driver.get(url)

        def page_ready(drv):
            sel = [".calendar__row", "tr.calendar__row", "tr.calendar-row", ".calendar__table tr", "table tr"]
            for s in sel:
                if drv.find_elements(By.CSS_SELECTOR, s):
                    return True
            return False

        WebDriverWait(driver, page_wait_seconds).until(page_ready)
        # Nudge lazy loads
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.75)
        html = driver.page_source
        return html
    finally:
        try: driver.quit()
        except Exception: pass
        try: del driver
        except Exception: pass

def parse_calendar_week_structured(html: str, tz_guess: str = "America/New_York") -> List[EventRow]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[EventRow] = []
    candidates = soup.select("tr.calendar__row") or soup.select("tr.calendar-row") or soup.select("tr")
    current_date: Optional[str] = None
    for tr in candidates:
        day_header = tr.get("data-day") or tr.get("data-date")
        if day_header:
            try:
                d = dtparser.parse(s_strip(day_header)).date()
                current_date = d.isoformat()
                continue
            except Exception:
                pass
        th = tr.find("th")
        if th:
            try:
                d = dtparser.parse(th.get_text(" ", strip=True), fuzzy=True).date()
                current_date = d.isoformat()
                continue
            except Exception:
                pass
        tds = tr.find_all(["td","div"])
        if not tds or len(tds) < 3: continue

        def maybe_index(names):
            for i, td in enumerate(tds):
                blob = " ".join([(td.get("class") or []).__str__(), td.get_text(' ', strip=True)]).lower()
                if any(n in blob for n in names): return i
            return None

        idx_time = maybe_index(["time","session"]) or 0
        idx_currency = maybe_index(["currency","curr","ccy"]) or 1
        idx_impact = maybe_index(["impact","volatility","folder","bull"]) or 2
        idx_title = maybe_index(["event","title","detail","news"]) or 3
        idx_actual = maybe_index(["actual"])
        idx_forecast = maybe_index(["forecast"])
        idx_previous = maybe_index(["previous","prev","revised"])

        link = tds[idx_title].find("a") if isinstance(idx_title,int) else None
        url = link.get("href") if link and link.has_attr("href") else None
        event_id = None
        if url:
            m = re.search(r"(\d+)", url)
            if m: event_id = m.group(1)

        rows.append(EventRow(
            event_id=event_id,
            date_local=current_date or "",
            time_local=tds[idx_time].get_text(" ", strip=True) if isinstance(idx_time,int) else "",
            currency=(tds[idx_currency].get_text(" ", strip=True) if isinstance(idx_currency,int) else "").upper(),
            impact=_impact_from_text(tds[idx_impact].get_text(" ", strip=True) if isinstance(idx_impact,int) else ""),
            title=tds[idx_title].get_text(" ", strip=True) if isinstance(idx_title,int) else "",
            actual=tds[idx_actual].get_text(" ", strip=True) if isinstance(idx_actual,int) else None,
            forecast=tds[idx_forecast].get_text(" ", strip=True) if isinstance(idx_forecast,int) else None,
            previous=tds[idx_previous].get_text(" ", strip=True) if isinstance(idx_previous,int) else None,
            tz_source=tz_guess,
            url=url
        ))
    return rows

# ---------- normalization & storage ----------
def parse_time_label(date_str: str, time_label: str, tz_name: str) -> Optional[datetime]:
    t = s_strip(time_label).lower()
    if not t or t in {"--","all day","tentative","day 1","day 2","day 3"}:
        return None
    try:
        naive = dtparser.parse(t).time()
    except Exception:
        return None
    try:
        d = datetime.fromisoformat(s_strip(date_str))
    except Exception:
        return None
    tz = pytz.timezone(tz_name)
    local_dt = tz.localize(datetime(d.year, d.month, d.day, naive.hour, naive.minute, 0))
    return local_dt

def normalize_events(rows: List[EventRow], cfg: Dict) -> pd.DataFrame:
    tz = cfg["calendar"]["timezone"]
    majors = set(canonicalize_list(cfg["calendar"].get("currencies", []), upper=True))
    impacts = set(canonicalize_list(cfg["calendar"].get("impacts", []), upper=False))

    norm = []
    for r in rows:
        when_dt = parse_time_label(r.date_local, r.time_local, tz) if r.date_local else None
        impact_norm = s_strip(r.impact).lower() or "unknown"
        cur = s_strip(r.currency).upper()
        norm.append({
            "event_id": s_strip(r.event_id) or None,
            "currency": cur,
            "impact": impact_norm,
            "title": s_strip(r.title),
            "actual": s_strip(r.actual) or None,
            "forecast": s_strip(r.forecast) or None,
            "previous": s_strip(r.previous) or None,
            "date_local": s_strip(r.date_local) or None,
            "time_local": s_strip(r.time_local),
            "when_tz": tz,
            "when_iso": when_dt.isoformat() if when_dt else None,
            "has_specific_time": when_dt is not None,
            "url": s_strip(r.url) or None,
            "is_major": (cur in majors) if majors else True,
            "impact_included": ((impact_norm in impacts) or (impact_norm == "unknown")) if impacts else True,
        })
    df = pd.DataFrame(norm)
    if not df.empty:
        df = df[df["impact_included"]]
        if majors: df = df[df["is_major"]]
    return df.reset_index(drop=True)

def save_week_csv(rows: List[EventRow], out_dir: Path, week_start: date):
    ensure_dir(out_dir)
    key = iso_week_key(week_start)
    path = out_dir / f"events_raw_{key}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([field.name for field in dataclasses.fields(EventRow)])
        for r in rows:
            w.writerow([
                r.event_id, r.date_local, r.time_local, r.currency, r.impact, r.title,
                r.actual, r.forecast, r.previous, r.tz_source, r.url
            ])
    print(f"[saved] {path}")

def append_normalized_csv(df: pd.DataFrame, out_dir: Path):
    ensure_dir(out_dir)
    path = out_dir / "events_normalized.csv"
    header = not path.exists()
    df.to_csv(path, index=False, mode="a", header=header, encoding="utf-8")
    print(f"[appended] {path} (+{len(df)} rows)")

def upsert_sqlite(df: pd.DataFrame, db_path: Path):
    ensure_dir(db_path.parent)
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT,
        currency TEXT,
        impact TEXT,
        title TEXT,
        actual TEXT,
        forecast TEXT,
        previous TEXT,
        date_local TEXT,
        time_local TEXT,
        when_tz TEXT,
        when_iso TEXT,
        has_specific_time INTEGER,
        url TEXT,
        is_major INTEGER,
        impact_included INTEGER,
        PRIMARY KEY (event_id, date_local, title, currency, time_local)
    );
    """)
    for _, row in df.iterrows():
        cur.execute("""
        INSERT OR REPLACE INTO events (
            event_id,currency,impact,title,actual,forecast,previous,date_local,time_local,
            when_tz,when_iso,has_specific_time,url,is_major,impact_included
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);
        """, (
            row.get("event_id"),
            row.get("currency"),
            row.get("impact"),
            row.get("title"),
            row.get("actual"),
            row.get("forecast"),
            row.get("previous"),
            row.get("date_local"),
            row.get("time_local"),
            row.get("when_tz"),
            row.get("when_iso"),
            int(bool(row.get("has_specific_time"))),
            row.get("url"),
            int(bool(row.get("is_major"))),
            int(bool(row.get("impact_included"))),
        ))
    con.commit(); con.close()
    print(f"[upserted] {db_path} (+{len(df)} rows)")

def load_yaml(path: Path) -> Dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# ---------- driver flow ----------
def fetch_week_current_export(week_start: date, user_agent: str,
                              headless: bool, page_wait_seconds: int, chrome_binary: Optional[str]) -> List[EventRow]:
    # Export is only reliable for current week; we keep it simple here by pulling the page (to set context) and
    # then GETting ff_calendar_thisweek.{csv,json} within the same session via UC.
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By
    from selenium.common.exceptions import TimeoutException

    driver = _with_uc_driver(user_agent, headless, chrome_binary)
    try:
        url = f"{CAL_BASE}?day={week_start.isoformat()}"
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(lambda d: d.find_elements(By.PARTIAL_LINK_TEXT, "Export"))
        except TimeoutException:
            pass
        # Prefer CSV
        driver.get(f"{EXPORT_BASE}.csv")
        raw = driver.execute_script("return document.body ? document.body.innerText : '';") or ""
        rows: List[EventRow] = []
        if raw and len(raw) > 80:
            # parse CSV with flexible header
            lines = [ln for ln in raw.splitlines() if ln.strip()]
            header_idx = 0
            for i, ln in enumerate(lines[:10]):
                low = ln.lower()
                if "date" in low and "time" in low and ("impact" in low or "importance" in low):
                    header_idx = i; break
            rdr = csv.DictReader(lines[header_idx:])
            for rec in rdr:
                low = { (k or "").lower(): (v or "") for k,v in rec.items() }
                dt_str = low.get("date") or low.get("day") or ""
                tm_str = low.get("time") or ""
                ccy = low.get("currency") or low.get("country") or ""
                title = low.get("title") or low.get("event") or low.get("detail") or ""
                impact_raw = low.get("impact") or low.get("importance") or ""
                url_e = low.get("url") or low.get("link") or ""
                event_id = None
                if url_e:
                    m = re.search(r"(\d+)", url_e)
                    if m: event_id = m.group(1)
                try:
                    d_iso = dtparser.parse(dt_str).date().isoformat() if dt_str else ""
                except Exception:
                    d_iso = ""
                rows.append(EventRow(
                    event_id=event_id, date_local=d_iso, time_local=tm_str,
                    currency=ccy.upper(), impact=_impact_from_text(impact_raw), title=title,
                    actual=low.get("actual"), forecast=low.get("forecast"), previous=low.get("previous"),
                    tz_source="America/New_York", url=url_e or None
                ))
        return rows
    finally:
        try: driver.quit()
        except Exception: pass
        try: del driver
        except Exception: pass

@retry(reraise=True, stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=1, max=6),
       retry=retry_if_exception_type((RuntimeError,)))
def fetch_week(week_start: date, user_agent: str,
               headless: bool = True, page_wait_seconds: int = 25,
               chrome_binary: Optional[str] = None) -> List[EventRow]:
    if is_current_week(week_start):
        rows = fetch_week_current_export(week_start, user_agent, headless, page_wait_seconds, chrome_binary)
        if rows:
            return rows
    # Historical weeks -> HTML parse
    html = fetch_week_html_uc(week_start, user_agent, page_wait_seconds, headless, chrome_binary)
    parsed = parse_calendar_week_structured(html) or []
    return parsed

# ---------- CLI ----------
def cmd_run(args):
    cfg = load_yaml(Path(args.config))
    out_dir = Path(cfg.get("storage", {}).get("out_dir", "outputs"))
    db_path = Path(cfg.get("storage", {}).get("db_path", "outputs/ff_calendar.sqlite"))

    sc = cfg.get("scrape", {}) or {}
    ua = sc.get("user_agent", DEFAULT_UA)
    headless = bool(sc.get("headless", True))
    page_wait = int(sc.get("page_wait_seconds", 25))
    delay = float(sc.get("delay_seconds", 3))
    chrome_binary = sc.get("chrome_binary")

    cal = cfg.get("calendar", {}) or {}
    tz = cal.get("timezone", "America/New_York")
    currencies = canonicalize_list(cal.get("currencies", ["USD","EUR","GBP","JPY","AUD","NZD","CAD","CHF"]), upper=True)
    impacts = canonicalize_list(cal.get("impacts", ["high","medium","low"]), upper=False)
    cfg_norm = {"calendar": {"timezone": tz, "currencies": currencies, "impacts": impacts}}

    if args.start and args.end:
        start = dtparser.parse(args.start).date()
        end = dtparser.parse(args.end).date()
    else:
        today = date.today()
        start, end = week_bounds(today)

    mondays = sorted({ d - timedelta(days=d.weekday()) for d in daterange(start, end) })

    all_norm = []
    for monday in mondays:
        try:
            rows = fetch_week(monday, ua, headless=headless, page_wait_seconds=page_wait, chrome_binary=chrome_binary)
        except Exception as e:
            print(f"[error] week {monday}: {e}")
            time.sleep(delay); continue

        if not rows:
            print(f"[warn] No rows parsed for week starting {monday}")
            time.sleep(delay); continue

        save_week_csv(rows, out_dir, monday)
        df = normalize_events(rows, cfg_norm)
        if df.empty:
            print(f"[warn] Normalization produced 0 rows for week {monday}")
        else:
            append_normalized_csv(df, out_dir)
            upsert_sqlite(df, db_path)
            all_norm.append(df)

        time.sleep(delay + random.uniform(0, max(0.0, delay*0.5)))

    if all_norm:
        df_all = pd.concat(all_norm, ignore_index=True)
        print(df_all.tail(20).to_string(index=False))
    else:
        print("[done] No normalized rows.")

def cmd_upcoming(args):
    cfg = load_yaml(Path(args.config))
    db_path = Path(cfg.get("storage", {}).get("db_path", "outputs/ff_calendar.sqlite"))
    horizon_hours = int(args.hours or 48)
    if not db_path.exists():
        print(f"[error] DB not found at {db_path}. Run 'run' first.", file=sys.stderr)
        sys.exit(2)
    con = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=horizon_hours)
    q = "SELECT currency, impact, title, when_iso, url FROM events WHERE when_iso IS NOT NULL ORDER BY when_iso ASC"
    df = pd.read_sql_query(q, con); con.close()
    if df.empty:
        print("No timed events in DB."); return
    df["when_dt"] = pd.to_datetime(df["when_iso"], utc=True, errors="coerce")
    mask = (df["when_dt"] >= pd.Timestamp(now)) & (df["when_dt"] <= pd.Timestamp(cutoff))
    show = df.loc[mask, ["when_dt","currency","impact","title","url"]].sort_values("when_dt")
    print(show.to_string(index=False))

def build_argparser():
    p = argparse.ArgumentParser(description="FF calendar scraper (fixed9)")
    sub = p.add_subparsers(dest="cmd")
    prun = sub.add_parser("run", help="Fetch/parse weeks and persist to CSV/SQLite")
    prun.add_argument("--config", required=True)
    prun.add_argument("--start")
    prun.add_argument("--end")
    prun.set_defaults(func=cmd_run)
    pup = sub.add_parser("upcoming", help="List upcoming events from SQLite")
    pup.add_argument("--config", required=True)
    pup.add_argument("--hours")
    pup.set_defaults(func=cmd_upcoming)
    return p

def main(argv=None):
    argv = argv or sys.argv[1:]
    p = build_argparser(); args = p.parse_args(argv)
    if not args.cmd:
        p.print_help(); return 0
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())

    # --- injected: robust wait for time cells ---
    try:
        _ok = wait_until_times_loaded(driver, timeout=page_wait_seconds if 'page_wait_seconds' in locals() or 'page_wait_seconds' in globals() else 30)
    except Exception:
        _ok = False
    if not _ok:
        # Try additional scroll + short waits
        import time
        for _ in range(6):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(0.5)
            if wait_until_times_loaded(driver, timeout=5):
                _ok = True
                break
    # --- end injected ---
