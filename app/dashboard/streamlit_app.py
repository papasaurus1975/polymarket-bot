"""Streamlit dashboard — Phase 5: markets, signals, paper trading, approvals, wallet."""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app.database import init_db
from app.config import settings

init_db()

st.set_page_config(page_title="Polymarket Bot", layout="wide", page_icon="📊")
st.title("📊 Polymarket Bot")

mode_color = {"research": "🔵", "paper": "🟡", "semi_auto": "🟠", "live": "🔴"}
c1, c2, c3, c4 = st.columns(4)
c1.metric("Mode", f"{mode_color.get(settings.app_mode, '⚪')} {settings.app_mode.upper()}")
c2.metric("Live Trading", "✅ ENABLED" if settings.live_trading_enabled else "❌ DISABLED")
c3.metric("Compliance", "✅" if settings.compliance_approved else "❌ NOT APPROVED")
c4.metric("Phase", "5 — Semi-Auto")
st.divider()

tabs = st.tabs(["📋 Markets", "🎯 Signals", "📈 Paper Trading",
                "✅ Approval Queue", "💼 Wallet", "🔴 Live Execution"])

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    market_limit = st.slider("Markets to fetch", 50, 500, 200, step=50)
    bankroll = st.number_input("Bankroll ($)", value=1000, step=100)
    st.divider()
    st.subheader("Kill Switches")
    from app.risk.kill_switch import _switches, activate, reset, any_active
    for sw, active in _switches.items():
        col_l, col_r = st.columns([3, 1])
        col_l.write(f"{'🔴' if active else '🟢'} {sw}")
        if active:
            if col_r.button("Reset", key=f"reset_{sw}"):
                reset(sw, confirmed_by="dashboard_user")
                st.rerun()
        else:
            if col_r.button("Trip", key=f"trip_{sw}"):
                activate(sw, reason="manual dashboard trigger")
                st.rerun()

# ── Tab 1: Markets ───────────────────────────────────────────────────────────
with tabs[0]:
    from app.polymarket.markets import fetch_crypto_markets
    from app.ai.market_classifier import classify_market
    from app.polymarket.resolution import parse_resolution_source, score_resolution_match
    from app.risk.limits import check_spread, check_liquidity

    if st.button("🔍 Fetch Markets", type="primary"):
        with st.spinner("Fetching from Polymarket..."):
            st.session_state["markets"] = fetch_crypto_markets(limit=market_limit)

    if "markets" in st.session_state:
        markets = st.session_state["markets"]
        rows = []
        for m in markets:
            mtype = classify_market(m)
            res = parse_resolution_source(m.get("resolution_source",""), m.get("description",""))
            spread = m.get("spread")
            liq = m.get("liquidity", 0)
            tradable = (check_spread(spread) if spread else False) and check_liquidity(liq) and mtype != "D"
            rows.append({
                "Question": m["question"], "Type": mtype,
                "YES": f"{m['yes_price']:.3f}" if m.get("yes_price") else "—",
                "Spread": f"{spread:.3f}" if spread else "—",
                "Liquidity": f"${liq:,.0f}",
                "Tradable": "✅" if tradable else "❌",
                "Expires": m.get("end_date","")[:10],
            })
        df = pd.DataFrame(rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total", len(df))
        c2.metric("Tradable", (df["Tradable"]=="✅").sum())
        c3.metric("Type A", (df["Type"]=="A").sum())
        st.dataframe(df, use_container_width=True, hide_index=True,
            column_config={"Question": st.column_config.TextColumn(width="large")})

# ── Tab 2: Signals ───────────────────────────────────────────────────────────
with tabs[1]:
    if any_active():
        st.error("🔴 Kill switch active — scanner blocked")
    else:
        if st.button("🚀 Run Scanner", type="primary"):
            with st.spinner("Fetching markets + running models + news..."):
                from app.scanner import scan
                st.session_state["signals"] = scan(limit=market_limit, bankroll=float(bankroll))

    if "signals" in st.session_state:
        signals = st.session_state["signals"]
        if not signals:
            st.warning("No signals above 7% edge threshold.")
        else:
            st.success(f"**{len(signals)}** signals")
            rows = []
            for s in signals:
                rows.append({
                    "ID": s.signal_id, "Question": s.market_question[:80],
                    "Type": s.market_type, "Side": s.recommended_side,
                    "Mkt": f"{s.polymarket_price:.3f}",
                    "Model": f"{s.model_fair_probability:.3f}",
                    "Edge": f"{s.estimated_edge:+.3f}",
                    "CI": f"[{s.model_confidence_interval[0]:.2f}, {s.model_confidence_interval[1]:.2f}]",
                    "Conf": f"{s.confidence_score:.3f}",
                    "Size $": f"${s.recommended_position_size:.0f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                column_config={"Question": st.column_config.TextColumn(width="large")})

            st.divider()
            st.subheader("Route Signal")
            sig_ids = [s.signal_id for s in signals]
            sel_id = st.selectbox("Select signal", sig_ids,
                format_func=lambda sid: next(
                    f"[{s.market_type}] {s.recommended_side} {s.market_question[:55]}"
                    for s in signals if s.signal_id == sid))
            sel_sig = next(s for s in signals if s.signal_id == sel_id)

            # Order preview — compute Kelly once and cache in session state
            from app.risk.position_sizing import kelly_size
            kelly_key = f"kelly_{sel_id}"
            if kelly_key not in st.session_state:
                st.session_state[kelly_key] = kelly_size(sel_sig.estimated_edge, float(bankroll))
            kelly = st.session_state[kelly_key]

            with st.expander("📋 Order Preview", expanded=True):
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Side", sel_sig.recommended_side)
                p2.metric("Entry Price", f"{sel_sig.polymarket_price:.3f}")
                p3.metric("Size", f"${kelly['recommended_size_usd']:.2f}")
                p4.metric("Edge", f"{sel_sig.estimated_edge:+.1%}")
                st.info(f"**Kelly derivation:** {kelly['derivation']}")
                st.write(f"**Rationale:** {sel_sig.reason_for_signal[:300]}")
                if sel_sig.news_items_cited:
                    st.write("**News cited:**")
                    for n in sel_sig.news_items_cited[:3]:
                        st.write(f"  - {n[:80]}")
                if sel_sig.event_calendar_events_cited:
                    st.write("**Events cited:**")
                    for e in sel_sig.event_calendar_events_cited[:2]:
                        st.write(f"  - {e}")

            col_paper, col_approve = st.columns(2)
            if col_paper.button("📝 Paper Trade Now"):
                from app.trading.paper_trader import enter_trade
                sel_sig.mode = "paper"
                trade = enter_trade(sel_sig)
                if trade:
                    st.success(f"Paper trade entered: {trade['trade_id']} | {trade['side']} @ {trade['entry_price']:.3f}")

            if col_approve.button("📬 Submit for Approval"):
                from app.trading.approval_queue import submit_for_approval
                req = submit_for_approval(sel_sig, kelly)
                st.success(f"Submitted for approval: **{req['request_id']}**")

# ── Tab 3: Paper Trading ─────────────────────────────────────────────────────
with tabs[2]:
    from app.trading.paper_trader import get_all_trades, close_trade
    from app.trading.performance import compute_metrics
    from app.ai.adaptive_model import recommend_updates

    all_trades = get_all_trades()
    metrics = compute_metrics(all_trades)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Trades", metrics["total_trades"])
    m2.metric("Open", metrics["open_trades"])
    m3.metric("Total P&L", f"${metrics['total_pnl']:.2f}")
    m4.metric("Win Rate", f"{metrics['win_rate']:.0%}" if metrics["total_trades"] else "—")
    m5.metric("Brier Score", f"{metrics['brier_score']:.3f}" if metrics["brier_score"] else "—")

    st.divider()
    open_trades = [t for t in all_trades if t["status"] == "OPEN"]
    closed_trades = [t for t in all_trades if t["status"] == "CLOSED"]

    if open_trades:
        st.subheader(f"Open ({len(open_trades)})")
        rows = [{"ID": t["trade_id"], "Question": (t["market_question"] or "")[:65],
                 "Side": t["side"], "Entry": f"{t['entry_price']:.3f}",
                 "Size": f"${t['size']:.2f}", "Edge": f"{t['edge_at_entry']:+.3f}",
                 "Entered": str(t["entry_time"])[:16]} for t in open_trades]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Close a trade"):
            tid = st.selectbox("Trade", [t["trade_id"] for t in open_trades])
            exit_p = st.slider("Exit Price", 0.01, 0.99, 0.50, step=0.01)
            outcome = st.selectbox("Outcome", ["", "YES", "NO"])
            reason = st.selectbox("Reason", ["edge_closed","profit_target","stop_loss","expiration","manual"])
            if st.button("Close Trade"):
                r = close_trade(tid, exit_p, reason, final_outcome=outcome or None)
                if r:
                    st.success(f"Closed {tid} | P&L: ${r['profit_loss']:.2f}")
                    st.rerun()

    if closed_trades:
        st.subheader(f"Closed ({len(closed_trades)})")
        rows = [{"ID": t["trade_id"], "Q": (t["market_question"] or "")[:55],
                 "Side": t["side"],
                 "P&L": f"${t['profit_loss']:.2f}" if t.get("profit_loss") is not None else "—",
                 "Outcome": t.get("final_outcome") or "—",
                 "✓": "✅" if t.get("model_accuracy") else ("❌" if t.get("model_accuracy") is False else "—")} for t in closed_trades]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Adaptive recommendations
    updates = recommend_updates(all_trades)
    if updates:
        st.divider()
        st.subheader("🤖 Adaptive Model Recommendations")
        st.warning("These require your approval before being applied.")
        for u in updates:
            st.write(f"**{u['parameter_name']}**: {u['current_value']} → {u['recommended_value']}")
            st.caption(u["reason"])

    if not open_trades and not closed_trades:
        st.info("No trades yet. Use the Signals tab.")

# ── Tab 4: Approval Queue ────────────────────────────────────────────────────
with tabs[3]:
    from app.trading.approval_queue import get_pending, get_all_requests, approve, reject
    from app.trading.semi_auto import execute_approved

    st.subheader("Pending Approval")
    pending = get_pending()

    if not pending:
        st.info("No pending approval requests.")
    else:
        for req in pending:
            with st.container(border=True):
                h1, h2, h3, h4 = st.columns(4)
                h1.metric("ID", req["request_id"])
                h2.metric("Side", req["recommended_side"])
                h3.metric("Edge", f"{req['estimated_edge']:+.1%}")
                h4.metric("Size", f"${req['recommended_size_usd']:.2f}")

                st.write(f"**{req['market_question']}**")
                st.write(f"Market price: **{req['polymarket_price']:.3f}** | "
                         f"Model: **{req['model_fair_probability']:.3f}** | "
                         f"CI: [{req['confidence_interval_low']:.2f}, {req['confidence_interval_high']:.2f}]")
                st.info(f"**Kelly:** {req['kelly_derivation']}")
                st.write(f"**Rationale:** {req['reason_for_signal'][:300]}")

                notes = st.text_input("Notes (optional)", key=f"notes_{req['request_id']}")
                ca, cr = st.columns(2)
                if ca.button("✅ Approve", key=f"approve_{req['request_id']}", type="primary"):
                    approve(req["request_id"], reviewed_by="dashboard_user", notes=notes)
                    result = execute_approved(req["request_id"])
                    if result["success"]:
                        st.success(f"Approved and executed: {result['trade']['trade_id']}")
                    else:
                        st.error(result.get("reason"))
                    st.rerun()
                if cr.button("❌ Reject", key=f"reject_{req['request_id']}"):
                    reject(req["request_id"], reviewed_by="dashboard_user", notes=notes)
                    st.rerun()

    st.divider()
    st.subheader("Request History")
    all_reqs = get_all_requests(limit=20)
    if all_reqs:
        rows = [{"ID": r["request_id"], "Question": r["market_question"][:60],
                 "Side": r["recommended_side"], "Edge": f"{r['estimated_edge']:+.1%}",
                 "Status": r["status"], "Reviewed": str(r["reviewed_at"])[:16] if r["reviewed_at"] else "—",
                 "Notes": r["review_notes"] or "—"} for r in all_reqs]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Tab 5: Wallet ────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("Wallet & Positions (Read-Only)")
    st.info(
        "Connect your Polygon wallet address to view on-chain positions. "
        "No private key required for read access."
    )

    wallet_addr = st.text_input(
        "Polygon wallet address (0x...)",
        value=settings.polymarket_funder_address if hasattr(settings, 'polymarket_funder_address') else "",
        placeholder="0xYourWalletAddress",
    )

    if st.button("🔍 Load Positions") and wallet_addr:
        with st.spinner("Fetching on-chain positions..."):
            from app.polymarket.auth import read_wallet_balances
            wallet_data = read_wallet_balances(wallet_addr)
        st.session_state["wallet"] = wallet_data

    if "wallet" in st.session_state:
        wd = st.session_state["wallet"]
        w1, w2 = st.columns(2)
        w1.metric("Address", wd["address"][:10] + "...")
        w2.metric("Total Position Value", f"${wd['total_position_value_usd']:,.2f}")

        if wd.get("error"):
            st.warning(f"API note: {wd['error']}")

        positions = wd.get("positions", [])
        if positions:
            st.subheader(f"Open Positions ({len(positions)})")
            pos_rows = []
            for p in positions:
                pos_rows.append({
                    "Market": p.get("title", p.get("conditionId",""))[:60],
                    "Side": p.get("side", "—"),
                    "Size": p.get("size", "—"),
                    "Avg Price": p.get("avgPrice", "—"),
                    "Current Value": f"${float(p.get('currentValue', 0)):,.2f}",
                    "Unrealized P&L": p.get("unrealizedPnl", "—"),
                })
            st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No open positions found for this address.")

    st.info("See the Live Execution tab for the full pre-live checklist and emergency controls.")

# ── Tab 6: Live Execution ────────────────────────────────────────────────────
with tabs[5]:
    from app.trading.live_trader import verify_pre_live_checklist, CHECKLIST_ITEMS

    st.subheader("🔴 Live Execution — Phase 6")
    if settings.live_trading_enabled:
        st.error("⚠️ LIVE TRADING IS ENABLED — Real money at risk")
    else:
        st.info("Live trading disabled. Set LIVE_TRADING_ENABLED=true in .env only after completing checklist.")

    st.divider()
    st.subheader("Pre-Live Checklist")
    checklist_labels = {
        "user_confirmation": "Explicit user confirmation (typed phrase)",
        "wallet_funded": "Polygon wallet funded with L2 USDC",
        "eip712_tested": "EIP-712 signing tested on testnet",
        "compliance_approved": "Compliance approval confirmed",
        "paper_trading_complete": "Paper-trading period complete (≥4 weeks)",
        "paper_pnl_positive": "Paper P&L positive with Sharpe > 1.0",
        "risk_limits_configured": "All risk limits configured and tested",
        "kill_switch_tested": "Kill switches tested (manual and auto)",
        "logging_verified": "Logging verified (all events persisting to DB)",
        "emergency_shutdown_tested": "Emergency shutdown tested",
    }
    confirmed = [k for k, label in checklist_labels.items()
                 if st.checkbox(label, key=f"live_chk_{k}")]
    result = verify_pre_live_checklist(confirmed)
    st.progress(result["completed"] / result["total"],
                text=f"{result['completed']}/{result['total']} confirmed")
    if result["passed"]:
        st.success("✅ All items confirmed — live execution unlocked")

    st.divider()
    st.subheader("On-Chain Reconciliation")
    recon_addr = st.text_input("Wallet address", placeholder="0x...", key="recon_addr")
    if st.button("🔄 Reconcile") and recon_addr:
        with st.spinner("Comparing on-chain vs local DB..."):
            from app.trading.reconciler import reconcile
            rep = reconcile(recon_addr)
        fn = {"OK": st.success, "MISMATCH": st.warning}.get(rep["status"], st.error)
        fn(f"**{rep['status']}** | on-chain={rep.get('onchain_count',0)} | local={rep.get('local_count',0)}")
        if rep.get("ghost_positions"):
            st.warning(f"Ghost positions: {rep['ghost_positions']}")
        if rep.get("phantom_positions"):
            st.error(f"Phantom positions: {rep['phantom_positions']}")

    st.divider()
    st.subheader("Emergency Controls")
    c_shut, c_audit = st.columns(2)
    with c_shut:
        phrase = st.text_input("Type SHUTDOWN to confirm", key="shutdown_confirm")
        if st.button("🚨 EMERGENCY SHUTDOWN", type="primary"):
            if phrase == "SHUTDOWN":
                from app.polymarket.execution import emergency_shutdown
                res = emergency_shutdown(reason="dashboard_user")
                st.error(res["message"])
                st.rerun()
            else:
                st.error("Type exactly 'SHUTDOWN' to confirm")
    with c_audit:
        st.subheader("Audit Log")
        try:
            from app.database import AuditLog
            init_db()
            with get_session() as s:
                entries = s.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(15).all()
                rows = [{"Time": str(e.created_at)[:19], "Event": e.event_type,
                         "Data": e.data[:60]} for e in entries]
            st.dataframe(pd.DataFrame(rows) if rows else pd.DataFrame(),
                         use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Audit log: {e}")
