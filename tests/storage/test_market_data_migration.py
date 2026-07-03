from pathlib import Path

MIGRATION_PATH = Path("backend/alembic/versions/0001_market_data_storage.py")


def test_market_data_migration_defines_core_tables_and_idempotency_constraints() -> None:
    migration = MIGRATION_PATH.read_text()

    assert '"instruments"' in migration
    assert '"ingestion_batches"' in migration
    assert '"bars"' in migration
    assert '"corporate_actions"' in migration
    assert '"data_quality_checks"' in migration
    assert "uq_bars_instrument_timestamp_provider_policy" in migration
    assert "uq_corporate_actions_instrument_date_type_provider" in migration
