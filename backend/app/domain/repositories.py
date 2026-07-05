"""Repository contracts owned by the domain/application boundary."""

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from backend.app.domain.entities import (
    AgentSignal,
    BacktestRun,
    Bar,
    CorporateAction,
    Instrument,
    MasterDecision,
    Order,
    Portfolio,
    Trade,
)


class InstrumentRepository(Protocol):
    def get_by_symbol(self, symbol: str) -> Instrument | None: ...

    def save(self, instrument: Instrument) -> None: ...


class MarketDataRepository(Protocol):
    def get_bars(self, instrument_id: UUID, start: date, end: date) -> Sequence[Bar]: ...

    def save_bars(self, bars: Sequence[Bar]) -> None: ...

    def save_corporate_actions(self, actions: Sequence[CorporateAction]) -> None: ...


class SignalRepository(Protocol):
    def save_agent_signal(self, signal: AgentSignal) -> None: ...

    def save_master_decision(self, decision: MasterDecision) -> None: ...


class ExecutionRepository(Protocol):
    def save_order(self, order: Order) -> None: ...

    def save_trade(self, trade: Trade) -> None: ...


class PortfolioRepository(Protocol):
    def get(self, portfolio_id: UUID) -> Portfolio | None: ...

    def save(self, portfolio: Portfolio) -> None: ...


class BacktestRepository(Protocol):
    def save_run(self, run: BacktestRun) -> None: ...
