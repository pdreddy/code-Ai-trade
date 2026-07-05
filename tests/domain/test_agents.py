# ruff: noqa: PLR2004
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from backend.app.application.agents import create_default_agents
from backend.app.domain.agents import AgentRequest
from backend.app.domain.entities import Bar
from backend.app.domain.enums import SignalAction
from backend.app.domain.value_objects import Price

EXPECTED_AGENT_NAMES = (
    "trend",
    "momentum",
    "short_term_guard",
    "volatility",
    "risk",
    "portfolio",
    "mean_reversion",
    "breakout",
    "rally_base_pattern",
    "supply_demand",
    "support_resistance",
    "volume",
    "market_regime",
)


def _bars(
    count: int, slope: Decimal = Decimal("0.5"), final_breakout: bool = False
) -> tuple[Bar, ...]:
    instrument_id = uuid4()
    rows: list[Bar] = []
    for index in range(count):
        timestamp = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
        close = Decimal("100") + Decimal(index) * slope
        if final_breakout and index == count - 1:
            close += Decimal("20")
        rows.append(
            Bar(
                instrument_id=instrument_id,
                timestamp=timestamp,
                open=Price(close - Decimal("0.2")),
                high=Price(close + Decimal("1")),
                low=Price(close - Decimal("1")),
                close=Price(close),
                volume=1_000_000 + index * 1_000,
            )
        )
    return tuple(rows)


def _request(bars: tuple[Bar, ...]) -> AgentRequest:
    return AgentRequest(
        instrument_id=bars[-1].instrument_id,
        bars=bars,
        evaluated_at=bars[-1].timestamp + timedelta(minutes=1),
    )


def test_default_registry_contains_required_independent_agents() -> None:
    agents = create_default_agents()

    assert tuple(agent.name for agent in agents) == EXPECTED_AGENT_NAMES


def test_default_agents_return_standard_votes_without_future_data() -> None:
    request = _request(_bars(240, final_breakout=True))

    votes = tuple(agent.evaluate(request) for agent in create_default_agents())

    assert len(votes) == len(EXPECTED_AGENT_NAMES)
    assert all(vote.reasons for vote in votes)
    assert all(Decimal("0") <= vote.confidence.value <= Decimal("1") for vote in votes)
    assert all(vote.signal_bar_timestamp == request.signal_bar_timestamp for vote in votes)


def test_short_term_guard_de_risks_negative_one_month_return() -> None:
    request = _request(_bars(40, slope=Decimal("-0.2")))
    guard_agent = create_default_agents()[2]

    vote = guard_agent.evaluate(request)

    assert vote.agent_name == "short_term_guard"
    assert vote.action is SignalAction.SELL
    assert "1M guard" in vote.reasons[0]


def test_breakout_agent_detects_close_above_prior_range() -> None:
    request = _request(_bars(40, slope=Decimal("0.1"), final_breakout=True))
    breakout_agent = create_default_agents()[7]

    vote = breakout_agent.evaluate(request)

    assert vote.agent_name == "breakout"
    assert vote.action is SignalAction.BUY
    assert "prior 20-session high" in vote.reasons[0]


def test_rally_base_pattern_agent_detects_rally_base_rally() -> None:
    bars = _bars(40, slope=Decimal("0.1"))
    instrument_id = bars[-1].instrument_id
    start = bars[-1].timestamp + timedelta(days=1)
    pattern_closes = (
        Decimal("100"),
        Decimal("102"),
        Decimal("104"),
        Decimal("104.1"),
        Decimal("103.9"),
        Decimal("104.2"),
        Decimal("105"),
        Decimal("107"),
        Decimal("109"),
    )
    pattern = tuple(
        Bar(
            instrument_id=instrument_id,
            timestamp=start + timedelta(days=index),
            open=Price(close - Decimal("0.4")),
            high=Price(close + Decimal("0.5")),
            low=Price(close - Decimal("0.5")),
            close=Price(close),
            volume=1_200_000,
        )
        for index, close in enumerate(pattern_closes)
    )
    request = _request(bars + pattern)
    pattern_agent = create_default_agents()[8]

    vote = pattern_agent.evaluate(request)

    assert vote.agent_name == "rally_base_pattern"
    assert vote.action is SignalAction.BUY
    assert "rally-base-rally" in vote.reasons[0]


def test_supply_demand_agent_detects_demand_retest() -> None:
    bars = _bars(30, slope=Decimal("0.1"))
    instrument_id = bars[-1].instrument_id
    start = bars[-1].timestamp + timedelta(days=1)
    prices = (
        Decimal("110"),
        Decimal("110.2"),
        Decimal("109.9"),
        Decimal("113"),
        Decimal("116"),
        Decimal("119"),
        Decimal("116"),
        Decimal("113"),
        Decimal("110.3"),
    )
    demand_sequence = tuple(
        Bar(
            instrument_id=instrument_id,
            timestamp=start + timedelta(days=index),
            open=Price(close - Decimal("0.2")),
            high=Price(close + Decimal("0.4")),
            low=Price(close - Decimal("0.4")),
            close=Price(close),
            volume=1_500_000,
        )
        for index, close in enumerate(prices)
    )
    request = _request(bars + demand_sequence)
    supply_demand_agent = create_default_agents()[9]

    vote = supply_demand_agent.evaluate(request)

    assert vote.agent_name == "supply_demand"
    assert vote.action is SignalAction.BUY
    assert "demand zone" in vote.reasons[0]
