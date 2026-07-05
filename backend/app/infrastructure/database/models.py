"""SQLAlchemy models for market-data storage.

These infrastructure models intentionally stay out of the domain layer. They are
optimized for reproducible ingestion, provider lineage, and data-quality auditability.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy infrastructure models."""


class InstrumentModel(Base):
    """Tradable instrument master record."""

    __tablename__ = "instruments"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    bars: Mapped[list["BarModel"]] = relationship(back_populates="instrument")
    corporate_actions: Mapped[list["CorporateActionModel"]] = relationship(
        back_populates="instrument"
    )


class IngestionBatchModel(Base):
    """Provider ingestion batch with source lineage and adjustment policy."""

    __tablename__ = "ingestion_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    adjustment_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    retrieved_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    bars: Mapped[list["BarModel"]] = relationship(back_populates="ingestion_batch")
    corporate_actions: Mapped[list["CorporateActionModel"]] = relationship(
        back_populates="ingestion_batch"
    )
    quality_checks: Mapped[list["DataQualityCheckModel"]] = relationship(
        back_populates="ingestion_batch"
    )


class BarModel(Base):
    """Daily OHLCV bar with raw prices and optional provider-adjusted close."""

    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "timestamp_utc",
            "provider",
            "adjustment_policy",
            name="uq_bars_instrument_timestamp_provider_policy",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    ingestion_batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_batches.id"), nullable=False, index=True
    )
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    adjusted_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    instrument: Mapped[InstrumentModel] = relationship(back_populates="bars")
    ingestion_batch: Mapped[IngestionBatchModel] = relationship(back_populates="bars")


class CorporateActionModel(Base):
    """Split and dividend events tied to an instrument and provider lineage."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "ex_date",
            "action_type",
            "provider",
            name="uq_corporate_actions_instrument_date_type_provider",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    ingestion_batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_batches.id"), nullable=False, index=True
    )
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)

    instrument: Mapped[InstrumentModel] = relationship(back_populates="corporate_actions")
    ingestion_batch: Mapped[IngestionBatchModel] = relationship(
        back_populates="corporate_actions"
    )


class DataQualityCheckModel(Base):
    """Data-quality check result for an ingestion batch."""

    __tablename__ = "data_quality_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingestion_batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingestion_batches.id"), nullable=False, index=True
    )
    check_name: Mapped[str] = mapped_column(String(128), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ingestion_batch: Mapped[IngestionBatchModel] = relationship(back_populates="quality_checks")


class PaperOrderModel(Base):
    """Persisted paper order with deterministic lifecycle state."""

    __tablename__ = "paper_orders"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    instrument_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_in_force: Mapped[str] = mapped_column(String(16), nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class PaperTradeModel(Base):
    """Persisted paper trade produced by the paper broker."""

    __tablename__ = "paper_trades"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    instrument_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True), ForeignKey("instruments.id"), nullable=False, index=True
    )
    entry_order_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    exit_order_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True), nullable=True)
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class RiskDecisionModel(Base):
    """Persisted risk decision and rejection reasons for auditability."""

    __tablename__ = "risk_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reasons: Mapped[str] = mapped_column(String(4096), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
