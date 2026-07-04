"""Forward-looking options paper ledger — real chain quotes only, no modeling.

Unlike the Black-Scholes-modeled backtester, this ledger never invents a
premium: it opens a position at the real last-traded (or bid/ask mid) price
from the live Yahoo options chain, marks open positions using a fresh chain
lookup, and settles a position at expiration using the real underlying close
(intrinsic value) once the contract has rolled off the chain. The track record
only grows forward from whenever this is first run — there is no way to
backfill it, because no historical options-quote data source exists (see
``options_pricing.py``).

State lives in memory for the lifetime of the running process, the same
pattern the existing stock ``PaperBroker`` already uses in this codebase — a
restart clears it. Durable cross-restart storage would reuse the Postgres/
Alembic scaffolding already in this repo, but that is not implemented for any
feature yet (the stock paper broker is not persisted either) and is a natural
follow-up rather than something this session could verify without a live
database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from backend.app.application.market_data import MarketDataService
from backend.app.application.options_backtesting import OptionsStyle
from backend.app.application.options_pricing import OptionSide, intrinsic_value
from backend.app.application.options_research import OptionsResearchService
from backend.app.application.portfolio_execution import instrument_id
from backend.app.domain.options import OptionContract, OptionsProvider
from backend.app.domain.providers import HistoricalMarketDataRequest

CONTRACT_MULTIPLIER = Decimal("100")
PREMIUM_BUDGET_FRACTION = Decimal("0.20")


@dataclass(frozen=True, slots=True)
class OpenLedgerPosition:
    id: UUID
    symbol: str
    style: OptionsStyle
    option_side: OptionSide
    contract_symbol: str
    strike: Decimal
    expiration: date
    opened_at: datetime
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    entry_reason: str


@dataclass(frozen=True, slots=True)
class ClosedLedgerPosition:
    id: UUID
    symbol: str
    style: OptionsStyle
    option_side: OptionSide
    contract_symbol: str
    strike: Decimal
    expiration: date
    opened_at: datetime
    entry_underlying: Decimal
    entry_premium: Decimal
    contracts: int
    entry_reason: str
    closed_at: datetime
    exit_underlying: Decimal
    exit_premium: Decimal
    realized_pnl: Decimal
    settlement: str


@dataclass(frozen=True, slots=True)
class MarkedPosition:
    position: OpenLedgerPosition
    mark_premium: Decimal | None
    unrealized_pnl: Decimal | None


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    open_positions: tuple[MarkedPosition, ...]
    closed_positions: tuple[ClosedLedgerPosition, ...]
    cash_by_symbol: dict[str, Decimal]


def _real_premium(last_price: Decimal | None, bid: Decimal | None, ask: Decimal | None) -> Decimal:
    if last_price is not None and last_price > Decimal("0"):
        return last_price
    if bid is not None and ask is not None and bid > Decimal("0") and ask > Decimal("0"):
        return (bid + ask) / Decimal("2")
    return Decimal("0")


@dataclass(slots=True)
class OptionsForwardLedgerService:
    """In-memory, real-quote-only options paper-trading ledger for one process."""

    options: OptionsProvider
    market_data: MarketDataService
    cash_by_symbol: dict[str, Decimal] = field(default_factory=dict)
    open_positions: dict[UUID, OpenLedgerPosition] = field(default_factory=dict)
    closed_positions: list[ClosedLedgerPosition] = field(default_factory=list)

    def ensure_symbol(self, symbol: str, allocated_capital: Decimal) -> None:
        self.cash_by_symbol.setdefault(symbol.upper(), allocated_capital)

    def has_open_position(self, symbol: str, style: OptionsStyle) -> bool:
        symbol = symbol.upper()
        return any(
            position.symbol == symbol and position.style is style
            for position in self.open_positions.values()
        )

    def open_if_signal(
        self, symbol: str, style: OptionsStyle, max_dte: int
    ) -> OpenLedgerPosition | None:
        symbol = symbol.upper()
        if self.has_open_position(symbol, style):
            return None

        research = OptionsResearchService(
            options=self.options, market_data=self.market_data
        ).research(symbol, max_dte=max_dte)
        if not research.planned_trades:
            return None

        plan = research.planned_trades[0]
        contract = plan.contract
        premium = _real_premium(contract.last_price, contract.bid, contract.ask)
        if premium <= Decimal("0"):
            return None

        cash = self.cash_by_symbol.get(symbol, Decimal("0"))
        contract_cost = premium * CONTRACT_MULTIPLIER
        budget = cash * PREMIUM_BUDGET_FRACTION
        contracts = int(budget // contract_cost) if contract_cost > Decimal("0") else 0
        if contracts < 1:
            if cash >= contract_cost:
                contracts = 1
            else:
                return None

        total_cost = contract_cost * Decimal(contracts)
        if total_cost > cash:
            return None

        self.cash_by_symbol[symbol] = cash - total_cost
        position = OpenLedgerPosition(
            id=uuid4(),
            symbol=symbol,
            style=style,
            option_side=OptionSide(contract.option_type.value),
            contract_symbol=contract.contract_symbol,
            strike=contract.strike,
            expiration=contract.expiration,
            opened_at=datetime.now(UTC),
            entry_underlying=research.underlying_price,
            entry_premium=premium,
            contracts=contracts,
            entry_reason=plan.rationale,
        )
        self.open_positions[position.id] = position
        return position

    def tick(self) -> tuple[ClosedLedgerPosition, ...]:
        """Settle every open position whose contract has matured or delisted."""

        today = datetime.now(UTC).date()
        by_symbol: dict[str, list[OpenLedgerPosition]] = {}
        for position in self.open_positions.values():
            by_symbol.setdefault(position.symbol, []).append(position)

        closed_now: list[ClosedLedgerPosition] = []
        for symbol, positions in by_symbol.items():
            live_contract_symbols = self._live_contract_symbols(symbol)
            for position in positions:
                still_listed = position.contract_symbol in live_contract_symbols
                if position.expiration > today and still_listed:
                    continue
                closed_now.append(self._settle(position, today))
        return tuple(closed_now)

    def mark_open_positions(self) -> tuple[MarkedPosition, ...]:
        """Mark every open position at its current real chain quote (no settlement)."""

        by_symbol: dict[str, list[OpenLedgerPosition]] = {}
        for position in self.open_positions.values():
            by_symbol.setdefault(position.symbol, []).append(position)

        marks: list[MarkedPosition] = []
        for symbol, positions in by_symbol.items():
            chain_by_contract = self._chain_by_contract(symbol)
            for position in positions:
                contract = chain_by_contract.get(position.contract_symbol)
                if contract is None:
                    marks.append(MarkedPosition(position, None, None))
                    continue
                mark = _real_premium(contract.last_price, contract.bid, contract.ask)
                pnl_multiplier = CONTRACT_MULTIPLIER * Decimal(position.contracts)
                unrealized = (
                    (mark - position.entry_premium) * pnl_multiplier
                    if mark > Decimal("0")
                    else None
                )
                marks.append(MarkedPosition(position, mark, unrealized))
        return tuple(marks)

    def snapshot(self) -> LedgerSnapshot:
        return LedgerSnapshot(
            open_positions=self.mark_open_positions(),
            closed_positions=tuple(self.closed_positions),
            cash_by_symbol=dict(self.cash_by_symbol),
        )

    def _live_contract_symbols(self, symbol: str) -> frozenset[str]:
        try:
            chain = self.options.fetch_option_chain(symbol, max_expiries=4)
        except Exception:  # noqa: BLE001 - provider outage means "treat as delisted/settle"
            return frozenset()
        return frozenset(contract.contract_symbol for contract in chain.contracts)

    def _chain_by_contract(self, symbol: str) -> dict[str, OptionContract]:
        try:
            chain = self.options.fetch_option_chain(symbol, max_expiries=4)
        except Exception:  # noqa: BLE001
            return {}
        return {contract.contract_symbol: contract for contract in chain.contracts}

    def _settle(self, position: OpenLedgerPosition, today: date) -> ClosedLedgerPosition:
        request = HistoricalMarketDataRequest(
            instrument_id=instrument_id(position.symbol),
            symbol=position.symbol,
            start=position.expiration - timedelta(days=7),
            end=today + timedelta(days=1),
        )
        bars = self.market_data.fetch_daily_history(request).bars
        settlement_bar = next(
            (bar for bar in reversed(bars) if bar.timestamp.date() <= position.expiration),
            bars[-1],
        )
        exit_underlying = settlement_bar.close.value
        exit_premium = intrinsic_value(exit_underlying, position.strike, position.option_side)
        proceeds = exit_premium * CONTRACT_MULTIPLIER * Decimal(position.contracts)
        entry_cost = position.entry_premium * CONTRACT_MULTIPLIER * Decimal(position.contracts)
        realized_pnl = proceeds - entry_cost

        self.cash_by_symbol[position.symbol] = (
            self.cash_by_symbol.get(position.symbol, Decimal("0")) + proceeds
        )
        del self.open_positions[position.id]

        closed = ClosedLedgerPosition(
            id=position.id,
            symbol=position.symbol,
            style=position.style,
            option_side=position.option_side,
            contract_symbol=position.contract_symbol,
            strike=position.strike,
            expiration=position.expiration,
            opened_at=position.opened_at,
            entry_underlying=position.entry_underlying,
            entry_premium=position.entry_premium,
            contracts=position.contracts,
            entry_reason=position.entry_reason,
            closed_at=datetime.now(UTC),
            exit_underlying=exit_underlying,
            exit_premium=exit_premium,
            realized_pnl=realized_pnl,
            settlement="real_underlying_intrinsic_settlement",
        )
        self.closed_positions.append(closed)
        return closed


def total_realized_pnl(closed_positions: Sequence[ClosedLedgerPosition]) -> Decimal:
    return sum((position.realized_pnl for position in closed_positions), Decimal("0"))
