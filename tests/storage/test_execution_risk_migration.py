from pathlib import Path

MIGRATION = Path("backend/alembic/versions/0002_execution_and_risk_audit.py")


def test_execution_and_risk_audit_migration_defines_required_tables() -> None:
    migration = MIGRATION.read_text()

    assert "paper_orders" in migration
    assert "paper_trades" in migration
    assert "risk_decisions" in migration
    assert "ix_paper_orders_state" in migration
    assert "ix_risk_decisions_order_id" in migration
