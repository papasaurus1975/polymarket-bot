"""Streamlit dashboard — Phase 1: live crypto market scanner."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app.polymarket.markets import fetch_crypto_markets
from app.ai.market_classifier import classify_market
from app.polymarket.resolution import parse_resolution_source, score_resolution_match
from app.risk.limits import check_spread, check_liquidity

st.set_page_config(page_title="Polymarket Bot", layout="wide", page_icon="📊")

st.title("📊 Polymarket Bot — Research Scanner")
col1, col2, col3 = st.columns(3)
col1.metric("Mode", "RESEARCH")
col2.metric("Live Trading", "DISABLED")
col3.metric("Status", "🟢 Online")

st.divider()

with st.sidebar:
    st.header("Filters")
    min_liquidity = st.slider("Min Liquidity ($)", 0, 50000, 1000, step=500)
    max_spread = st.slider("Max Spread", 0.0, 0.50, 0.10, step=0.01)
    show_types = st.multiselect("Market Types", ["A", "B", "C", "D"], default=["A", "B", "C"])
    limit = st.slider("Markets to fetch", 50, 500, 200, step=50)

if st.button("🔍 Fetch Crypto Markets", type="primary"):
    with st.spinner("Connecting to Polymarket Gamma API..."):
        markets = fetch_crypto_markets(limit=limit)

    st.success(f"Found **{len(markets)}** crypto markets")

    rows = []
    for m in markets:
        mtype = classify_market(m)
        parsed_res = parse_resolution_source(m.get("resolution_source", ""), m.get("description", ""))
        res_score = score_resolution_match(parsed_res)

        spread = m.get("spread")
        liquidity = m.get("liquidity", 0)
        spread_ok = check_spread(spread) if spread else False
        liquidity_ok = check_liquidity(liquidity)
        tradable = spread_ok and liquidity_ok and mtype != "D"

        rows.append({
            "Question": m["question"],
            "Type": mtype,
            "YES Price": f"{m['yes_price']:.2f}" if m.get("yes_price") else "—",
            "NO Price": f"{m['no_price']:.2f}" if m.get("no_price") else "—",
            "Spread": f"{spread:.3f}" if spread else "—",
            "Liquidity $": f"{liquidity:,.0f}",
            "Volume 24h $": f"{m.get('volume_24hr', 0):,.0f}",
            "Resolution Source": parsed_res["resolution_source"],
            "Res Match": f"{res_score:.1f}",
            "Tradable": "✅" if tradable else "❌",
            "Expires": m.get("end_date", "")[:10],
        })

    df = pd.DataFrame(rows)

    # Apply sidebar filters
    df = df[df["Type"].isin(show_types)]

    # Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    c2.metric("Tradable", df["Tradable"].value_counts().get("✅", 0))
    c3.metric("Type A (price)", (df["Type"] == "A").sum())
    c4.metric("Type B (regulatory)", (df["Type"] == "B").sum())

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Question": st.column_config.TextColumn(width="large"),
            "Tradable": st.column_config.TextColumn(width="small"),
        }
    )

    st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
