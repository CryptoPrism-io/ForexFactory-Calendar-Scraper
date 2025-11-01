# calendar_verify_and_prepare_directional.py
# Builds an enriched “golden” calendar dataset, adds surprise & directional_surprise,
# and writes quality reports to ./outputs

import argparse, sqlite3, re
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np

DEF_DB = 'outputs/ff_calendar.sqlite'
DEF_NORM = 'outputs/events_normalized.csv'
OUT_DIR = 'outputs'
IMPACT_MAP = {'unknown':0,'low':1,'medium':2,'high':3}

def read_events(db_path: Path, norm_csv: Path) -> pd.DataFrame:
    if db_path.exists():
        con = sqlite3.connect(db_path)
        df = pd.read_sql_query('select * from events', con)
        con.close()
        print(f'[read] {len(df):,} rows from {db_path}')
        return df
    if norm_csv.exists():
        df = pd.read_csv(norm_csv)
        print(f'[read] {len(df):,} rows from {norm_csv}')
        return df
    raise SystemExit(f'No events found. Looked for {db_path} and {norm_csv}')

def iso_week_id(s: pd.Series) -> pd.Series:
    def f(x):
        if not isinstance(x,str) or len(x)<8: return None
        dt = pd.to_datetime(x, errors='coerce')
        if pd.isna(dt): return None
        y,w,_ = dt.isocalendar().astype(int)
        return f'{y}{w:02d}'
    return s.apply(f)

def round_down(ts: pd.Series, freq: str) -> pd.Series:
    t = pd.to_datetime(ts, utc=True, errors='coerce')
    return t.dt.floor(freq)

def parse_number(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    if text is None: return None,None
    s = str(text).strip()
    if not s or s.lower() in {'n/a','na','--'}: return None,None
    kind = 'pct' if '%' in s else 'level'
    s = s.replace('%',' ').replace('\\xa0',' ').strip()
    s = re.sub(r'\\b(bn|billion)\\b','B',s,flags=re.I)
    s = re.sub(r'\\b(mln|million)\\b','M',s,flags=re.I)
    s = re.sub(r'\\b(thou|thousand)\\b','K',s,flags=re.I)
    s = re.sub(r'[^\\w\\.\\-\\+\\sKMGT]','',s)
    s = s.replace(',','').replace(' ','')
    mult = 1.0
    m = re.match(r'^([+-]?\\d*\\.?\\d+)([KMBT])?$', s, flags=re.I)
    if not m:
        m2 = re.search(r'([+-]?\\d*\\.?\\d+)', s)
        if not m2: return None,None
        return float(m2.group(1)), kind
    num = float(m.group(1)); suf = (m.group(2) or '').upper()
    mult = {'K':1e3,'M':1e6,'B':1e9,'T':1e12}.get(suf,1.0)
    return num*mult, kind

HIGHER_BETTER_PATTERNS = [
    r'\\b(gdp|gross domestic product)\\b',
    r'\\b(retail sales|core retail sales)\\b',
    r'\\b(non[- ]farm payrolls|nfp|employment change|payrolls)\\b',
    r'\\b(average hourly earnings|wage|earnings)\\b',
    r'\\b(cpi|core cpi|pce price|core pce|ppi|core ppi|inflation)\\b',
    r'\\b(ism|pmi)\\b',
    r'\\b(industrial production|factory orders|durable goods|capex)\\b',
    r'\\b(housing starts|building permits|home sales|new home sales|existing home sales|pending home sales)\\b',
    r'\\b(consumer confidence|business confidence|ifo|zew|gfk|sentiment)\\b',
    r'\\b(leading indicators)\\b',
]
LOWER_BETTER_PATTERNS = [
    r'\\bunemployment rate\\b',
    r'\\b(jobless claims|initial claims|continuing claims)\\b',
    r'\\bunemployment change\\b',
]

def classify_direction(title_norm: str) -> str:
    if not isinstance(title_norm,str) or not title_norm: return 'ambiguous'
    t = title_norm.lower()
    for pat in HIGHER_BETTER_PATTERNS:
        if re.search(pat,t): return 'higher_better'
    for pat in LOWER_BETTER_PATTERNS:
        if re.search(pat,t): return 'lower_better'
    return 'ambiguous'

def derive_enriched(df: pd.DataFrame) -> pd.DataFrame:
    dfe = df.copy()
    for c in ['currency','impact','title','date_local','time_local','when_tz','url','actual','forecast','previous']:
        if c in dfe.columns: dfe[c] = dfe[c].astype('string').fillna('').str.strip()
    dfe['impact_norm'] = dfe['impact'].str.lower().replace({'medium':'medium','med':'medium'})
    dfe['impact_num'] = dfe['impact_norm'].map(IMPACT_MAP).fillna(0).astype(int)
    dfe['when_dt_utc'] = pd.to_datetime(dfe.get('when_iso'), utc=True, errors='coerce')
    dfe['has_time'] = dfe['has_specific_time'].fillna(False).astype(bool)
    dfe['week_id'] = iso_week_id(dfe.get('date_local'))
    dfe['day_id'] = dfe['date_local'].where(dfe['date_local'].notna() & (dfe['date_local']!=''), other=None)
    dfe['hour_local'] = dfe['time_local'].str.extract(r'(\\d{1,2}):?(\\d{2})?\\s*(am|pm)?', expand=True).fillna('').agg(''.join, axis=1)
    for freq,col in [('1min','ts_1m'),('5min','ts_5m'),('15min','ts_15m'),('60min','ts_1h')]:
        dfe[col] = round_down(dfe['when_dt_utc'], freq)
    dfe['actual_val'], dfe['actual_kind'] = zip(*dfe['actual'].map(parse_number))
    dfe['forecast_val'], dfe['forecast_kind'] = zip(*dfe['forecast'].map(parse_number))
    dfe['previous_val'], dfe['previous_kind'] = zip(*dfe['previous'].map(parse_number))
    same_kind = (dfe['actual_kind']==dfe['forecast_kind']) & dfe['actual_kind'].notna()
    dfe['surprise_kind'] = np.where(same_kind, dfe['actual_kind'], None)
    dfe['surprise_raw'] = np.where(
        same_kind & dfe['actual_val'].notna() & dfe['forecast_val'].notna(),
        dfe['actual_val'].astype(float) - dfe['forecast_val'].astype(float),
        np.nan
    )
    dfe['title_norm'] = (
        dfe['title'].str.lower().str.replace(r'\\s+',' ',regex=True)
        .str.replace(r'[^a-z0-9 %/\\.\\-]','',regex=True).str.strip()
    )
    grp = dfe.groupby('title_norm', dropna=True)['surprise_raw']
    stats = grp.agg(['count','mean','std']).reset_index().rename(columns={'mean':'mu','std':'sigma'})
    stats['ok'] = (stats['count']>=10) & stats['sigma'].notna() & (stats['sigma']>0)
    dfe = dfe.merge(stats[['title_norm','mu','sigma','ok']], on='title_norm', how='left')
    dfe['surprise_z'] = np.where(dfe['ok'].fillna(False) & dfe['surprise_raw'].notna(),
                                 (dfe['surprise_raw']-dfe['mu'])/dfe['sigma'], np.nan)
    dfe['direction'] = dfe['title_norm'].apply(classify_direction)
    sign = np.select([dfe['direction'].eq('higher_better'), dfe['direction'].eq('lower_better')],[1.0,-1.0], default=np.nan)
    dfe['directional_surprise'] = sign * dfe['surprise_raw']
    grp2 = dfe.groupby('title_norm', dropna=True)['directional_surprise']
    stats2 = grp2.agg(['count','mean','std']).reset_index().rename(columns={'mean':'mu_dir','std':'sigma_dir'})
    stats2['ok_dir'] = (stats2['count']>=10) & stats2['sigma_dir'].notna() & (stats2['sigma_dir']>0)
    dfe = dfe.merge(stats2[['title_norm','mu_dir','sigma_dir','ok_dir']], on='title_norm', how='left')
    dfe['directional_z'] = np.where(dfe['ok_dir'].fillna(False) & dfe['directional_surprise'].notna(),
                                    (dfe['directional_surprise']-dfe['mu_dir'])/dfe['sigma_dir'], np.nan)
    return dfe

def quality_reports(df: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(df)
    timed = int(df['when_dt_utc'].notna().sum())
    unknown_impact = int((df['impact_norm']=='unknown').sum())
    dupes = df.groupby(['event_id','date_local','currency','title','time_local'], dropna=False).size()
    dupes = dupes[dupes>1].reset_index().rename(columns={0:'dupe_count'})
    weeks = df['week_id'].dropna().unique().size
    overall = pd.DataFrame([{
        'rows_total': total,
        'rows_with_time': timed,
        'pct_with_time': round(100*timed/max(total,1),2),
        'rows_unknown_impact': unknown_impact,
        'pct_unknown_impact': round(100*unknown_impact/max(total,1),2),
        'unique_weeks_with_rows': weeks,
        'duplicate_keys_found': len(dupes),
        'rows_with_surprise_raw': int(df['surprise_raw'].notna().sum()),
        'pct_with_surprise_raw': round(100*df['surprise_raw'].notna().sum()/max(total,1),2),
        'rows_with_direction': int((df['direction']!='ambiguous').sum()),
        'rows_with_directional_surprise': int(df['directional_surprise'].notna().sum()),
    }])
    overall.to_csv(out_dir/'calendar_quality_overall.csv', index=False)
    df['year'] = df['date_local'].str.slice(0,4)
    df.groupby('year', dropna=False).size().reset_index(name='rows').to_csv(out_dir/'calendar_summary_by_year.csv', index=False)
    df.groupby('currency', dropna=False).size().reset_index(name='rows').sort_values('rows', ascending=False).to_csv(out_dir/'calendar_summary_by_currency.csv', index=False)
    df.groupby('impact_norm', dropna=False).size().reset_index(name='rows').sort_values('rows', ascending=False).to_csv(out_dir/'calendar_summary_by_impact.csv', index=False)
    tmp = df.copy(); tmp['has_time'] = tmp['when_dt_utc'].notna()
    wk = tmp.groupby('week_id', dropna=False)['has_time'].agg(['count','sum']).reset_index()
    wk['timed_pct'] = (wk['sum']/wk['count']).round(3)
    wk.sort_values(['timed_pct','count'], inplace=True)
    wk.to_csv(out_dir/'calendar_weeks_timed_ratio.csv', index=False)
    if not dupes.empty: dupes.to_csv(out_dir/'calendar_duplicate_keys.csv', index=False)
    cov = df.groupby('title_norm').agg(
        rows=('surprise_raw','size'),
        with_surprise=('surprise_raw', lambda s: int(s.notna().sum())),
        with_dir=('directional_surprise', lambda s: int(s.notna().sum()))
    ).reset_index()
    cov['pct_with_surprise'] = (100*cov['with_surprise']/cov['rows']).round(2)
    cov['pct_with_directional'] = (100*cov['with_dir']/cov['rows']).round(2)
    cov.sort_values('with_dir', ascending=False).to_csv(out_dir/'calendar_surprise_coverage_by_title.csv', index=False)
    print('[wrote]', out_dir / 'calendar_quality_overall.csv')
    print('[wrote]', out_dir / 'calendar_summary_by_year.csv')
    print('[wrote]', out_dir / 'calendar_summary_by_currency.csv')
    print('[wrote]', out_dir / 'calendar_summary_by_impact.csv')
    print('[wrote]', out_dir / 'calendar_weeks_timed_ratio.csv')
    print('[wrote]', out_dir / 'calendar_surprise_coverage_by_title.csv')
    print('[wrote]', out_dir / 'calendar_duplicate_keys.csv')

def write_golden(df: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = [
        'event_id','currency','impact_norm','impact_num','title','title_norm',
        'actual','forecast','previous','actual_val','forecast_val','previous_val',
        'surprise_kind','surprise_raw','surprise_z',
        'direction','directional_surprise','directional_z',
        'date_local','time_local','when_tz','when_dt_utc','week_id','day_id','hour_local',
        'ts_1m','ts_5m','ts_15m','ts_1h','url','is_major','impact_included'
    ]
    keep = [c for c in cols if c in df.columns]
    gold = df[keep].copy()
    gold.to_csv(out_dir/'calendar_events_golden.csv', index=False)
    try:
        import pyarrow as pa, pyarrow.parquet as pq
        pq.write_table(pa.Table.from_pandas(gold), out_dir/'calendar_events_golden.parquet')
        print('[wrote]', out_dir / 'calendar_events_golden.parquet')
    except Exception as e:
        print(f'[warn] Parquet not written (install pyarrow to enable). {e}')
    print('[wrote]', out_dir / 'calendar_events_golden.csv')
    return gold

def main():
    ap = argparse.ArgumentParser(description='Verify calendar and prepare golden dataset + directional surprises')
    ap.add_argument('--db', default=DEF_DB)
    ap.add_argument('--normalized_csv', default=DEF_NORM)
    ap.add_argument('--out_dir', default=OUT_DIR)
    args = ap.parse_args()
    df = read_events(Path(args.db), Path(args.normalized_csv))
    dfe = derive_enriched(df)
    quality_reports(dfe, Path(args.out_dir))
    write_golden(dfe, Path(args.out_dir))

if __name__ == '__main__':
    main()
