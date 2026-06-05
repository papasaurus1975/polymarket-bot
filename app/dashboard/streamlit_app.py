"""Streamlit dashboard — Phase 3: market scanner, signals, paper trading, performance."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app.polymarket.markets import fetch_crypto_markets
from app.ai.market_classifier import classify_market
from app.polymarket.resolution import parse_resolution_source, score_resolution_match
from app.risk.limits import check_spread, check_liquidity
from app.database import init_db

init_db()

st.set_page_config(page_title="Polymarket Bot", layout="wide", page_icon="📊")
st.title("📊 Polymarket Bot — Research Mode")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Mode", "RESEARCH")
c2.metric("Live Trading", "DISABLED")
c3.metric("Status", "🟢 Online")
c4.metric("Phase", "3 — Paper Trading")
st.divider()

tab1, tab2, tab3 = st.tabs(["📋 Markets", "🎯 Signals", "📈 Paper Trading"])

with st.sidebar:
    st.header("Settings")
    min_liquidity = st.slider("Min Liquidity ($)", 0, 50_000, 1_000, step=500)
    max_spread_val = st.slider("Max Spread", 0.0, 0.50, 0.10, step=0.01)
    show_types = st.multiselect("Market Types", ["A", "B", "C", "D"], default=["A", "B", "C"])
    market_limit = st.slider("Markets to fetch", 50, 500, 200, step=50)
    bankroll = st.number_input("Paper Bankroll ($)", value=1000, step=100)

# ── Tab 1: Markets ─────────────────────────────────────────────────────────
with tab1:
    if st.button("🔍 Fetch Markets", type="primary"):
        with st.spinner("Fetching from Polymarket..."):
            st.session_state["markets"] = fetch_crypto_markets(limit=market_limit)

    if "markets" in st.session_state:
        markets = st.session_state["markets"]
        rows = []
        for m in markets:
            mtype = classify_market(m)
            res = parse_resolution_source(m.get("resolution_source", ""), m.get("description", ""))
            res_score = score_resolution_match(res)
            spread = m.get("spread")
            liq = m.get("liquidity", 0)
            tradable = (check_spread(spread) if spread else False) and check_liquidity(liq) and mtype != "D"
            rows.append({
                "Question": m["question"], "Type": mtype,
                "YES": f"{m['yes_price']:.3f}" if m.get("yes_price") else "—",
                "Spread": f"{spread:.3f}" if spread else "—",
                "Liquidity": f"${liq:,.0f}",
                "Vol 24h": f"${m.get('volume_24hr', 0):,.0f}",
                "Res Source": res["resolution_source"],
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

# ── Tab 2: Signals ─────────────────────────────────────────────────────────
with tab2:
    if st.button("🚀 Run Probability Scanner", type="primary"):
        with st.spinner("Running probability models..."):
            from app.scanner import scan
            st.session_state["signals"] = scan(limit=market_limit, bankroll=float(bankroll))

    if "signals" in st.session_state:
        signals = st.session_state["signals"]
        if not signals:
            st.warning("No signals above 7% edge threshold right now.")
        else:
            st.success(f"**{len(signals)}** signals found")
            rows = []
            for s in signals:
                rows.append({
                    "ID": s.signal_id, "Question": s.market_question[:80],
                    "Type": s.market_type, "Side": s.recommended_side,
                    "Mkt Price": f"{s.polymarket_price:.3f}",
                    "Model": f"{s.model_fair_probability:.3f}",
                    "Edge": f"{s.estimated_edge:+.3f}",
                    "Conf": f"{s.confidence_score:.3f}",
                    "Size $": f"${s.recommended_position_size:.0f}",
                    "Reason": s.reason_for_signal,
                })
            df_sig = pd.DataFrame(rows)
            st.dataframe(df_sig, use_container_width=True, hide_index=True,
                column_config={"Question": st.column_config.TextColumn(width="large"),
                               "Reason": st.column_config.TextColumn(width="medium")})

            st.divider()
            st.subheader("Enter Paper Trade")
            sig_ids = [s.signal_id for s in signals]
            selected_id = st.selectbox("Select signal", sig_ids,
                format_func=lambda sid: next(
                    f"[{s.market_type}] {s.recommended_side} {s.market_question[:60]}"
                    for s in signals if s.signal_id == sid))
            if st.button("📝 Enter Paper Trade"):
                from app.trading.paper_trader import enter_trade
                selected = next(s for s in signals if s.signal_id == selected_id)
                selected.mode = "paper"
                trade = enter_trade(selected)
                if trade:
                    st.success(f"Trade entered: {trade['trade_id']} | {trade['side']} @ {trade['entry_price']:.3f} | size=${trade['size']:.2f}")
                else:
                    st.error("Trade entry failed")

# ── Tab 3: Paper Trading ────────────────────────────────────────────────────
with tab3:
    from app.trading.paper_trader import get_all_trades, close_trade
    from app.trading.performance import compute_metrics

    col_refresh, col_close = st.columns([1, 3])
    refresh = col_refresh.button("🔄 Refresh")

    all_trades = get_all_trades()
    metrics = compute_metrics(all_trades)

    # Summary metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Trades", metrics["total_trades"])
    m2.metric("Open", metrics["open_trades"])
    m3.metric("Total P&L", f"${metrics['total_pnl']:.2f}")
    m4.metric("Win Rate", f"{metrics['win_rate']:.0%}" if metrics["total_trades"] else "—")
    m5.metric("Brier Score", f"{metrics['brier_score']:.3f}" if metrics["brier_score"] else "—")

    st.divider()

    # Open trades
    open_trades = [t for t in all_trades if t.status == "OPEN"]
    if open_trades:
        st.subheader(f"Open Trades ({len(open_trades)})")
        open_rows = []
        for t in open_trades:
            open_rows.append({
                "ID": t.trade_id, "Question": t.market_question[:70],
                "Side": t.side, "Entry": f"{t.entry_price:.3f}",
                "Size $": f"${t.size:.2f}",
                "Edge": f"{t.edge_at_entry:+.3f}",
                "Model Prob": f"{t.model_probability_at_entry:.3f}",
                "Entered": str(t.entry_time)[:16],
            })
        st.dataframe(pd.DataFrame(open_rows), use_container_width=True, hide_index=True,
            column_config={"Question": st.column_config.TextColumn(width="large")})

        with st.expander("Close a trade"):
            trade_ids = [t.trade_id for t in open_trades]
            tid = st.selectbox("Trade ID", trade_ids)
            exit_p = st.slider("Exit Price", 0.01, 0.99, 0.50, step=0.01)
            outcome = st.selectbox("Final Outcome (optional)", ["", "YES", "NO"])
            reason = st.selectbox("Exit Reason",
                ["edge_closed", "profit_target", "stop_loss", "expiration", "manual"])
            if st.button("Close Trade"):
                result = close_trade(tid, exit_p, reason, final_outcome=outcome or None)
                if result:
                    st.success(f"Closed {tid} | P&L: ${result['profit_loss']:.2f}")

    # Closed trades
    closed_trades = [t for t in all_trades if t.status == "CLOSED"]
    if closed_trades:
        st.subheader(f"Closed Trades ({len(closed_trades)})")
        closed_rows = []
        for t in closed_trades:
            closed_rows.append({
                "ID": t.trade_id, "Question": t.market_question[:60],
                "Side": t.side,
                "Entry": f"{t.entry_price:.3f}",
                "Exit": f"{t.exit_price:.3f}" if t.exit_price else "—",
                "P&L $": f"${t.profit_loss:.2f}" if t.profit_loss is not None else "—",
                "Outcome": t.final_outcome or "—",
                "Model ✓": "✅" if t.model_accuracy else ("❌" if t.model_accuracy is False else "—"),
                "Cal Err": f"{t.calibration_error:.3f}" if t.calibration_error else "—",
            })
        st.dataframe(pd.DataFrame(closed_rows), use_container_width=True, hide_index=True,
            column_config={"Question": st.column_config.TextColumn(width="large")})

    if not open_trades and not closed_trades:
        st.info("No trades yet. Run the scanner and enter a paper trade from the Signals tab.")

    st.caption(f"Refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
