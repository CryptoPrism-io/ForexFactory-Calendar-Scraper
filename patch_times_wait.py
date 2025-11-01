
"""
patch_times_wait.py
Adds robust "wait for times" logic to forexfactory_pipeline.py so historical weeks
populate time cells before we capture HTML.

What it changes:
- Injects imports: WebDriverWait, ExpectedConditions, By
- Adds helper: wait_until_times_loaded(driver, timeout)
- In fetch_week_html_uc(...): after driver.get(url), waits for time cells with text;
  scrolls to trigger lazy loads; then captures page_source.

Creates a backup: forexfactory_pipeline.py.bak
"""

from pathlib import Path
import re

TARGET = Path("forexfactory_pipeline.py")
BACKUP = Path("forexfactory_pipeline.py.bak")

src = TARGET.read_text(encoding="utf-8")

# 1) Ensure Selenium support imports
def ensure_imports(text: str) -> str:
    need = [
        "from selenium.webdriver.common.by import By",
        "from selenium.webdriver.support.ui import WebDriverWait",
        "from selenium.webdriver.support import expected_conditions as EC",
    ]
    missing = [imp for imp in need if imp not in text]
    if missing:
        # put imports after the first selenium import we find
        m = re.search(r"^import selenium.*?$", text, flags=re.M)
        insert_at = m.end() if m else 0
        block = "\n" + "\n".join(missing) + "\n"
        text = text[:insert_at] + block + text[insert_at:]
    return text

# 2) Add helper wait function (idempotent)
HELPER_NAME = "wait_until_times_loaded"
if HELPER_NAME not in src:
    helper = '''
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
'''
    # Insert helper after imports (after last import line)
    m = list(re.finditer(r"^(?:from\s+\S+\s+import\s+.*|import\s+\S+.*?)$", src, flags=re.M))
    if m:
        last_imp = m[-1].end()
        src = src[:last_imp] + "\n" + helper + src[last_imp:]
    else:
        src = helper + src

# 3) Ensure imports exist
src = ensure_imports(src)

# 4) Inject wait call inside fetch_week_html_uc after driver.get(url)
pattern = r"(def\s+fetch_week_html_uc\s*\(.*?\):)(.*?driver\.get\([^\n]+\).*)"
m = re.search(pattern, src, flags=re.S)
if not m:
    raise SystemExit("Could not find fetch_week_html_uc(...) and driver.get(...) in the target file. No changes made.")
head = src[:m.end(2)]
tail = src[m.end(2):]

injection = """
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
"""

src = head + injection + tail

# 5) Write backup and patched file
BACKUP.write_text(Path(TARGET).read_text(encoding="utf-8"), encoding="utf-8")
TARGET.write_text(src, encoding="utf-8")
print("[patched] Added times wait/scroll logic to fetch_week_html_uc()")
print("[backup]  forexfactory_pipeline.py.bak created")
