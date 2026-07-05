"""execution and risk audit storage

Revision ID: 0002_execution_and_risk_audit
Revises: 0001_market_data_storage
Create Date: 2026-07-03 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_execution_and_risk_audit"
down_revision = "0001_market_data_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_in_force", sa.String(length=16), nullable=False),
        sa.Column("limit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("stop_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("average_fill_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("rejection_reason", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_orders_instrument_id", "paper_orders", ["instrument_id"])
    op.create_index("ix_paper_orders_state", "paper_orders", ["state"])

    op.create_table(
        "paper_trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exit_order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=False),
        sa.Column("exit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(24, 8), nullable=True),
        sa.Column("reason", sa.String(length=2048), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_trades_instrument_id", "paper_trades", ["instrument_id"])

    op.create_table(
        "risk_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reasons", sa.String(length=4096), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_decisions_order_id", "risk_decisions", ["order_id"])
    op.create_index("ix_risk_decisions_decision", "risk_decisions", ["decision"])


def downgrade() -> None:
    op.drop_index("ix_risk_decisions_decision", table_name="risk_decisions")
    op.drop_index("ix_risk_decisions_order_id", table_name="risk_decisions")
    op.drop_table("risk_decisions")
    op.drop_index("ix_paper_trades_instrument_id", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("ix_paper_orders_state", table_name="paper_orders")
    op.drop_index("ix_paper_orders_instrument_id", table_name="paper_orders")
    op.drop_table("paper_orders")
