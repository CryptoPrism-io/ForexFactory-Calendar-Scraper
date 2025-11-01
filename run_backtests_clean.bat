@echo off
setlocal enableextensions enabledelayedexpansion

REM === CONFIG (edit paths if needed) ===
set "BASE=C:\Users\Aze\Documents\test run 8\News Calendar"
set "PRICES_DIR=C:\Users\Aze\Documents\test run 6.2\data\eurusd\timeframes"
set "PY=%BASE%\.venv\Scripts\python.exe"

cd /d "%BASE%" || (echo [err] cd failed & exit /b 1)

echo.
echo [1/6] Build surprises and pair signals...
"%PY%" compute_directional_surprises.py --db "outputs\ff_calendar.sqlite" --years 2012-2024 || goto :err

echo.
echo [2/6] Prefilter signals (sessions + impact>=2 + abs(z)>=1.0 + dedupe)...
call :prefilter "London,NewYork" "outputs\pair_signals_LN.csv" || goto :err
call :prefilter "London"         "outputs\pair_signals_L.csv"  || goto :err
call :prefilter "NewYork"        "outputs\pair_signals_NY.csv" || goto :err
call :prefilter "Sydney,Tokyo"   "outputs\pair_signals_ASIA.csv" || goto :err

echo.
echo [3/6] Split London+NY into train/val/test...
"%PY%" split_signals.py --in_csv "outputs\pair_signals_LN.csv" --out_dir "outputs" --train_end 2018-12-31 --val_end 2021-12-31 || goto :err

echo.
echo [4/6] Score ALL timeframes for TRAIN/VAL/TEST on London+NY...
call :score "outputs\pair_signals_LN_train.csv" "LN_M5_train"  M5  || goto :err
call :score "outputs\pair_signals_LN_train.csv" "LN_M15_train" M15 || goto :err
call :score "outputs\pair_signals_LN_train.csv" "LN_M30_train" M30 || goto :err
call :score "outputs\pair_signals_LN_train.csv" "LN_H1_train"  H1  || goto :err

call :score "outputs\pair_signals_LN_val.csv"   "LN_M5_val"    M5  || goto :err
call :score "outputs\pair_signals_LN_val.csv"   "LN_M15_val"   M15 || goto :err
call :score "outputs\pair_signals_LN_val.csv"   "LN_M30_val"   M30 || goto :err
call :score "outputs\pair_signals_LN_val.csv"   "LN_H1_val"    H1  || goto :err

call :score "outputs\pair_signals_LN_test.csv"  "LN_M5_test"   M5  || goto :err
call :score "outputs\pair_signals_LN_test.csv"  "LN_M15_test"  M15 || goto :err
call :score "outputs\pair_signals_LN_test.csv"  "LN_M30_test"  M30 || goto :err
call :score "outputs\pair_signals_LN_test.csv"  "LN_H1_test"   H1  || goto :err

echo.
echo [5/6] Score full-session variants (optional, single run each)...
call :score "outputs\pair_signals_L.csv"  "L_M15"   M15 || goto :err
call :score "outputs\pair_signals_NY.csv" "NY_M15"  M15 || goto :err
call :score "outputs\pair_signals_ASIA.csv" "ASIA_M15" M15 || goto :err

echo.
echo [6/6] Summarize all metrics...
"%PY%" summarize_backtests.py --metrics_glob "outputs\price_join_metrics_*.csv" --out_dir "outputs" || goto :err

echo.
echo [done] See outputs:
echo   outputs\price_join_metrics_*.csv
echo   outputs\trades_EURUSD_*.csv
echo   outputs\all_metrics_summary.csv
echo   outputs\top20_15m_by_tag.csv
exit /b 0

:prefilter
REM %1 = sessions (comma list), %2 = out_csv
echo    CMD: "%PY%" filter_signals_prejoin.py --pairs_csv "outputs\calendar_surprises_pair_signals.csv" --events_csv "outputs\calendar_surprises.csv" --out_csv "%~2" --sessions "%~1" --impact_min 2 --zmin 1.0 --dedupe_policy impact_then_absz --min_gap_min 0
"%PY%" filter_signals_prejoin.py --pairs_csv "outputs\calendar_surprises_pair_signals.csv" --events_csv "outputs\calendar_surprises.csv" --out_csv "%~2" --sessions "%~1" --impact_min 2 --zmin 1.0 --dedupe_policy impact_then_absz --min_gap_min 0
exit /b %errorlevel%

:score
REM %1 = pairs_csv, %2 = tag, %3 = TF
set "PAIRS=%~1"
set "TAG=%~2"
set "TF=%~3"

if /I "%TF%"=="M5"  (set "WIN=5,15,30,60"  & set "PAT={pair}_*_M5.csv")
if /I "%TF%"=="M15" (set "WIN=15,30,60"    & set "PAT={pair}_*_M15.csv")
if /I "%TF%"=="M30" (set "WIN=30,60,120"   & set "PAT={pair}_*_M30.csv")
if /I "%TF%"=="H1"  (set "WIN=60,120,240"  & set "PAT={pair}_*_H1.csv")

echo    [%TAG%] %TF%  windows=%WIN%
"%PY%" price_join_and_score_v2.py --pairs_csv "%PAIRS%" --events_csv "outputs\calendar_surprises.csv" --prices_dir "%PRICES_DIR%" --file_pattern "%PAT%" --tf %TF% --ts_col datetime --prices_tz UTC --windows %WIN% --tag "%TAG%"
exit /b %errorlevel%

:err
echo [ERROR] A step failed. Check the last messages above.
exit /b 1
