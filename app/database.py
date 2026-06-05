"""Database connection: SQLite (SIMPLE_MODE) or PostgreSQL (production)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_engine():
    from app.config import settings
    if settings.simple_mode:
        return create_engine("sqlite:///polymarket_bot.db", echo=False)
    return create_engine(settings.database_url, echo=False)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    Base.metadata.create_all(bind=engine)
