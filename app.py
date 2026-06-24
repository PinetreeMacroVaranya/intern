"""
Live Dividend Dashboard
========================
Run with:   streamlit run app.py

Tracks, for a customizable list of fund/ETF holdings:
  - upcoming / estimated ex-dividend date and per-share amount
  - trailing-12-month (TTM) yield, computed live from price + dividend history
  - 30-Day SEC Yield (manual entry, or best-effort scrape from an issuer URL)
  - each holding's portfolio weight and its resulting "dividend liability"
    (the cash that position is expected to pay out on its next ex-div date)

See README.md for setup instructions and a full explanation of data sources
and limitations.
"""

import datetime as dt
import pandas as pd
import streamlit as st

from data_sources import (
    pick,
    fetch_price_and_dividends,
    ttm_yield,
    estimate_next_ex_dividend,
    try_scrape_sec_yield,
)

st.set_page_config(page_title="Dividend Dashboard", layout="wide")
st.title("📈 Live Dividend Dashboard")

# ---------------------------------------------------------------- sidebar ---
st.sidebar.header("Portfolio settings")
total_aum = st.sidebar.number_input(
    "Total portfolio value ($)", min_value=0.0, value=1_000_000.0, step=10_000.0, format="%.2f"
)
horizon_days = st.sidebar.slider("Look-ahead window (days) for 'upcoming'", 7, 120, 30)

if st.sidebar.button("🔄 Refresh live data"):
    st.cache_data.clear()

st.sidebar.caption(
    "**Price & dividend history:** Yahoo Finance (yfinance).\n\n"
    "**30-Day SEC Yield:** manual entry, or best-effort scrape of an issuer "
    "factsheet URL you provide.\n\n"
    "**Ex-dividend dates:** estimated from each holding's own payment cadence "
    "unless you type in the real date."
)

# ---------------------------------------------------------- holdings table ---
DEFAULT_PATH = "portfolio.csv"
COLUMNS = [
    "ticker", "name", "weight_pct", "sec_yield_30d_manual",
    "sec_yield_source_url", "next_exdiv_date_manual", "next_div_amount_manual",
]

if "holdings" not in st.session_state:
    try:
        st.session_state.holdings = pd.read_csv(DEFAULT_PATH)
    except FileNotFoundError:
        st.session_state.holdings = pd.DataFrame(columns=COLUMNS)

st.subheader("Holdings (editable)")
st.caption(
    "Add or remove rows, edit weights, or paste in an official ex-div date / "
    "amount / 30-day SEC yield whenever you have one — manual values always "
    "override the live estimate."
)
edited = st.data_editor(
    st.session_state.holdings, num_rows="dynamic", use_container_width=True, key="editor"
)
st.session_state.holdings = edited

if not edited.empty:
    weight_sum = pd.to_numeric(edited["weight_pct"], errors="coerce").fillna(0).sum()
    if weight_sum > 0 and abs(weight_sum - 100) > 0.5:
        st.warning(f"Weights sum to {weight_sum:.1f}%, not 100% — dollar figures will scale accordingly.")

# ------------------------------------------------------------- live fetch ---
@st.cache_data(ttl=900, show_spinner=False)
def load_live_row(ticker: str):
    price, divs = fetch_price_and_dividends(ticker)
    ttm = ttm_yield(divs, price)
    est_date, est_amount, freq_days = estimate_next_ex_dividend(divs)
    return price, ttm, est_date, est_amount, freq_days


rows, errors = [], []

if not edited.empty:
    clean = edited.reset_index(drop=True)
    n = len(clean)
    progress = st.progress(0.0, text="Fetching live data...")

    for i, r in clean.iterrows():
        ticker = str(r.get("ticker") or "").strip().upper()
        if not ticker:
            progress.progress((i + 1) / n)
            continue

        try:
            price, ttm, est_date, est_amount, freq_days = load_live_row(ticker)
        except Exception as e:
            errors.append(f"{ticker}: {e}")
            price, ttm, est_date, est_amount, freq_days = None, None, None, None, None

        next_date = pick(r.get("next_exdiv_date_manual"), est_date)
        next_amount = pick(r.get("next_div_amount_manual"), est_amount)
        try:
            next_amount = float(next_amount) if next_amount is not None else None
        except (TypeError, ValueError):
            next_amount = None

        sec_yield = pick(r.get("sec_yield_30d_manual"), None)
        if sec_yield is None:
            url = pick(r.get("sec_yield_source_url"), None)
            if url:
                sec_yield = try_scrape_sec_yield(url)
        try:
            sec_yield = float(sec_yield) if sec_yield is not None else None
        except (TypeError, ValueError):
            sec_yield = None

        weight_raw = pick(r.get("weight_pct"), 0)
        try:
            weight = float(weight_raw)
        except (TypeError, ValueError):
            weight = 0.0

        position_value = total_aum * weight / 100.0
        liability = (
            position_value * (next_amount / price)
            if next_amount and price
            else None
        )

        days_to_exdiv = None
        if next_date:
            try:
                days_to_exdiv = (pd.to_datetime(next_date).date() - dt.date.today()).days
            except Exception:
                pass

        rows.append({
            "Ticker": ticker,
            "Name": r.get("name"),
            "Price": price,
            "Weight %": weight,
            "Position $": position_value,
            "Next Ex-Div Date": next_date,
            "Days to Ex-Div": days_to_exdiv,
            "Est. Div/Share": next_amount,
            "Dividend Liability $": liability,
            "TTM Yield %": (ttm * 100) if ttm is not None else None,
            "30-Day SEC Yield %": sec_yield,
        })
        progress.progress((i + 1) / n, text=f"Fetching live data... {ticker}")
    progress.empty()

if errors:
    st.error("Some tickers failed to fetch:\n" + "\n".join(errors))

# ------------------------------------------------------------------ output ---
if rows:
    result = pd.DataFrame(rows).sort_values(by="Days to Ex-Div", na_position="last")

    st.subheader("Live summary")
    upcoming_mask = result["Days to Ex-Div"].fillna(99999).between(0, horizon_days)
    upcoming = result[upcoming_mask]

    c1, c2, c3 = st.columns(3)
    c1.metric("Holdings tracked", len(result))
    c2.metric(f"Going ex-div within {horizon_days}d", len(upcoming))
    c3.metric(
        f"Total liability due within {horizon_days}d",
        f"${upcoming['Dividend Liability $'].fillna(0).sum():,.0f}",
    )

    st.dataframe(
        result.style.format(
            {
                "Price": "${:,.2f}",
                "Position $": "${:,.0f}",
                "Est. Div/Share": "${:,.4f}",
                "Dividend Liability $": "${:,.0f}",
                "TTM Yield %": "{:.2f}%",
                "30-Day SEC Yield %": "{:.2f}%",
            },
            na_rep="—",
        ),
        use_container_width=True,
        height=420,
    )

    st.subheader(f"Dividend liability due in the next {horizon_days} days")
    if upcoming.empty:
        st.info("No holdings are currently expected to go ex-dividend in this window.")
    else:
        st.bar_chart(upcoming.set_index("Ticker")["Dividend Liability $"])
else:
    st.info("Add at least one ticker in the holdings table above to see live data.")
