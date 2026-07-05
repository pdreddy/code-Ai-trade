# ruff: noqa: PLR2004
"""Deterministic technical and portfolio-aware research agents.

These agents intentionally do not fetch data, place orders, mutate portfolios, or
perform persistence. They evaluate only bars and optional portfolio/risk context
that has already passed through data-quality boundaries.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from decimal import Decimal

from backend.app.domain.agents import AgentRequest, AgentVote
from backend.app.domain.entities import Bar
from backend.app.domain.enums import SignalAction
from backend.app.domain.value_objects import Confidence

AgentEvaluation = tuple[SignalAction, Decimal, Decimal, tuple[str, ...]]

DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


class BaseDeterministicAgent(ABC):
    """Shared vote construction for deterministic agents."""

    name: str

    def evaluate(self, request: AgentRequest) -> AgentVote:
        action, confidence, score, reasons = self._evaluate(request)
        return AgentVote(
            agent_name=self.name,
            action=action,
            confidence=Confidence(confidence),
            score=score,
            reasons=reasons,
            evaluated_at=request.evaluated_at,
            signal_bar_timestamp=request.signal_bar_timestamp,
        )

    @abstractmethod
    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        """Return action, confidence, score, and reasons."""

    def _insufficient_history(self, required: int, actual: int) -> AgentEvaluation:
        return (
            SignalAction.HOLD,
            Decimal("0"),
            Decimal("0"),
            (f"{self.name} requires {required} bars but received {actual}",),
        )


class TrendAgent(BaseDeterministicAgent):
    name = "trend"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        closes = _closes(request.bars)
        if len(closes) < 50:
            return self._insufficient_history(50, len(closes))
        fast = _mean(closes[-20:])
        slow = _mean(closes[-50:])
        latest = closes[-1]
        spread = _bounded((fast - slow) / slow * Decimal("5"))
        if latest > fast > slow:
            return _vote(SignalAction.BUY, spread, "close is above rising 20/50 day trend")
        if latest < fast < slow:
            return _vote(
                SignalAction.SELL, spread.copy_abs(), "close is below falling 20/50 day trend"
            )
        return _vote(SignalAction.HOLD, spread.copy_abs(), "trend stack is mixed")


class MomentumAgent(BaseDeterministicAgent):
    name = "momentum"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        closes = _closes(request.bars)
        if len(closes) < 22:
            return self._insufficient_history(22, len(closes))
        ret = closes[-1] / closes[-22] - DECIMAL_ONE
        score = _bounded(ret * Decimal("8"))
        if ret > Decimal("0.03"):
            return _vote(SignalAction.BUY, score, "21-session momentum is positive")
        if ret < Decimal("-0.03"):
            return _vote(SignalAction.SELL, score.copy_abs(), "21-session momentum is negative")
        return _vote(SignalAction.HOLD, score.copy_abs(), "21-session momentum is neutral")


class VolatilityAgent(BaseDeterministicAgent):
    name = "volatility"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        closes = _closes(request.bars)
        if len(closes) < 61:
            return self._insufficient_history(61, len(closes))
        current = _realized_volatility(closes[-21:])
        baseline = _realized_volatility(closes[-61:])
        ratio = current / baseline if baseline > DECIMAL_ZERO else DECIMAL_ONE
        if ratio > Decimal("1.35"):
            return _vote(
                SignalAction.SELL,
                _bounded((ratio - DECIMAL_ONE) / Decimal("2")),
                "short-term volatility is elevated versus baseline",
            )
        if ratio < Decimal("0.75"):
            return _vote(
                SignalAction.BUY,
                _bounded(DECIMAL_ONE - ratio),
                "short-term volatility is compressed versus baseline",
            )
        return _vote(SignalAction.HOLD, Decimal("0.25"), "volatility is close to baseline")


class RiskAgent(BaseDeterministicAgent):
    name = "risk"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if request.risk_rule is not None and request.risk_rule.kill_switch_enabled:
            return _vote(SignalAction.SELL, Decimal("1"), "risk kill switch is enabled")
        closes = _closes(request.bars)
        if len(closes) < 20:
            return self._insufficient_history(20, len(closes))
        drawdown = _max_drawdown(closes[-20:])
        if drawdown < Decimal("-0.08"):
            return _vote(
                SignalAction.SELL,
                _bounded(drawdown.copy_abs() * Decimal("5")),
                "20-session drawdown exceeds risk threshold",
            )
        return _vote(SignalAction.HOLD, Decimal("0.3"), "risk drawdown is within mandate")


class PortfolioAgent(BaseDeterministicAgent):
    name = "portfolio"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        position = request.portfolio_position
        if position is None:
            return _vote(
                SignalAction.HOLD,
                Decimal("0.2"),
                "no existing portfolio position for this instrument",
            )
        pnl_fraction = (position.market_price.value / position.average_cost.value) - DECIMAL_ONE
        if pnl_fraction > Decimal("0.10"):
            return _vote(
                SignalAction.HOLD,
                Decimal("0.45"),
                "position has material unrealized gain; avoid overtrading",
            )
        if pnl_fraction < Decimal("-0.06"):
            return _vote(
                SignalAction.SELL,
                _bounded(pnl_fraction.copy_abs() * Decimal("4")),
                "position unrealized loss exceeds portfolio tolerance",
            )
        return _vote(
            SignalAction.HOLD, Decimal("0.25"), "position unrealized PnL is within rebalance band"
        )


class MeanReversionAgent(BaseDeterministicAgent):
    name = "mean_reversion"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        closes = _closes(request.bars)
        if len(closes) < 20:
            return self._insufficient_history(20, len(closes))
        window = closes[-20:]
        z_score = _z_score(window[-1], window)
        if z_score <= Decimal("-2"):
            return _vote(
                SignalAction.BUY,
                _bounded(z_score.copy_abs() / Decimal("3")),
                "close is more than two standard deviations below mean",
            )
        if z_score >= Decimal("2"):
            return _vote(
                SignalAction.SELL,
                _bounded(z_score / Decimal("3")),
                "close is more than two standard deviations above mean",
            )
        return _vote(SignalAction.HOLD, Decimal("0.2"), "close is inside mean-reversion band")


class BreakoutAgent(BaseDeterministicAgent):
    name = "breakout"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if len(request.bars) < 21:
            return self._insufficient_history(21, len(request.bars))
        latest_close = request.bars[-1].close.value
        prior = request.bars[-21:-1]
        prior_high = max(bar.high.value for bar in prior)
        prior_low = min(bar.low.value for bar in prior)
        if latest_close > prior_high:
            return _vote(
                SignalAction.BUY, Decimal("0.7"), "close broke above prior 20-session high"
            )
        if latest_close < prior_low:
            return _vote(
                SignalAction.SELL, Decimal("0.7"), "close broke below prior 20-session low"
            )
        return _vote(
            SignalAction.HOLD, Decimal("0.2"), "close remains inside prior 20-session range"
        )


class SupportResistanceAgent(BaseDeterministicAgent):
    name = "support_resistance"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if len(request.bars) < 30:
            return self._insufficient_history(30, len(request.bars))
        latest_close = request.bars[-1].close.value
        window = request.bars[-30:]
        support = min(bar.low.value for bar in window)
        resistance = max(bar.high.value for bar in window)
        distance_to_support = (latest_close - support) / latest_close
        distance_to_resistance = (resistance - latest_close) / latest_close
        if distance_to_support < Decimal("0.015"):
            return _vote(
                SignalAction.BUY, Decimal("0.55"), "close is within 1.5% of 30-session support"
            )
        if distance_to_resistance < Decimal("0.015"):
            return _vote(
                SignalAction.SELL, Decimal("0.55"), "close is within 1.5% of 30-session resistance"
            )
        return _vote(SignalAction.HOLD, Decimal("0.2"), "price is between support and resistance")


class VolumeAgent(BaseDeterministicAgent):
    name = "volume"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if len(request.bars) < 21:
            return self._insufficient_history(21, len(request.bars))
        average_volume = Decimal(sum(bar.volume for bar in request.bars[-21:-1])) / Decimal("20")
        latest_volume = Decimal(request.bars[-1].volume)
        latest_return = request.bars[-1].close.value / request.bars[-2].close.value - DECIMAL_ONE
        if average_volume <= DECIMAL_ZERO:
            return _vote(SignalAction.HOLD, Decimal("0"), "average volume is zero")
        volume_ratio = latest_volume / average_volume
        if volume_ratio > Decimal("1.5") and latest_return > DECIMAL_ZERO:
            return _vote(
                SignalAction.BUY,
                _bounded((volume_ratio - DECIMAL_ONE) / Decimal("2")),
                "up day confirmed by elevated volume",
            )
        if volume_ratio > Decimal("1.5") and latest_return < DECIMAL_ZERO:
            return _vote(
                SignalAction.SELL,
                _bounded((volume_ratio - DECIMAL_ONE) / Decimal("2")),
                "down day confirmed by elevated volume",
            )
        return _vote(SignalAction.HOLD, Decimal("0.2"), "latest volume is not a confirming outlier")


class RallyBasePatternAgent(BaseDeterministicAgent):
    name = "rally_base_pattern"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if len(request.bars) < 9:
            return self._insufficient_history(9, len(request.bars))
        first = request.bars[-9:-6]
        base = request.bars[-6:-3]
        last = request.bars[-3:]
        first_move = _segment_return(first)
        last_move = _segment_return(last)
        base_high = max(bar.high.value for bar in base)
        base_low = min(bar.low.value for bar in base)
        latest_close = request.bars[-1].close.value
        base_tight = _zone_width(base_low, base_high) <= Decimal("0.035")
        impulse = Decimal("0.012")

        if base_tight and first_move > impulse and last_move > impulse and latest_close > base_high:
            return _vote(
                SignalAction.BUY,
                _bounded((first_move + last_move) * Decimal("10")),
                "rally-base-rally continuation broke above a tight base",
            )
        if (
            base_tight
            and first_move < -impulse
            and last_move > impulse
            and latest_close > base_high
        ):
            return _vote(
                SignalAction.BUY,
                _bounded((last_move + first_move.copy_abs()) * Decimal("8")),
                "drop-base-rally demand reversal broke above its base",
            )
        if (
            base_tight
            and first_move < -impulse
            and last_move < -impulse
            and latest_close < base_low
        ):
            return _vote(
                SignalAction.SELL,
                _bounded((first_move.copy_abs() + last_move.copy_abs()) * Decimal("10")),
                "drop-base-drop continuation broke below a tight base",
            )
        if base_tight and first_move > impulse and last_move < -impulse and latest_close < base_low:
            return _vote(
                SignalAction.SELL,
                _bounded((first_move + last_move.copy_abs()) * Decimal("8")),
                "rally-base-drop supply reversal broke below its base",
            )
        return _vote(
            SignalAction.HOLD, Decimal("0.2"), "no fresh rally/drop-base pattern confirmed"
        )


class SupplyDemandAgent(BaseDeterministicAgent):
    name = "supply_demand"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        if len(request.bars) < 24:
            return self._insufficient_history(24, len(request.bars))
        latest_close = request.bars[-1].close.value
        demand_zones: list[tuple[Decimal, Decimal, Decimal]] = []
        supply_zones: list[tuple[Decimal, Decimal, Decimal]] = []
        window = request.bars[-80:]
        for index in range(3, len(window) - 3):
            base = window[index : index + 3]
            departure = window[index + 3 : index + 6]
            base_low = min(bar.low.value for bar in base)
            base_high = max(bar.high.value for bar in base)
            if _zone_width(base_low, base_high) > Decimal("0.03"):
                continue
            departure_return = _segment_return(departure)
            strength = _bounded(departure_return.copy_abs() * Decimal("8"))
            if departure_return > Decimal("0.015"):
                demand_zones.append((base_low, base_high, strength))
            elif departure_return < Decimal("-0.015"):
                supply_zones.append((base_low, base_high, strength))

        demand = _nearest_zone(latest_close, demand_zones)
        if demand is not None:
            low, high, strength = demand
            return _vote(
                SignalAction.BUY,
                max(strength, Decimal("0.45")),
                f"price is retesting demand zone {low:.2f}-{high:.2f}",
            )
        supply = _nearest_zone(latest_close, supply_zones)
        if supply is not None:
            low, high, strength = supply
            return _vote(
                SignalAction.SELL,
                max(strength, Decimal("0.45")),
                f"price is retesting supply zone {low:.2f}-{high:.2f}",
            )
        return _vote(
            SignalAction.HOLD, Decimal("0.2"), "price is not retesting a fresh supply/demand zone"
        )


class MarketRegimeAgent(BaseDeterministicAgent):
    name = "market_regime"

    def _evaluate(self, request: AgentRequest) -> AgentEvaluation:
        closes = _closes(request.bars)
        if len(closes) < 200:
            return self._insufficient_history(200, len(closes))
        fast = _mean(closes[-50:])
        slow = _mean(closes[-200:])
        spread = _bounded((fast - slow) / slow * Decimal("5"))
        if fast > slow:
            return _vote(SignalAction.BUY, spread, "50-day average is above 200-day regime average")
        if fast < slow:
            return _vote(
                SignalAction.SELL,
                spread.copy_abs(),
                "50-day average is below 200-day regime average",
            )
        return _vote(SignalAction.HOLD, Decimal("0.1"), "market regime averages are flat")


def _segment_return(bars: Sequence[Bar]) -> Decimal:
    first_open = bars[0].open.value
    if first_open <= DECIMAL_ZERO:
        return DECIMAL_ZERO
    return bars[-1].close.value / first_open - DECIMAL_ONE


def _zone_width(low: Decimal, high: Decimal) -> Decimal:
    midpoint = (low + high) / Decimal("2")
    if midpoint <= DECIMAL_ZERO:
        return DECIMAL_ONE
    return (high - low) / midpoint


def _nearest_zone(
    price: Decimal, zones: Sequence[tuple[Decimal, Decimal, Decimal]]
) -> tuple[Decimal, Decimal, Decimal] | None:
    if price <= DECIMAL_ZERO:
        return None
    candidates = [
        zone for zone in zones if zone[0] * Decimal("0.985") <= price <= zone[1] * Decimal("1.015")
    ]
    if not candidates:
        return None
    return min(
        candidates, key=lambda zone: min((price - zone[0]).copy_abs(), (price - zone[1]).copy_abs())
    )


def _vote(action: SignalAction, confidence: Decimal, reason: str) -> AgentEvaluation:
    bounded_confidence = _bounded(confidence.copy_abs())
    score = _score_for_action(action, bounded_confidence)
    return action, bounded_confidence, score, (reason,)


def _score_for_action(action: SignalAction, confidence: Decimal) -> Decimal:
    if action is SignalAction.BUY:
        return confidence
    if action is SignalAction.SELL:
        return -confidence
    return DECIMAL_ZERO


def _closes(bars: Sequence[Bar]) -> tuple[Decimal, ...]:
    return tuple(bar.close.value for bar in bars)


def _mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, DECIMAL_ZERO) / Decimal(len(values))


def _realized_volatility(closes: Sequence[Decimal]) -> Decimal:
    returns = tuple(
        closes[index] / closes[index - 1] - DECIMAL_ONE for index in range(1, len(closes))
    )
    if not returns:
        return DECIMAL_ZERO
    mean_return = _mean(returns)
    variance = _mean(tuple((value - mean_return) ** 2 for value in returns))
    return variance.sqrt()


def _max_drawdown(closes: Sequence[Decimal]) -> Decimal:
    peak = closes[0]
    max_drawdown = DECIMAL_ZERO
    for close in closes:
        peak = max(peak, close)
        drawdown = close / peak - DECIMAL_ONE
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def _z_score(value: Decimal, values: Sequence[Decimal]) -> Decimal:
    mean_value = _mean(values)
    variance = _mean(tuple((item - mean_value) ** 2 for item in values))
    standard_deviation = variance.sqrt()
    if standard_deviation == DECIMAL_ZERO:
        return DECIMAL_ZERO
    return (value - mean_value) / standard_deviation


def _bounded(value: Decimal) -> Decimal:
    if value < DECIMAL_ZERO:
        return DECIMAL_ZERO
    if value > DECIMAL_ONE:
        return DECIMAL_ONE
    return value
