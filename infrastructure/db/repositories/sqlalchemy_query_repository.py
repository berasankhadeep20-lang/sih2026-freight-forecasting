from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.enums import AlertType, DurationType, Severity, VesselClass
from domain.models import (
    Forecast,
    ForecastPoint,
    QueryResult,
    QuerySummary,
    RiskAlert,
    Route,
    TimingWindow,
    VesselRecommendation,
)
from infrastructure.db.orm_models import (
    ForecastORM,
    ForecastPointORM,
    QueryORM,
    RecommendedTimingWindowORM,
    RiskAlertORM,
    RouteORM,
)


class SqlAlchemyQueryRepository:
    """Implements QueryRepositoryProtocol — persists and reloads full
    query results (FR-8.3)."""

    def __init__(self, session: Session):
        self._session = session

    def save_query_result(
        self, cargo_volume_tonnes: int, duration_type: DurationType, result: QueryResult
    ) -> int:
        forecast_row = ForecastORM(
            route_id=result.route.route_id,
            vessel_class_id=result.forecast.vessel_class.value,
            generated_at=result.forecast.generated_at,
            horizon_days=result.forecast.horizon_days,
            model_version=result.forecast.model_version,
        )
        self._session.add(forecast_row)
        self._session.flush()  # populate forecast_row.forecast_id before children reference it

        self._session.add_all(
            ForecastPointORM(
                forecast_id=forecast_row.forecast_id,
                day_offset=p.day_offset,
                predicted_rate=p.predicted_rate,
                lower_bound=p.lower_bound,
                upper_bound=p.upper_bound,
            )
            for p in result.forecast.points
        )
        self._session.add_all(
            RecommendedTimingWindowORM(
                forecast_id=forecast_row.forecast_id,
                start_day_offset=w.start_day_offset,
                end_day_offset=w.end_day_offset,
                rank=w.rank,
                avg_predicted_rate=w.avg_predicted_rate,
            )
            for w in result.timing_windows
        )
        now = result.forecast.generated_at  # reuse one consistent timestamp for this query's rows
        self._session.add_all(
            RiskAlertORM(
                forecast_id=forecast_row.forecast_id,
                route_id=result.route.route_id,
                alert_type=a.alert_type.value,
                severity=a.severity.value,
                message=a.message,
                generated_at=now,
            )
            for a in result.risk_alerts
        )

        query_row = QueryORM(
            cargo_volume_tonnes=cargo_volume_tonnes,
            route_id=result.route.route_id,
            desired_duration_type=duration_type.value,
            recommended_vessel_class_id=result.recommended_vessel.vessel_class.value,
            recommendation_reason=result.recommended_vessel.reason,
            is_constrained=result.recommended_vessel.is_constrained,
            forecast_vessel_class_note=result.forecast_vessel_class_note,
            forecast_id=forecast_row.forecast_id,
            requested_at=now,
        )
        self._session.add(query_row)
        self._session.commit()
        return query_row.query_id

    def get_query(self, query_id: int) -> QueryResult | None:
        query_row = self._session.get(QueryORM, query_id)
        if query_row is None:
            return None

        forecast_row = self._session.get(ForecastORM, query_row.forecast_id)
        route_row = self._session.get(RouteORM, query_row.route_id)

        point_rows = self._session.scalars(
            select(ForecastPointORM)
            .where(ForecastPointORM.forecast_id == forecast_row.forecast_id)
            .order_by(ForecastPointORM.day_offset)
        ).all()
        window_rows = self._session.scalars(
            select(RecommendedTimingWindowORM)
            .where(RecommendedTimingWindowORM.forecast_id == forecast_row.forecast_id)
            .order_by(RecommendedTimingWindowORM.rank)
        ).all()
        alert_rows = self._session.scalars(
            select(RiskAlertORM).where(RiskAlertORM.forecast_id == forecast_row.forecast_id)
        ).all()

        forecast = Forecast(
            route_id=forecast_row.route_id,
            vessel_class=VesselClass(forecast_row.vessel_class_id),
            horizon_days=forecast_row.horizon_days,
            model_version=forecast_row.model_version,
            points=[
                ForecastPoint(
                    day_offset=p.day_offset, predicted_rate=p.predicted_rate,
                    lower_bound=p.lower_bound, upper_bound=p.upper_bound,
                )
                for p in point_rows
            ],
            generated_at=self._as_utc(forecast_row.generated_at),
        )

        return QueryResult(
            query_id=query_row.query_id,
            route=Route(
                route_id=route_row.route_id,
                origin_port_id=route_row.origin_port_id,
                destination_port_id=route_row.destination_port_id,
                commodity=route_row.commodity,
            ),
            recommended_vessel=VesselRecommendation(
                vessel_class=VesselClass(query_row.recommended_vessel_class_id),
                reason=query_row.recommendation_reason,
                is_constrained=query_row.is_constrained,
            ),
            forecast=forecast,
            timing_windows=[
                TimingWindow(
                    rank=w.rank, start_day_offset=w.start_day_offset,
                    end_day_offset=w.end_day_offset, avg_predicted_rate=w.avg_predicted_rate,
                )
                for w in window_rows
            ],
            risk_alerts=[
                RiskAlert(
                    route_id=a.route_id, alert_type=AlertType(a.alert_type),
                    severity=Severity(a.severity), message=a.message,
                )
                for a in alert_rows
            ],
            forecast_vessel_class_note=query_row.forecast_vessel_class_note,
        )

    def list_queries(self, limit: int = 25, offset: int = 0) -> list[QuerySummary]:
        stmt = (
            select(QueryORM)
            .order_by(QueryORM.requested_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self._session.scalars(stmt).all()
        return [
            QuerySummary(
                query_id=r.query_id, route_id=r.route_id,
                requested_at=self._as_utc(r.requested_at),
            )
            for r in rows
        ]

    @staticmethod
    def _as_utc(dt):
        # Same SQLite-naive-datetime issue as SqlAlchemyPortRepository —
        # see that file's comment for the full explanation.
        if dt is not None and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
