"""Create market data storage tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_market_data_storage"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("symbol", name="uq_instruments_symbol"),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])

    op.create_table(
        "ingestion_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("adjustment_policy", sa.String(length=128), nullable=False),
        sa.Column("retrieved_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ingestion_batches_symbol", "ingestion_batches", ["symbol"])

    op.create_table(
        "bars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("adjustment_policy", sa.String(length=128), nullable=False),
        sa.Column("open", sa.Numeric(20, 8), nullable=False),
        sa.Column("high", sa.Numeric(20, 8), nullable=False),
        sa.Column("low", sa.Numeric(20, 8), nullable=False),
        sa.Column("close", sa.Numeric(20, 8), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(20, 8), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"]),
        sa.UniqueConstraint(
            "instrument_id",
            "timestamp_utc",
            "provider",
            "adjustment_policy",
            name="uq_bars_instrument_timestamp_provider_policy",
        ),
    )
    op.create_index("ix_bars_instrument_id", "bars", ["instrument_id"])
    op.create_index("ix_bars_ingestion_batch_id", "bars", ["ingestion_batch_id"])

    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"]),
        sa.UniqueConstraint(
            "instrument_id",
            "ex_date",
            "action_type",
            "provider",
            name="uq_corporate_actions_instrument_date_type_provider",
        ),
    )
    op.create_index("ix_corporate_actions_instrument_id", "corporate_actions", ["instrument_id"])
    op.create_index(
        "ix_corporate_actions_ingestion_batch_id",
        "corporate_actions",
        ["ingestion_batch_id"],
    )

    op.create_table(
        "data_quality_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ingestion_batch_id", sa.Integer(), nullable=False),
        sa.Column("check_name", sa.String(length=128), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("details", sa.String(length=2048), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_batch_id"], ["ingestion_batches.id"]),
    )
    op.create_index(
        "ix_data_quality_checks_ingestion_batch_id",
        "data_quality_checks",
        ["ingestion_batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_quality_checks_ingestion_batch_id", table_name="data_quality_checks")
    op.drop_table("data_quality_checks")
    op.drop_index("ix_corporate_actions_ingestion_batch_id", table_name="corporate_actions")
    op.drop_index("ix_corporate_actions_instrument_id", table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_index("ix_bars_ingestion_batch_id", table_name="bars")
    op.drop_index("ix_bars_instrument_id", table_name="bars")
    op.drop_table("bars")
    op.drop_index("ix_ingestion_batches_symbol", table_name="ingestion_batches")
    op.drop_table("ingestion_batches")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_table("instruments")
