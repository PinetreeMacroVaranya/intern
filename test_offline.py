"""Offline sanity checks -- no network calls, so this runs anywhere.
(yfinance is stubbed out here purely so this sandbox -- which has no internet
access -- can import data_sources.py and test the pure-logic functions. The
real environment where you run the dashboard should have the real yfinance
package installed via requirements.txt; nothing below tests network calls.)"""
import sys
import types

if "yfinance" not in sys.modules:
    sys.modules["yfinance"] = types.ModuleType("yfinance")

import datetime as dt
import pandas as pd
from data_sources import pick, ttm_yield, estimate_next_ex_dividend, try_scrape_sec_yield
import re

# --- pick() ---
assert pick(None, "fallback") == "fallback"
assert pick(float("nan"), "fallback") == "fallback"
assert pick("", "fallback") == "fallback"
assert pick("2026-08-01", "fallback") == "2026-08-01"
assert pick(0.25, "fallback") == 0.25  # falsy-but-valid number must NOT be replaced
print("pick() OK")

# --- ttm_yield() ---
idx = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=12, freq="30D")
divs = pd.Series([0.50] * 12, index=idx)
y = ttm_yield(divs, current_price=100.0)
# last 12 monthly-ish payments * 0.50 / 100 -> should be roughly 6 payments worth in 365 days window
assert 0 < y < 0.10, f"unexpected ttm yield: {y}"
print(f"ttm_yield() OK -> {y:.4f}")

# --- estimate_next_ex_dividend() ---
start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=10) - pd.DateOffset(months=15)
quarterly_idx = pd.date_range(start=start, periods=6, freq="QS")
quarterly_divs = pd.Series([0.45, 0.46, 0.47, 0.48, 0.49, 0.50], index=quarterly_idx)
est_date, est_amount, freq = estimate_next_ex_dividend(quarterly_divs)
assert est_date > dt.date.today(), f"estimate must be in the future, got {est_date}"
assert 80 <= freq <= 100, f"expected ~quarterly cadence, got {freq} days"
print(f"estimate_next_ex_dividend() OK -> date={est_date}, amount={est_amount:.4f}, freq={freq}d")

# --- try_scrape_sec_yield() regex logic (no real network call) ---
sample_html = "<div>Fund stats: <span>30-Day SEC Yield</span>: <b>4.27%</b> as of today</div>"
plain = re.sub(r"<[^>]+>", " ", sample_html)
plain = re.sub(r"\s+", " ", plain)
m = re.search(r"30[\s-]Day SEC Yield[^%\d]{0,40}([\d.]+)\s*%", plain, re.IGNORECASE)
assert m and abs(float(m.group(1)) - 4.27) < 1e-9
print("SEC-yield regex pattern OK -> 4.27")

print("\nAll offline checks passed.")
