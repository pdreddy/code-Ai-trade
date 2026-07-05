"""Compare modeled options strategy styles and rank the strongest variants."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from backend.app.application.agents.registry import create_default_agents
from backend.app.application.decision_engine import MasterDecisionEngine
from backend.app.application.options_backtesting import (
    OptionsBacktester,
    OptionsBacktestResult,
    OptionsStyle,
)
from backend.app.domain.entities import Bar

DEFAULT_MIN_WIN_RATE = Decimal("0.55")


@dataclass(frozen=True, slots=True)
class OptionsStrategyScreenResult:
    style: OptionsStyle
    result: OptionsBacktestResult
    meets_threshold: bool
    recommended: bool


@dataclass(frozen=True, slots=True)
class OptionsStrategyScreen:
    symbol: str
    min_win_rate: Decimal
    results: tuple[OptionsStrategyScreenResult, ...]


class OptionsStrategyScreenService:
    """Run every supported options style over the same bars and rank outcomes."""

    def screen(
        self,
        instrument_id: UUID,
        symbol: str,
        bars: Sequence[Bar],
        capital: Decimal,
        min_win_rate: Decimal = DEFAULT_MIN_WIN_RATE,
    ) -> OptionsStrategyScreen:
        scored: list[OptionsStrategyScreenResult] = []
        for style in OptionsStyle:
            backtester = OptionsBacktester(
                agents=create_default_agents(),
                engine=MasterDecisionEngine(),
                style=style,
                initial_capital=capital,
            )
            result = backtester.run(instrument_id, symbol, bars)
            scored.append(
                OptionsStrategyScreenResult(
                    style=style,
                    result=result,
                    meets_threshold=(
                        result.metrics.win_rate >= min_win_rate
                        and result.metrics.total_return > Decimal("0")
                    ),
                    recommended=False,
                )
            )

        ranked = sorted(
            scored,
            key=lambda item: (
                item.meets_threshold,
                item.result.metrics.win_rate,
                item.result.metrics.total_return,
                item.result.metrics.profit_factor,
                -item.result.metrics.max_drawdown.copy_abs(),
            ),
            reverse=True,
        )
        if ranked:
            ranked[0] = OptionsStrategyScreenResult(
                style=ranked[0].style,
                result=ranked[0].result,
                meets_threshold=ranked[0].meets_threshold,
                recommended=True,
            )
        return OptionsStrategyScreen(
            symbol=symbol,
            min_win_rate=min_win_rate,
            results=tuple(ranked),
        )
