# Live Dividend Dashboard

A local, customizable dashboard that tracks, for every holding in a portfolio:

- **Next ex-dividend date** and estimated per-share amount
- **Trailing-12-month (TTM) yield** — computed live from price + dividend history
- **30-Day SEC Yield** — manual entry, or best-effort auto-fetch from an issuer URL
- **Portfolio weight** and the resulting **dividend liability** ($ expected to be
  paid out on that holding's next ex-div date)

It's built as a small local Python web app (Streamlit), not a browser-only tool,
because issuer sites and aggregators like Morningstar block the kind of
cross-origin requests a browser-based tool would need to make — your own
machine needs to do the fetching.

---

## 1. How to run it

**Requirements:** Python 3.9+ and internet access on the machine you run it on.

```bash
# 1. Unzip / place these files in a folder, then cd into it
cd dividend_dashboard

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the dashboard
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) and should
open it in your browser automatically. Leave the terminal window running —
that's your live server.

To stop it, press `Ctrl+C` in the terminal.

---

## 2. How to use / customize it

- **Edit holdings directly in the browser table** — add a row, type a ticker,
  set its weight. Or edit `portfolio.csv` in a text editor/Excel before
  launching, and it will load as the starting table.
- **Total portfolio value ($)** — set this in the sidebar; it's what turns
  "weight %" into actual position size and dividend liability dollars.
- **Look-ahead window** — the sidebar slider controls what counts as
  "upcoming" (default 30 days).
- **Manual overrides always win.** If you know the *actual* upcoming ex-div
  date/amount from the fund's official distribution schedule, or the *actual*
  30-Day SEC Yield from the fund's factsheet, type them into:
  - `next_exdiv_date_manual` (e.g. `2026-07-15`)
  - `next_div_amount_manual` (per-share $, e.g. `0.18`)
  - `sec_yield_30d_manual` (percentage, e.g. `4.27`)
  Leave them blank to fall back to the live estimate/scrape.
- **`sec_yield_source_url`** — optionally paste the URL of the fund issuer's
  own factsheet page (e.g. an iShares, Vanguard, SPDR, or Schwab fund page).
  The app will try to find "30-Day SEC Yield: X%" on that page automatically.
  This is best-effort and will silently fail on pages it can't parse — that's
  expected; just type the number in manually instead.
- **Refresh button** — live data is cached for 15 minutes per ticker so the
  dashboard doesn't hammer Yahoo Finance on every UI interaction. Click
  "🔄 Refresh live data" in the sidebar to force a re-fetch immediately.

---

## 3. Where the numbers come from (and their limits)

| Metric | Source | Notes |
|---|---|---|
| Current price | Yahoo Finance (`yfinance`) | Free, no API key. Unofficial API — can occasionally fail or change. |
| Dividend history | Yahoo Finance (`yfinance`) | Used to compute TTM yield and to estimate cadence. |
| TTM yield | Computed locally | Sum of dividends paid in the trailing 365 days ÷ current price. |
| Next ex-div date & amount | **Estimated** from historical cadence, unless overridden | Heuristic only — not an official announcement. Always prefer the fund's own published distribution schedule when available. |
| 30-Day SEC Yield | Manual entry, or best-effort scrape of an issuer URL | No free public API exists for this regulatory figure. Each fund company publishes it themselves; format varies by issuer, so scraping is fragile by nature. |

**Morningstar / paid aggregators:** this tool does **not** scrape Morningstar
or similar paid aggregator data. Doing so generally violates their Terms of
Service. If you have a Morningstar Office/Direct subscription with API/export
access, that's the appropriate way to pull their data — you could extend
`data_sources.py` to call that API in `try_scrape_sec_yield`'s place.

**Dividend liability formula:**
```
position_value      = total_portfolio_value × (weight_% / 100)
dividend_liability   = position_value × (next_dividend_per_share / current_price)
```
This is the cash expected to be distributed on that holding's next ex-div
date, scaled to your stated position size.

---

## 4. Extending it

- **Auto-refresh on a schedule:** wrap the data-fetch loop in a scheduled job
  (cron / Windows Task Scheduler) that writes results to a CSV, and have a
  second lightweight script email/Slack you a summary.
- **True "always-on" access from any device:** deploy this same code to
  [Streamlit Community Cloud](https://streamlit.io/cloud) (free tier) or your
  own server — then the "local URL" becomes a real hosted URL anyone with the
  link can open.
- **More holdings detail:** add columns for fund expense ratio, distribution
  frequency, or asset class, and corresponding columns to `portfolio.csv`.
- **Persistence:** swap `portfolio.csv` for a small SQLite database if you
  want history of how weights/estimates changed over time.

---

## 5. Files in this project

- `app.py` — the Streamlit dashboard (run this)
- `data_sources.py` — data-fetching and calculation logic
- `portfolio.csv` — sample starter holdings (edit freely)
- `requirements.txt` — Python dependencies
- `test_offline.py` — quick sanity tests for the calculation logic (no network needed): `python3 test_offline.py`
