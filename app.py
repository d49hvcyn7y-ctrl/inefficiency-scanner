import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False

st.set_page_config(page_title="Market Inefficiency Scanner", page_icon="📊", layout="wide")

# -------------------- Crypto --------------------
CRYPTO_ASSETS = {
    "BTC": {
        "coinbase": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
        "kraken": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
        "bitstamp": "https://www.bitstamp.net/api/v2/ticker/btcusd/",
    },
    "ETH": {
        "coinbase": "https://api.coinbase.com/v2/prices/ETH-USD/spot",
        "kraken": "https://api.kraken.com/0/public/Ticker?pair=ETHUSD",
        "bitstamp": "https://www.bitstamp.net/api/v2/ticker/ethusd/",
    },
    "SOL": {
        "coinbase": "https://api.coinbase.com/v2/prices/SOL-USD/spot",
        "kraken": "https://api.kraken.com/0/public/Ticker?pair=SOLUSD",
        "bitstamp": "https://www.bitstamp.net/api/v2/ticker/solusd/",
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_price_coinbase(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        return float(r.json()["data"]["amount"]) if r.status_code == 200 else None
    except:
        return None

def get_price_kraken(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        data = r.json()
        if not data.get("error"):
            for v in data["result"].values():
                return float(v["c"][0])
    except:
        return None

def get_price_bitstamp(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        return float(r.json()["last"]) if r.status_code == 200 else None
    except:
        return None

def scan_crypto(threshold=0.2):
    results = []
    for asset, urls in CRYPTO_ASSETS.items():
        prices = {
            "Coinbase": get_price_coinbase(urls["coinbase"]),
            "Kraken": get_price_kraken(urls["kraken"]),
            "Bitstamp": get_price_bitstamp(urls["bitstamp"]),
        }
        valid = {k: v for k, v in prices.items() if v}
        if len(valid) < 2:
            continue
        exchanges = list(valid.keys())
        for i in range(len(exchanges)):
            for j in range(i+1, len(exchanges)):
                a, b = exchanges[i], exchanges[j]
                pa, pb = valid[a], valid[b]
                spread = abs(pa - pb) / ((pa + pb)/2) * 100
                results.append({
                    "Asset": asset,
                    "Pair": f"{a} vs {b}",
                    "Price A": round(pa, 2),
                    "Price B": round(pb, 2),
                    "Spread %": round(spread, 3),
                    "Higher": a if pa > pb else b,
                    "Flag": "✅" if spread >= threshold else "—"
                })
        time.sleep(0.4)
    return pd.DataFrame(results)

# -------------------- Stocks (improved) --------------------
TOP_STOCKS = [
    "NVDA","AAPL","MSFT","GOOGL","AMZN","META","AVGO","TSLA","ORCL","AMD",
    "ADBE","CRM","CSCO","INTC","QCOM","LLY","UNH","JNJ","ABBV","MRK",
    "BRK-B","JPM","V","MA","BAC","WFC","WMT","COST","HD","MCD",
    "XOM","CVX","CAT","GE","HON","DIS","NFLX","NEE","BA","AMD"
]

@st.cache_data(ttl=300, show_spinner=False)  # cache for 5 minutes
def scan_stocks(max_tickers=20):
    if not YF_AVAILABLE:
        return pd.DataFrame(), "yfinance not available"

    tickers = TOP_STOCKS[:max_tickers]
    rows = []
    errors = 0

    # Very small batches + longer pauses = more reliable
    batch_size = 4
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        try:
            data = yf.download(
                batch,
                period="6mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=False,
                progress=False,
            )
            time.sleep(1.5)  # important pause
        except Exception:
            errors += 1
            time.sleep(2)
            continue

        is_multi = isinstance(data.columns, pd.MultiIndex)

        for t in batch:
            try:
                if is_multi:
                    if t not in data.columns.get_level_values(0):
                        continue
                    close = data[t]["Close"].dropna()
                else:
                    close = data["Close"].dropna()

                if len(close) < 50:
                    continue

                last = float(close.iloc[-1])
                ma50 = float(close.tail(50).mean())
                ma200 = float(close.tail(min(200, len(close))).mean())
                pct50 = (last / ma50 - 1) * 100
                pct200 = (last / ma200 - 1) * 100
                stretch = pct50 * 0.6 + pct200 * 0.4

                rows.append({
                    "Ticker": t,
                    "Last": round(last, 2),
                    "% vs 50DMA": round(pct50, 2),
                    "% vs 200DMA": round(pct200, 2),
                    "Stretch Score": round(stretch, 2)
                })
            except:
                continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df, "No data returned (rate limited). Try fewer stocks or wait a minute."
    return df.sort_values("Stretch Score", ascending=False).reset_index(drop=True), None

# -------------------- UI --------------------
st.title("📊 Market Inefficiency Scanner")
st.caption("Works on iPhone • Click Scan for fresh results")

mode = st.radio("Choose scan type", [
    "Crypto Cross-Exchange Spreads",
    "Top Stocks Technical Screen",
    "Relative Value Calculator"
])

threshold = st.slider("Crypto min spread % to flag", 0.05, 1.0, 0.20, 0.05)
stock_limit = st.slider("How many stocks to scan (keep low for reliability)", 8, 30, 15)

if st.button("🔄 Scan for Inefficiencies", type="primary"):
    if mode == "Crypto Cross-Exchange Spreads":
        with st.spinner("Checking live crypto prices..."):
            df = scan_crypto(threshold)
            if df.empty:
                st.warning("Could not get crypto prices right now. Try again.")
            else:
                st.dataframe(df, use_container_width=True)
                good = df[df["Flag"] == "✅"]
                if not good.empty:
                    st.success(f"Found {len(good)} interesting spread(s)")
                else:
                    st.info("No big spreads at the moment")

    elif mode == "Top Stocks Technical Screen":
        with st.spinner(f"Scanning {stock_limit} stocks (small batches for reliability)..."):
            df, error_msg = scan_stocks(stock_limit)
            if error_msg:
                st.warning(error_msg)
            elif df.empty:
                st.warning("No stock data returned. Try lowering the number or wait 1 minute.")
            else:
                st.success(f"Successfully scanned {len(df)} stocks")
                st.dataframe(df, use_container_width=True)

                oversold = df[df["% vs 200DMA"] < -12]
                if not oversold.empty:
                    st.subheader("Possible mean-reversion candidates (below 200DMA)")
                    st.dataframe(oversold, use_container_width=True)

    elif mode == "Relative Value Calculator":
        st.info("Use the inputs below")

if mode == "Relative Value Calculator":
    price = st.number_input("Current price $", value=100.0)
    fair = st.number_input("Your fair value $", value=120.0)
    if st.button("Calculate Gap"):
        gap = ((fair - price) / price) * 100
        if gap > 5:
            st.success(f"Looks undervalued by about {gap:.1f}%")
        elif gap < -5:
            st.error(f"Looks overvalued by about {abs(gap):.1f}%")
        else:
            st.info(f"Roughly fair ({gap:+.1f}%)")

st.markdown("---")
st.caption("Educational tool only. Not financial advice. Stock data can be rate-limited on free servers.")
