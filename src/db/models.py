"""SQLAlchemy ORM models."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    holdings: Mapped[list["Holding"]] = relationship("Holding", back_populates="portfolio")
    scores: Mapped[list["HealthScore"]] = relationship("HealthScore", back_populates="portfolio")


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "ticker", name="uq_portfolio_ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)  # 0–1, must sum to 1

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="holdings")


class Price(Base):
    """Daily adjusted close prices fetched from yfinance."""

    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("ticker", "price_date", name="uq_ticker_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)


class HealthScore(Base):
    __tablename__ = "health_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    volatility: Mapped[float] = mapped_column(Float)
    max_drawdown: Mapped[float] = mapped_column(Float)
    sharpe: Mapped[float] = mapped_column(Float)
    concentration_hhi: Mapped[float] = mapped_column(Float)
    avg_correlation: Mapped[float] = mapped_column(Float)

    portfolio: Mapped["Portfolio"] = relationship("Portfolio", back_populates="scores")
