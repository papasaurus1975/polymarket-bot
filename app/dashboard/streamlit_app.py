"""Streamlit dashboard — Phase 2: live scanner with probability models and signals."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app.polymarket.markets import fetch_crypto_markets
from app.ai.market_classifier import classify_market
from app.polymarket.resolution import parse_resolution_source, score_resolution_match
from app.risk.limits import check_spread, check_liquidity

st.set_page_config(page_title="Polymarket Bot", layout="wide", page_icon="📊")

st.title("📊 Polymarket Bot — Research Scanner")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Mode", "RESEARCH")
col2.metric("Live Trading", "DISABLED")
col3.metric("Status", "🟢 Online")
col4.metric("Phase", "2 — Probability Engine")
st.divider()

tab1, tab2 = st.tabs(["📋 Market Scanner", "🎯 Signals"])

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    min_liquidity = st.slider("Min Liquidity ($)", 0, 50_000, 1_000, step=500)
    max_spread = st.slider("Max Spread", 0.0, 0.50, 0.10, step=0.01)
    show_types = st.multiselect("Market Types", ["A", "B", "C", "D"], default=["A", "B", "C"])
    market_limit = st.slider("Markets to fetch", 50, 500, 200, step=50)
    bankroll = st.number_input("Paper Bankroll ($)", value=1000, step=100)

# ── Tab 1: Market Scanner ──────────────────────────────────────────────────
with tab1:
    if st.button("🔍 Fetch Crypto Markets", type="primary"):
        with st.spinner("Fetching from Polymarket Gamma API..."):
            markets = fetch_crypto_markets(limit=market_limit)
        st.session_state["markets"] = markets

    if "markets" in st.session_state:
        markets = st.session_state["markets"]
        rows = []
        for m in markets:
            mtype = classify_market(m)
            parsed_res = parse_resolution_source(m.get("resolution_source", ""), m.get("description", ""))
            res_score = score_resolution_match(parsed_res)
            spread = m.get("spread")
            liquidity = m.get("liquidity", 0)
            tradable = (
                check_spread(spread) if spread else False
            ) and check_liquidity(liquidity) and mtype != "D"

            rows.append({
                "Question": m["question"],
                "Type": mtype,
                "YES": f"{m['yes_price']:.3f}" if m.get("yes_price") else "—",
                "NO": f"{m['no_price']:.3f}" if m.get("no_price") else "—",
                "Spread": f"{spread:.3f}" if spread else "—",
                "Liquidity": f"${liquidity:,.0f}",
                "Vol 24h": f"${m.get('volume_24hr', 0):,.0f}",
                "Res Source": parsed_res["resolution_source"],
                "Res Score": res_score,
                "Tradable": "✅" if tradable else "❌",
                "Expires": m.get("end_date", "")[:10],
            })

        df = pd.DataFrame(rows)
        df = df[df["Type"].isin(show_types)]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df))
        c2.metric("Tradable", (df["Tradable"] == "✅").sum())
        c3.metric("Type A", (df["Type"] == "A").sum())
        c4.metric("Type B", (df["Type"] == "B").sum())

        st.dataframe(df, use_container_width=True, hide_index=True,
            column_config={"Question": st.column_config.TextColumn(width="large")})
        st.caption(f"Refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

# ── Tab 2: Signals ─────────────────────────────────────────────────────────
with tab2:
    st.info(
        "The scanner fetches live markets, runs the lognormal (Type A) and Bayesian (Type B) "
        "probability models, calculates edge, and surfaces opportunities where "
        "|model_prob − market_price| ≥ 7%."
    )
    if st.button("🚀 Run Probability Scanner", type="primary"):
        with st.spinner("Fetching markets + running probability models..."):
            from app.scanner import scan
            signals = scan(limit=market_limit, bankroll=float(bankroll))
        st.session_state["signals"] = signals

    if "signals" in st.session_state:
        signals = st.session_state["signals"]
        if not signals:
            st.warning("No signals found above the minimum edge threshold (7%). Markets may be efficiently priced right now.")
        else:
            st.success(f"Found **{len(signals)}** signals")
            rows = []
            for s in signals:
                rows.append({
                    "ID": s.signal_id,
                    "Question": s.market_question[:80],
                    "Type": s.market_type,
                    "Side": s.recommended_side,
                    "Market Price": f"{s.polymarket_price:.3f}",
                    "Model Prob": f"{s.model_fair_probability:.3f}",
                    "Edge": f"{s.estimated_edge:+.3f}",
                    "Confidence": f"{s.confidence_score:.3f}",
                    "Res Score": f"{s.resolution_source_match_score:.1f}",
                    "Size $": f"${s.recommended_position_size:.0f}",
                    "Reason": s.reason_for_signal,
                })
            df_sig = pd.DataFrame(rows)
            st.dataframe(df_sig, use_container_width=True, hide_index=True,
                column_config={
                    "Question": st.column_config.TextColumn(width="large"),
                    "Reason": st.column_config.TextColumn(width="medium"),
                    "Edge": st.column_config.TextColumn(width="small"),
                })
            st.caption(f"All signals in RESEARCH mode — no trades executed")
