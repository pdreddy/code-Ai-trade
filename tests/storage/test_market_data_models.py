import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for storage model tests")

from backend.app.infrastructure.database.models import (  # noqa: E402
    BarModel,
    CorporateActionModel,
)


def test_market_data_models_define_idempotency_constraints() -> None:
    bar_constraints = {constraint.name for constraint in BarModel.__table__.constraints}
    action_constraints = {
        constraint.name for constraint in CorporateActionModel.__table__.constraints
    }

    assert "uq_bars_instrument_timestamp_provider_policy" in bar_constraints
    assert "uq_corporate_actions_instrument_date_type_provider" in action_constraints
