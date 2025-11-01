# ForexFactory Economic Calendar Pipeline (Lightweight)

Scrapes weekly ForexFactory calendar pages, normalizes times to your timezone, and writes CSV + SQLite.

## Quickstart
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python forexfactory_pipeline.py run --config config.yaml --start 2012-01-01 --end 2024-12-31
python forexfactory_pipeline.py upcoming --config config.yaml --hours 48
```
Use the Windows helpers provided for convenience.
