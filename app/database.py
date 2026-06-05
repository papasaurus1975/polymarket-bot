"""Database connection and ORM models: SQLite (SIMPLE_MODE) or PostgreSQL."""
from datetime import datetime
from sqlalchemy import create_engine, String, Float, Boolean, DateTime, JSON, Integer, Text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, mapped_column, Mapped
from contextlib import contextmanager


class Base(DeclarativeBase):
    pass


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    trade_id: Mapped[str] = mapped_column(String, primary_key=True)
    signal_id: Mapped[str] = mapped_column(String, index=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    market_question: Mapped[str] = mapped_column(Text)
    market_type: Mapped[str] = mapped_column(String(2))
    strategy_name: Mapped[str] = mapped_column(String)

    entry_time: Mapped[datetime] = mapped_column(DateTime)
    entry_price: Mapped[float] = mapped_column(Float)
    side: Mapped[str] = mapped_column(String(3))       # YES / NO
    size: Mapped[float] = mapped_column(Float)

    model_probability_at_entry: Mapped[float] = mapped_column(Float)
    market_probability_at_entry: Mapped[float] = mapped_column(Float)
    edge_at_entry: Mapped[float] = mapped_column(Float)
    resolution_source_match_score: Mapped[float] = mapped_column(Float)

    simulated_fill_ratio: Mapped[float] = mapped_column(Float, default=1.0)
    simulated_slippage: Mapped[float] = mapped_column(Float, default=0.0)
    fees_simulated: Mapped[float] = mapped_column(Float, default=0.0)

    exit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    profit_loss: Mapped[float | None] = mapped_column(Float, nullable=True)

    max_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)

    final_outcome: Mapped[str | None] = mapped_column(String, nullable=True)   # YES/NO/still_open
    actual_resolution_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_accuracy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    calibration_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String, default="OPEN")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    market_id: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    trigger_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResolutionEvent(Base):
    __tablename__ = "resolution_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_outcome: Mapped[str] = mapped_column(String)      # YES / NO
    model_probability_at_resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_price_at_resolution: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibration_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_name: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def get_engine():
    from app.config import settings
    if settings.simple_mode:
        return create_engine("sqlite:///polymarket_bot.db", echo=False,
                             connect_args={"check_same_thread": False})
    return create_engine(settings.database_url, echo=False)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    Base.metadata.create_all(bind=engine)
