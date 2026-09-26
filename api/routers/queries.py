"""
POST /queries, GET /queries/{id}, GET /queries — implements API Design
v0.1 §3. This router is deliberately thin: it translates HTTP <->
domain objects and maps domain exceptions to status codes. All the
actual logic already lives in QueryOrchestrator, the four services it
coordinates, and SqlAlchemyQueryRepository for history lookups.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_query_orchestrator, get_query_repository
from api.schemas.queries import (
    ForecastOut,
    ForecastPointOut,
    QueryRequest,
    QueryResponse,
    QuerySummaryOut,
    RiskAlertOut,
    RouteSummaryOut,
    TimingWindowOut,
    VesselRecommendationOut,
)
from application.query_orchestrator import QueryOrchestrator
from domain.enums import DurationType
from domain.models import InsufficientHistoryError, NoVesselCapacityError, QueryResult, RouteNotFoundError
from infrastructure.db.repositories.sqlalchemy_query_repository import SqlAlchemyQueryRepository

router = APIRouter(tags=["queries"])


def _to_response(result: QueryResult) -> QueryResponse:
    return QueryResponse(
        query_id=result.query_id,
        route=RouteSummaryOut(
            route_id=result.route.route_id,
            origin_port_id=result.route.origin_port_id,
            destination_port_id=result.route.destination_port_id,
        ),
        recommended_vessel=VesselRecommendationOut(
            vessel_class=result.recommended_vessel.vessel_class.value,
            reason=result.recommended_vessel.reason,
            is_constrained=result.recommended_vessel.is_constrained,
        ),
        forecast=ForecastOut(
            route_id=result.forecast.route_id,
            vessel_class=result.forecast.vessel_class.value,
            horizon_days=result.forecast.horizon_days,
            model_version=result.forecast.model_version,
            points=[
                ForecastPointOut(
                    day_offset=p.day_offset, predicted_rate=p.predicted_rate,
                    lower_bound=p.lower_bound, upper_bound=p.upper_bound,
                )
                for p in result.forecast.points
            ],
        ),
        timing_windows=[
            TimingWindowOut(
                rank=w.rank, start_day_offset=w.start_day_offset,
                end_day_offset=w.end_day_offset, avg_predicted_rate=w.avg_predicted_rate,
            )
            for w in result.timing_windows
        ],
        risk_alerts=[
            RiskAlertOut(
                alert_type=a.alert_type.value, severity=a.severity.value, message=a.message
            )
            for a in result.risk_alerts
        ],
        forecast_vessel_class_note=result.forecast_vessel_class_note,
    )


@router.post("/queries", response_model=QueryResponse, status_code=201)
async def submit_query(
    request: QueryRequest,
    orchestrator: QueryOrchestrator = Depends(get_query_orchestrator),
):
    try:
        result = await orchestrator.handle_query(
            cargo_volume_tonnes=request.cargo_volume_tonnes,
            origin_port_id=request.origin_port_id,
            destination_port_id=request.destination_port_id,
            horizon_days=request.horizon_days,
            duration_type=DurationType(request.desired_duration_type),
        )
    except RouteNotFoundError as e:
        # FR-1.2: inform the user rather than silently guessing.
        raise HTTPException(status_code=422, detail=str(e))
    except NoVesselCapacityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InsufficientHistoryError as e:
        # Not the user's fault (it's a data-availability gap), but they
        # still need a plain-language reason, not a bare 500.
        raise HTTPException(status_code=422, detail=str(e))

    return _to_response(result)


@router.get("/queries/{query_id}", response_model=QueryResponse)
def get_query(query_id: int, repo: SqlAlchemyQueryRepository = Depends(get_query_repository)):
    result = repo.get_query(query_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No query found with id {query_id}")
    return _to_response(result)


@router.get("/queries", response_model=list[QuerySummaryOut])
def list_queries(
    limit: int = 25, offset: int = 0,
    repo: SqlAlchemyQueryRepository = Depends(get_query_repository),
):
    summaries = repo.list_queries(limit=limit, offset=offset)
    return [
        QuerySummaryOut(
            query_id=s.query_id, route_id=s.route_id,
            requested_at=s.requested_at.isoformat(),
        )
        for s in summaries
    ]
