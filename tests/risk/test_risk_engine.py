from decimal import Decimal
from uuid import uuid4

from backend.app.application.risk import RiskContext, RiskDecision, RiskEngine, RiskPolicy
from backend.app.domain.entities import RiskRule
from backend.app.domain.value_objects import RiskFraction


def _rule(kill_switch: bool = False) -> RiskRule:
    return RiskRule(
        id=uuid4(),
        name="institutional-default",
        max_risk_per_trade=RiskFraction(Decimal("0.01")),
        max_gross_exposure=RiskFraction(Decimal("0.50")),
        max_sector_exposure=RiskFraction(Decimal("0.25")),
        max_drawdown=RiskFraction(Decimal("0.10")),
        kill_switch_enabled=kill_switch,
    )


def _context(**overrides: object) -> RiskContext:
    values = {
        "rule": _rule(),
        "equity": Decimal("100000"),
        "current_gross_exposure": Decimal("10000"),
        "proposed_order_value": Decimal("10000"),
        "intended_risk_fraction": RiskFraction(Decimal("0.005")),
        "current_drawdown": RiskFraction(Decimal("0.02")),
        "average_daily_volume": 1_000_000,
        "max_pairwise_correlation": Decimal("0.40"),
    }
    values.update(overrides)
    return RiskContext(**values)  # type: ignore[arg-type]


def test_risk_engine_approves_order_inside_limits() -> None:
    assessment = RiskEngine().evaluate(_context())

    assert assessment.decision is RiskDecision.APPROVED
    assert assessment.approved


def test_risk_engine_rejects_kill_switch_exposure_liquidity_and_correlation() -> None:
    assessment = RiskEngine(RiskPolicy(min_average_daily_volume=500_000)).evaluate(
        _context(
            rule=_rule(kill_switch=True),
            proposed_order_value=Decimal("60000"),
            average_daily_volume=100_000,
            max_pairwise_correlation=Decimal("0.95"),
        )
    )

    assert assessment.decision is RiskDecision.REJECTED
    assert "kill switch is enabled" in assessment.reasons
    assert "max gross exposure exceeded" in assessment.reasons
    assert "liquidity filter failed" in assessment.reasons
    assert "correlation filter failed" in assessment.reasons


def test_risk_engine_rejects_trade_risk_and_drawdown_limits() -> None:
    assessment = RiskEngine().evaluate(
        _context(
            intended_risk_fraction=RiskFraction(Decimal("0.02")),
            current_drawdown=RiskFraction(Decimal("0.20")),
        )
    )

    assert "max risk per trade exceeded" in assessment.reasons
    assert "max drawdown exceeded" in assessment.reasons
