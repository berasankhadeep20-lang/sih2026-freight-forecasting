from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.enums import VesselClass
from domain.models import RouteFreightRate
from infrastructure.db.orm_models import RouteFreightRateORM


class SqlAlchemyRateRepository:
    """Implements RateRepositoryProtocol against a real DB session."""

    def __init__(self, session: Session):
        self._session = session

    def get_historical_rates(
        self, route_id: str, vessel_class: VesselClass
    ) -> list[RouteFreightRate]:
        stmt = (
            select(RouteFreightRateORM)
            .where(
                RouteFreightRateORM.route_id == route_id,
                RouteFreightRateORM.vessel_class_id == vessel_class.value,
            )
            .order_by(RouteFreightRateORM.trade_date)
        )
        rows = self._session.scalars(stmt).all()
        return [
            RouteFreightRate(
                route_id=row.route_id,
                vessel_class=vessel_class,
                trade_date=row.trade_date,
                adjusted_rate_usd_per_day=row.adjusted_rate_usd_per_day,
            )
            for row in rows
        ]
