#!/usr/bin/env python3
# compute_directional_surprises.py — clean standalone version
from __future__ import annotations

import argparse, re, sqlite3, csv, os
from typing import Optional, Dict, List, Tuple
import pandas as pd

# ------------------------- numeric parsing -------------------------
_NUM_RE = re.compile(
    r"""
    (?P<sign>[-+])?
    \s*
    (?P<num>(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d+)?)
    \s*
    (?P<suf>%|[KMB])?
    """,
    re.VERBOSE | re.IGNORECASE,
)

def parse_number(s: Optional[str]) -> Optional[float]:
    """
    Extract first numeric token (handles commas, %, K/M/B suffix).
    Returns None if no number found.
    Note: '%' is treated as percentage *points* (no /100).
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    sign = -1.0 if (m.group("sign") == "-") else 1.0
    num = float(m.group("num").replace(",", ""))
    suf = (m.group("suf") or "").upper()
    if suf == "K":
        num *= 1_000
    elif suf == "M":
        num *= 1_000_000
    elif suf == "B":
        num *= 1_000_000_000
    return sign * num

# ------------------------- direction rules -------------------------
def load_rules(path: str) -> List[Tuple[re.Pattern, bool]]:
    """
    Read CSV with columns:
      - 'pattern' (preferred) OR legacy 'title_pattern'
      - 'good_is_higher' in {0,1,true,False,...}
    Returns list of (compiled_regex, good_is_higher_bool)
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"rules CSV not found: {path}")
    rules: List[Tuple[re.Pattern, bool]] = []
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        header_map = {k.lower(): k for k in (rdr.fieldnames or [])}
        pat_key = header_map.get("pattern") or header_map.get("title_pattern")
        gih_key = header_map.get("good_is_higher")
        if not pat_key or not gih_key:
            raise SystemExit("rules CSV must have columns: pattern,good_is_higher")
        for row in rdr:
            pat = (row.get(pat_key) or "").strip()
            if not pat:
                continue
            gih_raw = str(row.get(gih_key, "")).strip()
            good_is_higher = gih_raw in ("1", "true", "True", "TRUE")
            # substring, case-insensitive
            rules.append((re.compile(re.escape(pat), re.I), good_is_higher))
    return rules

def good_is_higher_for(title: str, rules: List[Tuple[re.Pattern, bool]]) -> bool:
    for rx, good in rules:
        if rx.search(title or ""):
            return good
    return True  # sensible default if no match

# ------------------------- pair projection -------------------------
def project_to_pairs(event_ccy: str, cc_strength_sign: int, pairs: List[str]) -> Dict[str, Optional[int]]:
    """
    Map currency-strength sign (+1/-1/0) to pair direction for each pair in 'pairs'.
    If event_ccy == base -> pair direction = strength sign
    If event_ccy == quote -> direction = - strength sign
    Else -> None (no signal for that pair)
    """
    out: Dict[str, Optional[int]] = {}
    if cc_strength_sign == 0:
        for p in pairs:
            out[p] = 0
        return out
    eccy = (event_ccy or "").upper().strip()
    for p in pairs:
        P = p.upper().strip()
        if len(P) != 6:
            out[P] = None
            continue
        base, quote = P[:3], P[3:]
        if eccy == base:
            out[P] = +1 if cc_strength_sign > 0 else -1
        elif eccy == quote:
            out[P] = -1 if cc_strength_sign > 0 else +1
        else:
            out[P] = None
    return out

# ------------------------- main -------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help=r"path to outputs\ff_calendar.sqlite")
    ap.add_argument("--out_events", default=r"outputs\calendar_surprises.csv")
    ap.add_argument("--out_pairs",  default=r"outputs\calendar_surprises_pair_signals.csv")
    ap.add_argument("--pairs", default="EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,NZDUSD,USDCAD")
    ap.add_argument("--rules_csv", default="event_direction_rules.csv")
    ap.add_argument("--years", default="2012-2024", help="YYYY-YYYY or single YYYY")
    args = ap.parse_args()

    # parse year range
    if "-" in args.years:
        y1, y2 = [int(x) for x in args.years.split("-", 1)]
    else:
        y1 = y2 = int(args.years)

    pairs = [x.strip().upper() for x in args.pairs.split(",") if x.strip()]
    rules = load_rules(args.rules_csv)

    # load events
    con = sqlite3.connect(args.db)
    df = pd.read_sql_query("SELECT * FROM events", con)

    # robust year filtering
    if "year_local" in df.columns:
        years = pd.to_numeric(df["year_local"], errors="coerce")
    else:
        years = pd.to_datetime(df.get("date_local"), errors="coerce").dt.year
    df = df.assign(year_local=years).dropna(subset=["year_local"]).copy()
    df["year_local"] = df["year_local"].astype(int)
    df = df[(df["year_local"] >= y1) & (df["year_local"] <= y2)].copy()

    # numeric parse for actual/forecast/previous
    for col in ("actual", "forecast", "previous"):
        if col in df.columns:
            df[f"num_{col}"] = df[col].apply(parse_number)
        else:
            df[f"num_{col}"] = None

    # surprise = actual - forecast when both present
    def _surp(row):
        a = row.get("num_actual")
        f = row.get("num_forecast")
        if pd.notna(a) and pd.notna(f):
            return a - f
        return None
    df["surprise"] = df.apply(_surp, axis=1)

    # sign helper
    def sign(x):
        if x is None or pd.isna(x): return 0
        return 1 if x > 0 else (-1 if x < 0 else 0)

    df["surprise_sign"] = df["surprise"].apply(sign)

    # good_is_higher from rules, then currency-strength sign
    df["good_is_higher"] = df.get("title").apply(lambda t: 1 if good_is_higher_for(str(t), rules) else 0)
    df["cc_strength_sign"] = df.apply(
        lambda r: (r["surprise_sign"] if r["good_is_higher"] == 1 else -r["surprise_sign"]),
        axis=1,
    )

    # write per-event surprises
    os.makedirs(os.path.dirname(args.out_events) or ".", exist_ok=True)
    cols_events_pref = [
        "event_id","date_local","time_local","currency","title","impact","impact_num","source",
        "actual","forecast","previous","num_actual","num_forecast","num_previous",
        "surprise","surprise_sign","good_is_higher","cc_strength_sign","when_iso"
    ]
    cols_events = [c for c in cols_events_pref if c in df.columns]
    df_events = df[cols_events].copy()
    df_events.to_csv(args.out_events, index=False, encoding="utf-8")
    print(f"[wrote] {args.out_events}  ({len(df_events)} rows)")

    # project to pairs and write
    os.makedirs(os.path.dirname(args.out_pairs) or ".", exist_ok=True)
    recs: List[Dict[str, object]] = []
    for _, r in df.iterrows():
        ccy = str(r.get("currency", "")).upper()
        sig = int(r.get("cc_strength_sign", 0)) if pd.notna(r.get("cc_strength_sign")) else 0
        for pair, dirsig in project_to_pairs(ccy, sig, pairs).items():
            if dirsig is None:
                continue
            recs.append({
                "event_id": r.get("event_id"),
                "date_local": r.get("date_local"),
                "time_local": r.get("time_local"),
                "currency": ccy,
                "title": r.get("title"),
                "pair": pair,
                "direction_sign": dirsig,
                "surprise": r.get("surprise"),
                "surprise_sign": r.get("surprise_sign"),
                "cc_strength_sign": sig,
                "impact": r.get("impact"),
                "impact_num": r.get("impact_num"),
                "source": r.get("source"),
                "when_iso": r.get("when_iso"),
            })
    df_pairs = pd.DataFrame.from_records(recs)
    df_pairs.to_csv(args.out_pairs, index=False, encoding="utf-8")
    print(f"[wrote] {args.out_pairs}  ({len(df_pairs)} rows)")

if __name__ == "__main__":
    raise SystemExit(main())
