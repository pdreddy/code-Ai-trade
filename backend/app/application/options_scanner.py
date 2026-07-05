"""Cross-universe scanner: real unusual options activity across many symbols.

The single-symbol Options tab already ranks unusual activity for one ticker at
a time. This runs the same research concurrently across a whole universe and
merges the results into one ranked list, so a user can see where the unusual
flow is right now without checking each symbol individually. Real chain data
only; a symbol whose chain can't be fetched surfaces as a per-symbol error.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from decimal import Decimal

from backend.app.application.market_data import MarketDataService
from backend.app.application.options_research import (
    DEFAULT_MAX_DTE,
    OptionsResearch,
    OptionsResearchService,
)
from backend.app.domain.options import OptionContract, OptionsProvider

DEFAULT_TOP_N = 25


@dataclass(frozen=True, slots=True)
class ScannedUnusualContract:
    symbol: str
    contract: OptionContract
    volume_oi_ratio: Decimal
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class ScannedPlannedTrade:
    symbol: str
    contract: OptionContract
    rationale: str


@dataclass(frozen=True, slots=True)
class ScannedOiSkew:
    symbol: str
    call_open_interest: int
    put_open_interest: int
    direction: str
    ratio: Decimal
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class ScannedBreakout:
    symbol: str
    direction: str
    reason: str
    confidence: Decimal


@dataclass(frozen=True, slots=True)
class ScannerError:
    symbol: str
    detail: str


@dataclass(frozen=True, slots=True)
class OptionsScanResult:
    symbols_scanned: int
    unusual_activity: tuple[ScannedUnusualContract, ...]
    oi_skew: tuple[ScannedOiSkew, ...]
    breakouts: tuple[ScannedBreakout, ...]
    planned_trades: tuple[ScannedPlannedTrade, ...]
    errors: tuple[ScannerError, ...]


@dataclass(slots=True)
class OptionsScannerService:
    options: OptionsProvider
    market_data: MarketDataService
    max_workers: int = 10

    def scan(
        self,
        symbols: Sequence[str],
        max_dte: int = DEFAULT_MAX_DTE,
        top_n: int = DEFAULT_TOP_N,
    ) -> OptionsScanResult:
        universe = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        research_service = OptionsResearchService(
            options=self.options, market_data=self.market_data
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            outcomes = list(
                pool.map(lambda symbol: self._research(research_service, symbol, max_dte), universe)
            )

        unusual: list[ScannedUnusualContract] = []
        planned: list[ScannedPlannedTrade] = []
        oi_skew: list[ScannedOiSkew] = []
        breakouts: list[ScannedBreakout] = []
        errors: list[ScannerError] = []
        succeeded = 0
        for symbol, outcome in zip(universe, outcomes, strict=True):
            if isinstance(outcome, ScannerError):
                errors.append(outcome)
                continue
            succeeded += 1
            for item in outcome.unusual_activity:
                unusual.append(
                    ScannedUnusualContract(
                        symbol=symbol,
                        contract=item.contract,
                        volume_oi_ratio=item.volume_oi_ratio,
                        confidence=item.confidence,
                    )
                )
            for plan in outcome.planned_trades:
                planned.append(
                    ScannedPlannedTrade(
                        symbol=symbol, contract=plan.contract, rationale=plan.rationale
                    )
                )
            if outcome.oi_skew is not None:
                oi_skew.append(
                    ScannedOiSkew(
                        symbol=symbol,
                        call_open_interest=outcome.oi_skew.call_open_interest,
                        put_open_interest=outcome.oi_skew.put_open_interest,
                        direction=outcome.oi_skew.direction,
                        ratio=outcome.oi_skew.ratio,
                        confidence=outcome.oi_skew.confidence,
                    )
                )
            if outcome.breakout is not None:
                breakouts.append(
                    ScannedBreakout(
                        symbol=symbol,
                        direction=outcome.breakout.direction,
                        reason=outcome.breakout.reason,
                        confidence=outcome.breakout.confidence,
                    )
                )

        unusual.sort(key=lambda item: item.volume_oi_ratio, reverse=True)
        oi_skew.sort(key=lambda item: item.confidence, reverse=True)
        breakouts.sort(key=lambda item: item.confidence, reverse=True)
        return OptionsScanResult(
            symbols_scanned=succeeded,
            unusual_activity=tuple(unusual[:top_n]),
            oi_skew=tuple(oi_skew[:top_n]),
            breakouts=tuple(breakouts[:top_n]),
            planned_trades=tuple(planned),
            errors=tuple(errors),
        )

    def _research(
        self, service: OptionsResearchService, symbol: str, max_dte: int
    ) -> OptionsResearch | ScannerError:
        try:
            return service.research(symbol, max_dte=max_dte)
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not sink the scan
            return ScannerError(symbol=symbol, detail=str(exc) or exc.__class__.__name__)
