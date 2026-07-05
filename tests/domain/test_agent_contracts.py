from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.domain.agents import AgentRequest, AgentVote
from backend.app.domain.entities import Bar
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Confidence, Price


def _bar(instrument_id, index: int) -> Bar:  # type: ignore[no-untyped-def]
    timestamp = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=index)
    price = Decimal("100") + Decimal(index)
    return Bar(
        instrument_id=instrument_id,
        timestamp=timestamp,
        open=Price(price),
        high=Price(price + Decimal("1")),
        low=Price(price - Decimal("1")),
        close=Price(price),
        volume=1_000_000 + index,
    )


def test_agent_request_rejects_future_bars() -> None:
    instrument_id = uuid4()
    bar = _bar(instrument_id, 1)

    with pytest.raises(DomainValidationError, match="future bars"):
        AgentRequest(
            instrument_id=instrument_id,
            bars=(bar,),
            evaluated_at=bar.timestamp - timedelta(seconds=1),
        )


def test_agent_vote_requires_reasons_and_valid_time_ordering() -> None:
    signal_bar_timestamp = datetime(2025, 1, 1, tzinfo=UTC)

    with pytest.raises(DomainValidationError, match="at least one reason"):
        AgentVote(
            agent_name="trend",
            action=SignalAction.HOLD,
            confidence=Confidence(Decimal("0")),
            score=Decimal("0"),
            reasons=(),
            evaluated_at=signal_bar_timestamp,
            signal_bar_timestamp=signal_bar_timestamp,
        )
