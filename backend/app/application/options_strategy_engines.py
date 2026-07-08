"""Deterministic strategy engines that produce signals before AI ranking."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from backend.app.domain.entities import Bar
from backend.app.domain.enums import SignalAction
from backend.app.domain.options import OptionContract, OptionType

MIN_REWARD_RISK = Decimal("2")
MAX_RISK_FRACTION = Decimal("0.01")
CONTRACT_MULTIPLIER = Decimal("100")
MOMENTUM_LOOKBACK_BARS = 22
MIN_FLOW_VOLUME = 100
MIN_GAMMA_OPEN_INTEREST = 500
VWAP_LOOKBACK_BARS = 20
RELATIVE_STRENGTH_LOOKBACK_BARS = 63
MIN_SPREAD_LEGS = 2


@dataclass(frozen=True, slots=True)
class StrategyEngineSignal:
    engine: str
    action: SignalAction
    confidence: Decimal
    rationale: str
    legs: tuple[str, ...]
    risk_reward: Decimal | None
    max_loss: Decimal | None
    target_return: Decimal | None
    position_contracts: int
    tradable: bool


@dataclass(frozen=True, slots=True)
class StrategyEngineContext:
    symbol: str
    underlying_price: Decimal
    contracts: Sequence[OptionContract]
    bars: Sequence[Bar]
    account_equity: Decimal = Decimal("10000")


class StrategyEngine(Protocol):
    name: str

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal: ...


class SpyQqqMomentumEngine:
    name = "spy_qqq_momentum"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        if context.symbol not in {"SPY", "QQQ"} or len(context.bars) < MOMENTUM_LOOKBACK_BARS:
            return _hold(self.name, "SPY/QQQ momentum requires SPY or QQQ and 22 bars")
        ret = context.bars[-1].close.value / context.bars[
            -MOMENTUM_LOOKBACK_BARS
        ].close.value - Decimal("1")
        if ret > Decimal("0.02"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.CALL,
                ret * Decimal("10"),
                "21-day SPY/QQQ momentum is positive",
            )
        if ret < Decimal("-0.02"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.PUT,
                ret.copy_abs() * Decimal("10"),
                "21-day SPY/QQQ momentum is negative",
            )
        return _hold(self.name, "SPY/QQQ momentum is neutral")


class UnusualOptionsFlowEngine:
    name = "unusual_options_flow"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        liquid = [
            c for c in context.contracts if c.volume >= MIN_FLOW_VOLUME and c.open_interest > 0
        ]
        if not liquid:
            return _hold(self.name, "no liquid option flow candidates")
        best = max(liquid, key=lambda c: (c.volume_open_interest_ratio, c.volume))
        if best.volume_open_interest_ratio < Decimal("1"):
            return _hold(self.name, "no contract traded at least 1x open interest")
        action = SignalAction.BUY if best.option_type is OptionType.CALL else SignalAction.SELL
        return _risk_checked_signal(
            engine=self.name,
            action=action,
            confidence=min(best.volume_open_interest_ratio / Decimal("3"), Decimal("1")),
            rationale=f"{best.contract_symbol} volume/OI {best.volume_open_interest_ratio:.2f}",
            legs=(best.contract_symbol,),
            debit=_entry_price(best),
            account_equity=context.account_equity,
        )


class GammaExposureEngine:
    name = "gamma_exposure"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        near = [
            c
            for c in context.contracts
            if abs(c.strike - context.underlying_price) / context.underlying_price
            <= Decimal("0.03")
        ]
        call_oi = sum(c.open_interest for c in near if c.option_type is OptionType.CALL)
        put_oi = sum(c.open_interest for c in near if c.option_type is OptionType.PUT)
        if call_oi + put_oi < MIN_GAMMA_OPEN_INTEREST:
            return _hold(self.name, "not enough near-spot open interest for gamma signal")
        if call_oi > put_oi * 2:
            return _single_leg_signal(
                context,
                self.name,
                OptionType.CALL,
                Decimal("0.7"),
                "call-side near-spot OI dominates",
            )
        if put_oi > call_oi * 2:
            return _single_leg_signal(
                context,
                self.name,
                OptionType.PUT,
                Decimal("0.7"),
                "put-side near-spot OI dominates",
            )
        return _hold(self.name, "near-spot gamma exposure is balanced")


class VwapTrendEngine:
    name = "vwap_trend"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        if len(context.bars) < VWAP_LOOKBACK_BARS:
            return _hold(self.name, "VWAP trend requires 20 bars")
        window = context.bars[-VWAP_LOOKBACK_BARS:]
        volume = sum((Decimal(bar.volume) for bar in window), Decimal("0"))
        if volume <= 0:
            return _hold(self.name, "volume is zero")
        vwap = sum((bar.close.value * Decimal(bar.volume) for bar in window), Decimal("0")) / volume
        latest = context.bars[-1].close.value
        if latest > vwap * Decimal("1.01"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.CALL,
                Decimal("0.6"),
                "price is above 20-bar volume-weighted trend",
            )
        if latest < vwap * Decimal("0.99"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.PUT,
                Decimal("0.6"),
                "price is below 20-bar volume-weighted trend",
            )
        return _hold(self.name, "price is near VWAP trend")


class RelativeStrengthEngine:
    name = "relative_strength"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        if len(context.bars) < RELATIVE_STRENGTH_LOOKBACK_BARS:
            return _hold(self.name, "relative strength requires 63 bars")
        ret = context.bars[-1].close.value / context.bars[
            -RELATIVE_STRENGTH_LOOKBACK_BARS
        ].close.value - Decimal("1")
        if ret > Decimal("0.08"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.CALL,
                Decimal("0.65"),
                "63-day relative strength is positive",
            )
        if ret < Decimal("-0.08"):
            return _single_leg_signal(
                context,
                self.name,
                OptionType.PUT,
                Decimal("0.65"),
                "63-day relative strength is negative",
            )
        return _hold(self.name, "relative strength is not decisive")


class SpreadScannerEngine:
    name = "credit_debit_spread_scanner"

    def evaluate(self, context: StrategyEngineContext) -> StrategyEngineSignal:
        calls = sorted(
            (c for c in context.contracts if c.option_type is OptionType.CALL and c.ask),
            key=lambda c: c.strike,
        )
        if len(calls) < MIN_SPREAD_LEGS:
            return _hold(self.name, "not enough call strikes for spread scan")
        long_leg = min(calls, key=lambda c: abs(c.strike - context.underlying_price))
        higher = next((c for c in calls if c.strike > long_leg.strike and c.bid), None)
        if higher is None:
            return _hold(self.name, "no higher call strike with bid for debit spread")
        debit = _entry_price(long_leg) - _entry_price(higher)
        width = higher.strike - long_leg.strike
        if debit <= 0 or width <= debit:
            return _hold(self.name, "debit spread pricing is not viable")
        target_return = (width - debit) / debit
        return _risk_checked_signal(
            engine=self.name,
            action=SignalAction.BUY,
            confidence=min(target_return / Decimal("2"), Decimal("1")),
            rationale="ATM call debit spread offers defined risk/reward",
            legs=(f"BUY {long_leg.contract_symbol}", f"SELL {higher.contract_symbol}"),
            debit=debit,
            account_equity=context.account_equity,
            target_return=target_return,
        )


DEFAULT_STRATEGY_ENGINES: tuple[StrategyEngine, ...] = (
    SpyQqqMomentumEngine(),
    UnusualOptionsFlowEngine(),
    GammaExposureEngine(),
    VwapTrendEngine(),
    RelativeStrengthEngine(),
    SpreadScannerEngine(),
)


def run_strategy_engines(context: StrategyEngineContext) -> tuple[StrategyEngineSignal, ...]:
    return tuple(engine.evaluate(context) for engine in DEFAULT_STRATEGY_ENGINES)


def _hold(engine: str, rationale: str) -> StrategyEngineSignal:
    return StrategyEngineSignal(
        engine, SignalAction.HOLD, Decimal("0"), rationale, (), None, None, None, 0, False
    )


def _single_leg_signal(
    context: StrategyEngineContext,
    engine: str,
    option_type: OptionType,
    confidence: Decimal,
    rationale: str,
) -> StrategyEngineSignal:
    candidates = [
        c for c in context.contracts if c.option_type is option_type and _entry_price(c) > 0
    ]
    if not candidates:
        return _hold(engine, f"{rationale}; no liquid {option_type.value} contract")
    contract = min(candidates, key=lambda c: abs(c.strike - context.underlying_price))
    return _risk_checked_signal(
        engine=engine,
        action=SignalAction.BUY if option_type is OptionType.CALL else SignalAction.SELL,
        confidence=min(confidence, Decimal("1")),
        rationale=rationale,
        legs=(contract.contract_symbol,),
        debit=_entry_price(contract),
        account_equity=context.account_equity,
    )


def _risk_checked_signal(
    engine: str,
    action: SignalAction,
    confidence: Decimal,
    rationale: str,
    legs: tuple[str, ...],
    debit: Decimal,
    account_equity: Decimal,
    target_return: Decimal = Decimal("1"),
) -> StrategyEngineSignal:
    max_loss = debit * CONTRACT_MULTIPLIER
    risk_budget = account_equity * MAX_RISK_FRACTION
    contracts = int(risk_budget // max_loss) if max_loss > 0 else 0
    risk_reward = target_return
    tradable = contracts > 0 and risk_reward >= MIN_REWARD_RISK / Decimal("2")
    return StrategyEngineSignal(
        engine=engine,
        action=action,
        confidence=confidence,
        rationale=rationale,
        legs=legs,
        risk_reward=risk_reward,
        max_loss=max_loss,
        target_return=target_return,
        position_contracts=contracts,
        tradable=tradable,
    )


def _entry_price(contract: OptionContract) -> Decimal:
    if (
        contract.ask is not None
        and contract.bid is not None
        and contract.ask > 0
        and contract.bid > 0
    ):
        return (contract.ask + contract.bid) / Decimal("2")
    return contract.last_price or Decimal("0")
