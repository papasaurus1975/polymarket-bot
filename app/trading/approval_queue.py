"""Human approval workflow for semi-auto mode.

Signals in semi_auto mode go to PENDING_HUMAN_APPROVAL status.
No order is placed until the user explicitly approves via the dashboard.
"""
import uuid
import structlog
from datetime import datetime, timezone
from app.database import get_session, init_db, Base
from sqlalchemy import String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import mapped_column, Mapped

log = structlog.get_logger()


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String, index=True)
    market_id: Mapped[str] = mapped_column(String)
    market_question: Mapped[str] = mapped_column(Text)
    market_type: Mapped[str] = mapped_column(String(2))
    recommended_side: Mapped[str] = mapped_column(String(3))

    polymarket_price: Mapped[float] = mapped_column(Float)
    model_fair_probability: Mapped[float] = mapped_column(Float)
    estimated_edge: Mapped[float] = mapped_column(Float)
    confidence_score: Mapped[float] = mapped_column(Float)
    resolution_source_match_score: Mapped[float] = mapped_column(Float)

    recommended_size_usd: Mapped[float] = mapped_column(Float)
    kelly_fraction: Mapped[float] = mapped_column(Float)
    kelly_derivation: Mapped[str] = mapped_column(Text)

    reason_for_signal: Mapped[str] = mapped_column(Text)
    invalidating_conditions: Mapped[str] = mapped_column(Text)
    news_items_cited: Mapped[str] = mapped_column(Text, default="")
    event_calendar_events_cited: Mapped[str] = mapped_column(Text, default="")

    confidence_interval_low: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_interval_high: Mapped[float] = mapped_column(Float, default=1.0)

    status: Mapped[str] = mapped_column(String, default="PENDING")  # PENDING/APPROVED/REJECTED/EXPIRED
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def submit_for_approval(signal, kelly_info: dict) -> dict:
    """Create an approval request from a signal. Returns snapshot dict."""
    init_db()
    req = ApprovalRequest(
        request_id=str(uuid.uuid4())[:12],
        signal_id=signal.signal_id,
        market_id=signal.market_id,
        market_question=signal.market_question,
        market_type=signal.market_type,
        recommended_side=signal.recommended_side,
        polymarket_price=signal.polymarket_price,
        model_fair_probability=signal.model_fair_probability,
        estimated_edge=signal.estimated_edge,
        confidence_score=signal.confidence_score,
        resolution_source_match_score=signal.resolution_source_match_score,
        recommended_size_usd=kelly_info["recommended_size_usd"],
        kelly_fraction=kelly_info["kelly_fraction"],
        kelly_derivation=kelly_info["derivation"],
        reason_for_signal=signal.reason_for_signal,
        invalidating_conditions=signal.invalidating_conditions,
        news_items_cited="\n".join(signal.news_items_cited or []),
        event_calendar_events_cited="\n".join(signal.event_calendar_events_cited or []),
        confidence_interval_low=signal.model_confidence_interval[0],
        confidence_interval_high=signal.model_confidence_interval[1],
        status="PENDING",
    )
    with get_session() as session:
        session.add(req)
        session.flush()
        snap = _snap(req)
    log.info("approval_submitted", request_id=snap["request_id"],
             question=signal.market_question[:60], side=signal.recommended_side)
    return snap


def approve(request_id: str, reviewed_by: str = "user",
            notes: str = "") -> dict | None:
    """Approve a pending request. Returns snapshot or None if not found."""
    init_db()
    with get_session() as session:
        req = session.get(ApprovalRequest, request_id)
        if not req or req.status != "PENDING":
            return None
        req.status = "APPROVED"
        req.reviewed_by = reviewed_by
        req.review_notes = notes
        req.reviewed_at = datetime.now(timezone.utc)
        session.add(req)
        snap = _snap(req)
    log.info("approval_approved", request_id=request_id, reviewed_by=reviewed_by)
    return snap


def reject(request_id: str, reviewed_by: str = "user",
           notes: str = "") -> dict | None:
    """Reject a pending request."""
    init_db()
    with get_session() as session:
        req = session.get(ApprovalRequest, request_id)
        if not req or req.status != "PENDING":
            return None
        req.status = "REJECTED"
        req.reviewed_by = reviewed_by
        req.review_notes = notes
        req.reviewed_at = datetime.now(timezone.utc)
        session.add(req)
        snap = _snap(req)
    log.info("approval_rejected", request_id=request_id)
    return snap


def get_pending() -> list[dict]:
    init_db()
    with get_session() as session:
        reqs = session.query(ApprovalRequest).filter(
            ApprovalRequest.status == "PENDING"
        ).order_by(ApprovalRequest.created_at.desc()).all()
        return [_snap(r) for r in reqs]


def get_all_requests(limit: int = 50) -> list[dict]:
    init_db()
    with get_session() as session:
        reqs = session.query(ApprovalRequest).order_by(
            ApprovalRequest.created_at.desc()
        ).limit(limit).all()
        return [_snap(r) for r in reqs]


def _snap(req: ApprovalRequest) -> dict:
    return {
        "request_id": req.request_id, "signal_id": req.signal_id,
        "market_id": req.market_id, "market_question": req.market_question,
        "market_type": req.market_type, "recommended_side": req.recommended_side,
        "polymarket_price": req.polymarket_price,
        "model_fair_probability": req.model_fair_probability,
        "estimated_edge": req.estimated_edge,
        "confidence_score": req.confidence_score,
        "resolution_source_match_score": req.resolution_source_match_score,
        "recommended_size_usd": req.recommended_size_usd,
        "kelly_fraction": req.kelly_fraction,
        "kelly_derivation": req.kelly_derivation,
        "reason_for_signal": req.reason_for_signal,
        "invalidating_conditions": req.invalidating_conditions,
        "news_items_cited": req.news_items_cited,
        "confidence_interval_low": req.confidence_interval_low,
        "confidence_interval_high": req.confidence_interval_high,
        "status": req.status, "reviewed_by": req.reviewed_by,
        "review_notes": req.review_notes, "reviewed_at": req.reviewed_at,
        "created_at": req.created_at,
    }
