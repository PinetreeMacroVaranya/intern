"""
data_sources.py
----------------
Helper functions for fetching dividend, price, and yield data for the dashboard.

DATA SOURCES
- Price + dividend history + TTM yield: Yahoo Finance, via the `yfinance` package.
  Free, no API key required. This is an unofficial API that Yahoo can change
  without notice, so treat it as "usually reliable, occasionally flaky."
- Next ex-dividend date / amount: ESTIMATED from each holding's own historical
  payment cadence (median days between recent ex-div dates). This is a heuristic,
  not an official announcement. Funds publish their real upcoming distribution
  schedule on their own site (e.g. an iShares/Vanguard/SPDR product page) --
  whenever you know the real date/amount, type it into the "manual" columns in
  the dashboard table and it will override the estimate automatically.
- 30-Day SEC Yield: there is no free public API for this figure (it's a
  regulatory number each fund calculates itself). Two options are provided:
    1) Manual entry (recommended - fastest and always correct).
    2) Best-effort scraping of a fund issuer's own public factsheet page, if you
       paste its URL into the "sec_yield_source_url" column. This uses a simple
       regex over the page text and WILL break on some issuers since every fund
       company formats their page differently.
  Scraping Morningstar (or other paid aggregators) is deliberately NOT included
  here -- doing so generally violates their Terms of Service. Use Morningstar's
  own export/API tools, or just type the number in manually.
"""

import re
import statistics
import requests
import pandas as pd
import yfinance as yf

HEADERS = {"User-Agent": "Mozilla/5.0 (dividend-dashboard/1.0; personal use)"}


def pick(manual, fallback):
    """Return `manual` unless it's missing/blank (None, NaN, or empty string)."""
    if manual is None:
        return fallback
    if isinstance(manual, float) and pd.isna(manual):
        return fallback
    if isinstance(manual, str) and manual.strip() == "":
        return fallback
    return manual


def fetch_price_and_dividends(ticker: str):
    """Return (current_price, dividend_series) for a ticker using yfinance."""
    tk = yf.Ticker(ticker)
    hist = tk.history(period="2y", auto_adjust=False)
    if hist.empty:
        raise ValueError(f"No price history returned for '{ticker}' (check the symbol).")
    current_price = float(hist["Close"].iloc[-1])
    divs = tk.dividends  # pandas Series: index = ex-div date (tz-aware), values = $/share
    return current_price, divs


def ttm_yield(divs: pd.Series, current_price: float) -> float:
    """Trailing-12-month yield = sum of dividends paid in the last 365 days / current price."""
    if divs is None or divs.empty or not current_price or current_price <= 0:
        return 0.0
    cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
    last_12mo = divs[divs.index >= cutoff]
    return float(last_12mo.sum() / current_price)


def estimate_next_ex_dividend(divs: pd.Series):
    """
    Estimate the next ex-dividend date and per-share amount from historical cadence.
    Returns (estimated_date: date|None, estimated_amount: float|None, frequency_days: int|None).
    This is a heuristic -- override with real data in the dashboard whenever you have it.
    """
    if divs is None or len(divs) < 2:
        return None, None, None

    recent = divs.iloc[-8:]  # up to the last 8 payments
    dates = list(recent.index)
    amounts = list(recent.values)
    diffs = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    if not diffs:
        return None, None, None

    freq_days = max(int(statistics.median(diffs)), 1)
    last_date = dates[-1]
    today = pd.Timestamp.now(tz=last_date.tz)

    est_date = last_date
    guard = 0
    while est_date <= today and guard < 50:
        est_date = est_date + pd.Timedelta(days=freq_days)
        guard += 1

    tail = amounts[-4:] if len(amounts) >= 4 else amounts
    est_amount = float(statistics.mean(tail))
    return est_date.date(), est_amount, freq_days


def try_scrape_sec_yield(url: str):
    """
    Best-effort attempt to find a '30-Day SEC Yield' percentage on a fund
    issuer's public factsheet page. Returns a float percentage (e.g. 4.32) or
    None if it can't be found. Always treat the result as unverified.
    """
    if not url:
        return None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    plain = re.sub(r"<[^>]+>", " ", resp.text)
    plain = re.sub(r"\s+", " ", plain)

    patterns = [
        r"30[\s-]Day SEC Yield[^%\d]{0,40}([\d.]+)\s*%",
        r"SEC 30[\s-]Day Yield[^%\d]{0,40}([\d.]+)\s*%",
        r"SEC Yield \(30[\s-]Day\)[^%\d]{0,40}([\d.]+)\s*%",
        r"30-day SEC yield[^%\d]{0,40}([\d.]+)\s*%",
    ]
    for pat in patterns:
        m = re.search(pat, plain, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None
