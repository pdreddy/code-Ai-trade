from typing import cast

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for model tests")

from sqlalchemy import Table  # noqa: E402

from backend.app.infrastructure.database.models import (  # noqa: E402
    PaperOrderModel,
    PaperTradeModel,
    RiskDecisionModel,
)


def test_execution_and_risk_models_define_audit_tables() -> None:
    metadata = sqlalchemy.MetaData()
    for model in (PaperOrderModel, PaperTradeModel, RiskDecisionModel):
        cast(Table, model.__table__).to_metadata(metadata)

    assert "paper_orders" in metadata.tables
    assert "paper_trades" in metadata.tables
    assert "risk_decisions" in metadata.tables
    assert "state" in metadata.tables["paper_orders"].columns
    assert "reasons" in metadata.tables["risk_decisions"].columns
