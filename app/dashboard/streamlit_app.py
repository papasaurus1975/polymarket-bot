"""Streamlit dashboard — Phase 1 shows live crypto markets from Gamma API."""
import streamlit as st
from app.polymarket.markets import fetch_crypto_markets
from app.ai.market_classifier import classify_market

st.set_page_config(page_title="Polymarket Bot", layout="wide")
st.title("Polymarket Bot — Research Mode")
st.caption("Mode: RESEARCH | No trading active")

if st.button("Fetch Crypto Markets"):
    with st.spinner("Fetching from Polymarket Gamma API..."):
        markets = fetch_crypto_markets(limit=100)

    st.success(f"Found {len(markets)} crypto-related markets")

    rows = []
    for m in markets:
        mtype = classify_market(m)
        rows.append({
            "Question": m.get("question", ""),
            "Type": mtype,
            "End Date": m.get("endDate", ""),
            "Volume": m.get("volume", ""),
        })

    if rows:
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
