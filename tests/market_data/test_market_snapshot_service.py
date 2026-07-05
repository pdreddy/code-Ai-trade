from datetime import UTC, datetime
from decimal import Decimal

from backend.app.application.market_snapshot import MarketSnapshotService, SnapshotBar

BAR_COUNT = 4


class DeterministicMarketSnapshotService(MarketSnapshotService):
    def _fetch_bars(self, symbol, start, end):  # type: ignore[no-untyped-def]
        return [
            SnapshotBar(datetime(2021, 1, 1, tzinfo=UTC), Decimal("100")),
            SnapshotBar(datetime(2021, 1, 2, tzinfo=UTC), Decimal("110")),
            SnapshotBar(datetime(2021, 1, 3, tzinfo=UTC), Decimal("105")),
            SnapshotBar(datetime(2021, 1, 4, tzinfo=UTC), Decimal("120")),
        ]


def test_market_snapshot_service_computes_real_metrics_from_provider_bars() -> None:
    snapshots = DeterministicMarketSnapshotService().five_year_snapshots(("spy",))

    snapshot = snapshots[0]

    assert snapshot.symbol == "SPY"
    assert snapshot.bars == BAR_COUNT
    assert snapshot.last_close == Decimal("120")
    assert snapshot.total_return == Decimal("0.2")
    assert snapshot.max_drawdown == Decimal("-0.0454545454545454545454545455")
    assert snapshot.realized_volatility > 0
