"""SQLAlchemy market-data repository implementation."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.domain.entities import Bar, CorporateAction, Instrument
from backend.app.domain.enums import AssetClass, CorporateActionType
from backend.app.domain.providers import HistoricalMarketData
from backend.app.domain.value_objects import Price
from backend.app.infrastructure.database.models import (
    BarModel,
    CorporateActionModel,
    IngestionBatchModel,
    InstrumentModel,
)


class SqlAlchemyMarketDataRepository:
    """Persist and retrieve normalized market data with provider lineage."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_instrument(self, instrument: Instrument) -> None:
        """Insert or update an instrument master record."""

        model = self._session.get(InstrumentModel, instrument.id)
        if model is None:
            model = InstrumentModel(id=instrument.id)
            self._session.add(model)
        model.symbol = instrument.symbol.upper()
        model.name = instrument.name
        model.exchange = instrument.exchange
        model.asset_class = instrument.asset_class.value
        model.currency = instrument.currency.upper()
        model.active = instrument.active

    def get_instrument_by_symbol(self, symbol: str) -> Instrument | None:
        """Fetch an instrument by symbol."""

        statement = select(InstrumentModel).where(InstrumentModel.symbol == symbol.upper())
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            return None
        return Instrument(
            id=model.id,
            symbol=model.symbol,
            name=model.name,
            exchange=model.exchange,
            asset_class=AssetClass(model.asset_class),
            currency=model.currency,
            active=model.active,
        )

    def save_historical_market_data(self, data: HistoricalMarketData) -> None:
        """Persist a normalized provider response as one ingestion batch."""

        retrieved_at = datetime.fromisoformat(data.lineage.retrieved_at_utc_iso)
        batch = IngestionBatchModel(
            provider=data.lineage.provider,
            dataset=data.lineage.dataset,
            symbol=data.lineage.symbol.upper(),
            adjustment_policy=data.lineage.adjustment_policy,
            retrieved_at_utc=retrieved_at,
            created_at_utc=datetime.now(UTC),
        )
        self._session.add(batch)
        self._session.flush()
        self._session.add_all(_bar_models(data, batch.id))
        self._session.add_all(_corporate_action_models(data, batch.id))

    def get_bars(self, instrument_id: UUID, start: date, end: date) -> Sequence[Bar]:
        """Fetch bars for an instrument over an inclusive date range."""

        start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
        end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
        statement = (
            select(BarModel)
            .where(BarModel.instrument_id == instrument_id)
            .where(BarModel.timestamp_utc >= start_dt)
            .where(BarModel.timestamp_utc <= end_dt)
            .order_by(BarModel.timestamp_utc.asc())
        )
        return tuple(_bar_from_model(model) for model in self._session.execute(statement).scalars())


def _bar_models(data: HistoricalMarketData, ingestion_batch_id: int) -> list[BarModel]:
    return [
        BarModel(
            instrument_id=bar.instrument_id,
            ingestion_batch_id=ingestion_batch_id,
            timestamp_utc=bar.timestamp,
            provider=data.lineage.provider,
            adjustment_policy=data.lineage.adjustment_policy,
            open=bar.open.value,
            high=bar.high.value,
            low=bar.low.value,
            close=bar.close.value,
            adjusted_close=bar.adjusted_close.value if bar.adjusted_close is not None else None,
            volume=bar.volume,
        )
        for bar in data.bars
    ]


def _corporate_action_models(
    data: HistoricalMarketData, ingestion_batch_id: int
) -> list[CorporateActionModel]:
    return [
        CorporateActionModel(
            instrument_id=action.instrument_id,
            ingestion_batch_id=ingestion_batch_id,
            ex_date=action.ex_date,
            action_type=action.action_type.value,
            value=action.value,
            provider=data.lineage.provider,
            source=action.source,
        )
        for action in data.corporate_actions
    ]


def _bar_from_model(model: BarModel) -> Bar:
    return Bar(
        instrument_id=model.instrument_id,
        timestamp=model.timestamp_utc,
        open=Price(model.open),
        high=Price(model.high),
        low=Price(model.low),
        close=Price(model.close),
        volume=model.volume,
        adjusted_close=Price(model.adjusted_close) if model.adjusted_close is not None else None,
    )


def _corporate_action_from_model(model: CorporateActionModel) -> CorporateAction:
    return CorporateAction(
        instrument_id=model.instrument_id,
        ex_date=model.ex_date,
        action_type=CorporateActionType(model.action_type),
        value=model.value,
        source=model.source,
    )
