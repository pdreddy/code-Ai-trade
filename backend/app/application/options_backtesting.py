"""Event-driven options backtester for 0DTE and weekly strategies.

Reuses the same AI agents and master-decision engine that drive the equity
strategy: a BUY decision opens a call, a SELL decision opens a put, in the
nearest 0DTE (same-day) or weekly (next Friday) expiry, sized at next-open.
The position is marked to market daily with Black-Scholes and closed either at
expiration (intrinsic value) or when the signal flips against it.

Premiums are theoretical — see ``options_pricing`` for why — priced off real
historical underlying closes with a realized-volatility proxy. Everything else
(underlying prices, strike selection, expiration calendar, the AI signal that
picks direction and timing) is real. Every result from this module must be
surfaced as a *modeled* backtest, never confused with quoted market prices.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from backend.app.application.decision_engine import (
    MasterDecisionEngine,
    MasterDecisionRequest,
)
from backend.app.application.options_pricing import (
    BlackScholesInputs,
    OptionSide,
    black_scholes_price,
    intrinsic_value,
    realized_volatility,
    round_to_strike_increment,
)
from backend.app.domain.agents import AgentRequest, TradingAgent
from backend.app.domain.entities import Bar, MasterDecision
from backend.app.domain.enums import SignalAction
from backend.app.domain.errors import DomainValidationError
from backend.app.domain.value_objects import Price

# Mirrors strategy_backtest.py: the most history-hungry agent looks back 200
# bars, so a bounded trailing window gives identical votes to the full history.
AGENT_LOOKBACK_BARS = 220
VOL_LOOKBACK_DAYS = 20
RISK_FREE_RATE = Decimal("0.05")
# Fraction of current cash committed as premium budget per new position; keeps a
# single 0DTE trade from being able to wipe out the sleeve in one move.
PREMIUM_BUDGET_FRACTION = Decimal("0.20")
CONTRACT_MULTIPLIER = Decimal("100")
COMMISSION_PER_CONTRACT = Decimal("0.65")
MIN_TRADABLE_PREMIUM = Decimal("0.05")
ZERO_DTE_MIN_CONFIDENCE = Decimal("0.38")
ZERO_DTE_MAX_RISK_SCORE = Decimal("0.63")
ZERO_DTE_PREMIUM_BUDGET_FRACTION = Decimal("0.05")
ZERO_DTE_MAX_CONTRACTS = 10
ZERO_DTE_MIN_TARGET_RETURN = Decimal("0.50")
ZERO_DTE_MIN_DAILY_TARGET_RETURN = Decimal("0.20")
ZERO_DTE_MIN_REWARD_RISK = Decimal("2")
MIN_BAR_COUNT = 30


class OptionsStyle(StrEnum):
    ZERO_DTE = "zero_dte"
    WEEKLY = "weekly"


@dataclass(frozen=True, slots=True)
class OptionsTrade:
    id: UUID
    option_side: OptionSide
    strike: Decimal
    expiration: date
    entry_at: date
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    exit_at: date
    exit_underlying: Decimal
    exit_premium: Decimal
    realized_pnl: Decimal
    entry_reason: str
    exit_reason: str


@dataclass(frozen=True, slots=True)
class OptionsEquityPoint:
    on: date
    equity: Decimal


@dataclass(frozen=True, slots=True)
class OptionsBacktestMetrics:
    win_rate: Decimal
    trade_count: int
    winning_trades: int
    losing_trades: int
    total_return: Decimal
    max_drawdown: Decimal
    profit_factor: Decimal


@dataclass(frozen=True, slots=True)
class OptionsBacktestResult:
    symbol: str
    style: OptionsStyle
    initial_capital: Decimal
    final_equity: Decimal
    trades: tuple[OptionsTrade, ...]
    equity_curve: tuple[OptionsEquityPoint, ...]
    metrics: OptionsBacktestMetrics
    next_signal: MasterDecision | None


@dataclass(slots=True)
class _OpenPosition:
    id: UUID
    option_side: OptionSide
    strike: Decimal
    expiration: date
    entry_at: date
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    entry_reason: str
    stop_underlying: Decimal | None
    take_profit_underlying: Decimal | None


def _signal_flips(option_side: OptionSide, action: SignalAction) -> bool:
    if option_side is OptionSide.CALL and action is SignalAction.SELL:
        return True
    return option_side is OptionSide.PUT and action is SignalAction.BUY


@dataclass(slots=True)
class OptionsBacktester:
    agents: tuple[TradingAgent, ...]
    engine: MasterDecisionEngine
    style: OptionsStyle
    initial_capital: Decimal
    risk_free_rate: Decimal = RISK_FREE_RATE
    premium_budget_fraction: Decimal = PREMIUM_BUDGET_FRACTION

    def run(self, instrument_id: UUID, symbol: str, bars: Sequence[Bar]) -> OptionsBacktestResult:
        if len(bars) < MIN_BAR_COUNT:
            raise DomainValidationError(f"options backtest requires at least {MIN_BAR_COUNT} bars")

        cash = self.initial_capital
        position: _OpenPosition | None = None
        trades: list[OptionsTrade] = []
        equity_curve: list[OptionsEquityPoint] = []
        closes: list[Decimal] = []
        last_decision: MasterDecision | None = None

        for index, bar in enumerate(bars):
            closes.append(bar.close.value)
            today = bar.timestamp.date()

            if position is not None and today >= position.expiration:
                cash, closed = self._close_position(
                    cash, position, bar, closes, exit_reason="expired", at_expiration=True
                )
                trades.append(closed)
                position = None

            decision = self._decide(instrument_id, bars, index)
            last_decision = decision

            if position is not None and _signal_flips(position.option_side, decision.action):
                cash, closed = self._close_position(
                    cash,
                    position,
                    bar,
                    closes,
                    exit_reason=decision.explanation,
                    at_expiration=False,
                )
                trades.append(closed)
                position = None

            equity_curve.append(
                OptionsEquityPoint(today, cash + self._mark_position(position, bar, closes))
            )

            can_enter = decision.action is not SignalAction.HOLD and index + 1 < len(bars)
            if position is None and can_enter:
                cash, position = self._open_position(cash, decision, bars[index + 1], closes)

        if position is not None:
            cash, closed = self._close_position(
                cash,
                position,
                bars[-1],
                closes,
                exit_reason="backtest window ended",
                at_expiration=False,
            )
            trades.append(closed)

        final_equity = equity_curve[-1].equity if equity_curve else self.initial_capital
        metrics = _compute_metrics(self.initial_capital, final_equity, trades, equity_curve)
        return OptionsBacktestResult(
            symbol=symbol,
            style=self.style,
            initial_capital=self.initial_capital,
            final_equity=final_equity,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            metrics=metrics,
            next_signal=last_decision,
        )

    def _decide(self, instrument_id: UUID, bars: Sequence[Bar], index: int) -> MasterDecision:
        window_start = max(0, index + 1 - AGENT_LOOKBACK_BARS)
        window = bars[window_start : index + 1]
        evaluated_at = bars[index].timestamp
        request = AgentRequest(instrument_id=instrument_id, bars=window, evaluated_at=evaluated_at)
        votes = tuple(agent.evaluate(request) for agent in self.agents)
        return self.engine.decide(
            MasterDecisionRequest(
                instrument_id=instrument_id,
                votes=votes,
                current_price=Price(bars[index].close.value),
                generated_at=evaluated_at,
            )
        )

    def _expiration_for(self, entry_date: date) -> date:
        if self.style is OptionsStyle.ZERO_DTE:
            return entry_date
        # Weekly: the next Friday on/after entry_date (a Friday entry expires the
        # same day, mirroring how real Friday weeklies behave).
        days_until_friday = (4 - entry_date.weekday()) % 7
        return entry_date + timedelta(days=days_until_friday)

    def _open_position(
        self,
        cash: Decimal,
        decision: MasterDecision,
        entry_bar: Bar,
        closes: list[Decimal],
    ) -> tuple[Decimal, _OpenPosition | None]:
        entry_date = entry_bar.timestamp.date()
        expiration = self._expiration_for(entry_date)
        if self.style is OptionsStyle.ZERO_DTE and not _zero_dte_setup_allowed(decision):
            return cash, None
        spot = entry_bar.open.value
        strike = round_to_strike_increment(spot)
        side = OptionSide.CALL if decision.action is SignalAction.BUY else OptionSide.PUT
        years_to_expiry = Decimal(max((expiration - entry_date).days, 0)) / Decimal("365")
        sigma = realized_volatility(closes, lookback=VOL_LOOKBACK_DAYS)
        premium = black_scholes_price(
            BlackScholesInputs(
                spot=spot,
                strike=strike,
                years_to_expiry=years_to_expiry,
                risk_free_rate=self.risk_free_rate,
                volatility=sigma,
                side=side,
            )
        )
        if premium < MIN_TRADABLE_PREMIUM:
            return cash, None
        if self.style is OptionsStyle.ZERO_DTE and not _zero_dte_reward_plan_allowed(
            decision=decision,
            entry_premium=premium,
            strike=strike,
            side=side,
        ):
            return cash, None

        contract_cost = premium * CONTRACT_MULTIPLIER
        round_trip_commission = COMMISSION_PER_CONTRACT * Decimal("2")
        per_contract_budget = contract_cost + round_trip_commission
        premium_budget = cash * self._effective_premium_budget_fraction()
        contracts = (
            int(premium_budget // per_contract_budget) if per_contract_budget > Decimal("0") else 0
        )
        if contracts < 1:
            if cash >= per_contract_budget:
                contracts = 1
            else:
                return cash, None
        if self.style is OptionsStyle.ZERO_DTE:
            contracts = min(contracts, ZERO_DTE_MAX_CONTRACTS)

        total_cost = (contract_cost + COMMISSION_PER_CONTRACT) * Decimal(contracts)
        if total_cost > cash:
            return cash, None

        return cash - total_cost, _OpenPosition(
            id=uuid4(),
            option_side=side,
            strike=strike,
            expiration=expiration,
            entry_at=entry_date,
            entry_underlying=spot,
            entry_premium=premium,
            contracts=contracts,
            entry_reason=decision.explanation,
            stop_underlying=decision.stop_loss.value if decision.stop_loss else None,
            take_profit_underlying=decision.take_profit.value if decision.take_profit else None,
        )

    def _effective_premium_budget_fraction(self) -> Decimal:
        if self.style is OptionsStyle.ZERO_DTE:
            return min(self.premium_budget_fraction, ZERO_DTE_PREMIUM_BUDGET_FRACTION)
        return self.premium_budget_fraction

    def _mark_position(
        self, position: _OpenPosition | None, bar: Bar, closes: list[Decimal]
    ) -> Decimal:
        if position is None:
            return Decimal("0")
        today = bar.timestamp.date()
        years_remaining = Decimal(max((position.expiration - today).days, 0)) / Decimal("365")
        sigma = realized_volatility(closes, lookback=VOL_LOOKBACK_DAYS)
        mark_premium = black_scholes_price(
            BlackScholesInputs(
                spot=bar.close.value,
                strike=position.strike,
                years_to_expiry=years_remaining,
                risk_free_rate=self.risk_free_rate,
                volatility=sigma,
                side=position.option_side,
            )
        )
        return mark_premium * CONTRACT_MULTIPLIER * Decimal(position.contracts)

    def _close_position(
        self,
        cash: Decimal,
        position: _OpenPosition,
        bar: Bar,
        closes: list[Decimal],
        exit_reason: str,
        at_expiration: bool,
    ) -> tuple[Decimal, OptionsTrade]:
        today = bar.timestamp.date()
        exit_underlying = bar.close.value
        adjusted_exit_reason = exit_reason
        if at_expiration:
            exit_underlying, adjusted_exit_reason = _zero_dte_underlying_exit(
                position, bar, exit_reason
            )
            exit_premium = intrinsic_value(exit_underlying, position.strike, position.option_side)
        else:
            years_remaining = Decimal(max((position.expiration - today).days, 0)) / Decimal("365")
            exit_premium = black_scholes_price(
                BlackScholesInputs(
                    spot=bar.close.value,
                    strike=position.strike,
                    years_to_expiry=years_remaining,
                    risk_free_rate=self.risk_free_rate,
                    volatility=realized_volatility(closes, lookback=VOL_LOOKBACK_DAYS),
                    side=position.option_side,
                )
            )
        proceeds = (exit_premium * CONTRACT_MULTIPLIER - COMMISSION_PER_CONTRACT) * Decimal(
            position.contracts
        )
        entry_cost = (
            position.entry_premium * CONTRACT_MULTIPLIER + COMMISSION_PER_CONTRACT
        ) * Decimal(position.contracts)
        trade = OptionsTrade(
            id=position.id,
            option_side=position.option_side,
            strike=position.strike,
            expiration=position.expiration,
            entry_at=position.entry_at,
            entry_underlying=position.entry_underlying,
            entry_premium=position.entry_premium,
            contracts=position.contracts,
            exit_at=today,
            exit_underlying=exit_underlying,
            exit_premium=exit_premium,
            realized_pnl=proceeds - entry_cost,
            entry_reason=position.entry_reason,
            exit_reason=adjusted_exit_reason,
        )
        return cash + proceeds, trade


def _zero_dte_setup_allowed(decision: MasterDecision) -> bool:
    return (
        decision.confidence.value >= ZERO_DTE_MIN_CONFIDENCE
        and decision.risk_score.value <= ZERO_DTE_MAX_RISK_SCORE
        and decision.expected_r_multiple >= Decimal("1.5")
    )


def _zero_dte_reward_plan_allowed(
    decision: MasterDecision, entry_premium: Decimal, strike: Decimal, side: OptionSide
) -> bool:
    if decision.stop_loss is None or decision.take_profit is None or entry_premium <= Decimal("0"):
        return False
    target_premium = intrinsic_value(decision.take_profit.value, strike, side)
    stop_premium = intrinsic_value(decision.stop_loss.value, strike, side)
    target_return = target_premium / entry_premium - Decimal("1")
    planned_risk = max(entry_premium - stop_premium, Decimal("0"))
    planned_reward = target_premium - entry_premium
    reward_risk = planned_reward / planned_risk if planned_risk > Decimal("0") else Decimal("0")
    return (
        target_return >= ZERO_DTE_MIN_TARGET_RETURN
        and target_return >= ZERO_DTE_MIN_DAILY_TARGET_RETURN
        and reward_risk >= ZERO_DTE_MIN_REWARD_RISK
    )


def _zero_dte_underlying_exit(
    position: _OpenPosition, bar: Bar, default_reason: str
) -> tuple[Decimal, str]:
    if position.stop_underlying is None or position.take_profit_underlying is None:
        return bar.close.value, default_reason
    if position.option_side is OptionSide.CALL:
        stopped = bar.low.value <= position.stop_underlying
        targeted = bar.high.value >= position.take_profit_underlying
    else:
        stopped = bar.high.value >= position.stop_underlying
        targeted = bar.low.value <= position.take_profit_underlying
    if stopped:
        return position.stop_underlying, "0DTE underlying stop touched before expiry"
    if targeted:
        return position.take_profit_underlying, "0DTE underlying target touched before expiry"
    return bar.close.value, default_reason


def _compute_metrics(
    initial_capital: Decimal,
    final_equity: Decimal,
    trades: Sequence[OptionsTrade],
    equity_curve: Sequence[OptionsEquityPoint],
) -> OptionsBacktestMetrics:
    realized = [trade.realized_pnl for trade in trades]
    winning = sum(1 for pnl in realized if pnl > Decimal("0"))
    losing = sum(1 for pnl in realized if pnl < Decimal("0"))
    closed = winning + losing
    positive = sum((pnl for pnl in realized if pnl > Decimal("0")), Decimal("0"))
    negative = sum((pnl.copy_abs() for pnl in realized if pnl < Decimal("0")), Decimal("0"))
    return OptionsBacktestMetrics(
        win_rate=Decimal(winning) / Decimal(closed) if closed else Decimal("0"),
        trade_count=len(trades),
        winning_trades=winning,
        losing_trades=losing,
        total_return=(
            final_equity / initial_capital - Decimal("1")
            if initial_capital > Decimal("0")
            else Decimal("0")
        ),
        max_drawdown=_max_drawdown([point.equity for point in equity_curve]),
        profit_factor=positive / negative if negative > Decimal("0") else positive,
    )


def _max_drawdown(values: Sequence[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    peak = values[0]
    worst = Decimal("0")
    for value in values:
        peak = max(peak, value)
        if peak > Decimal("0"):
            worst = min(worst, value / peak - Decimal("1"))
    return worst
