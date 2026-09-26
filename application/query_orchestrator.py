"""
QueryOrchestrator — implements POST /queries (API Design v0.1 §3).

This is the direct implementation of the architecture doc's data flow
diagram, with one honest correction made explicit here (see below):
forecasting and full port-aware vessel matching are run concurrently,
because they genuinely don't depend on each other ONCE you split "which
vessel class's rates to forecast" from "which vessel class to actually
charter."

Why the split was necessary (read this before changing this file):
A Forecast is keyed by (route, vessel_class) — you can't generate one
without knowing the vessel class first. But the FULL vessel
recommendation (recommend_vessel) needs port data and may step down to
a smaller class than the cargo's natural size. If forecasting waited on
that full recommendation, it couldn't run in parallel with it — they'd
be sequential, contradicting the architecture doc's stated design.

The fix: `natural_vessel_class()` (cargo volume only, no ports) decides
which vessel class's rates to forecast, computed up front. The full
`recommend_vessel()` (needs ports) runs independently. Both then run
concurrently via asyncio.gather. If the full recommendation steps down
to a smaller class than the natural one (a port constraint forced it),
that mismatch is surfaced in `forecast_vessel_class_note` rather than
silently forecasting one class while recommending another with no
explanation.

query_repo is OPTIONAL (defaults to None) rather than a required
constructor argument. This is a deliberate choice, not an oversight:
making it required would force every existing test and caller to pass
a repository they don't care about, just to keep working, the moment
FR-8.3 logging was added. Persistence is a side effect of handling a
query, not a precondition for it — if query_repo is None, the query
still resolves correctly, it just isn't logged. Callers that DO want
logging (the real API) pass a real repository.
"""

from __future__ import annotations

import asyncio

from domain.enums import DurationType
from domain.models import QueryResult, RouteNotFoundError
from application.interfaces.port_repository import PortRepositoryProtocol
from application.interfaces.query_repository import QueryRepositoryProtocol
from application.interfaces.route_repository import RouteRepositoryProtocol
from application.interfaces.vessel_class_repository import VesselClassRepositoryProtocol
from application.forecasting_service import ForecastingService
from application.risk_alert_service import evaluate as evaluate_risk_alerts
from application.timing_recommendation_service import rank_windows
from application.vessel_matching_service import natural_vessel_class, recommend_vessel


class QueryOrchestrator:
    def __init__(
        self,
        route_repo: RouteRepositoryProtocol,
        port_repo: PortRepositoryProtocol,
        vessel_class_repo: VesselClassRepositoryProtocol,
        forecasting_service: ForecastingService,
        query_repo: QueryRepositoryProtocol | None = None,
    ):
        self._route_repo = route_repo
        self._port_repo = port_repo
        self._vessel_class_repo = vessel_class_repo
        self._forecasting_service = forecasting_service
        self._query_repo = query_repo

    async def handle_query(
        self,
        cargo_volume_tonnes: int,
        origin_port_id: str,
        destination_port_id: str,
        horizon_days: int = 60,
        duration_type: DurationType = DurationType.SPOT,
    ) -> QueryResult:
        route = self._route_repo.get_route(origin_port_id, destination_port_id)
        if route is None:
            raise RouteNotFoundError(
                f"No route configured for {origin_port_id} -> {destination_port_id} "
                f"in the current MVP scope."
            )

        origin_port = self._port_repo.get_port(origin_port_id)
        destination_port = self._port_repo.get_port(destination_port_id)
        vessel_classes = self._vessel_class_repo.list_vessel_classes()

        forecast_class_spec = natural_vessel_class(cargo_volume_tonnes, vessel_classes)

        # Genuinely independent work, run concurrently. Both are wrapped
        # in asyncio.to_thread because the underlying calls are blocking
        # (Prophet/XGBoost fitting is CPU-bound; vessel matching is fast
        # but wrapped the same way for consistency and so this code
        # doesn't need to change if either later gets slower, e.g. a real
        # DB-backed vessel_class_repo).
        forecast_task = asyncio.to_thread(
            self._forecasting_service.generate_forecast,
            route.route_id,
            forecast_class_spec.vessel_class,
            horizon_days,
        )
        vessel_task = asyncio.to_thread(
            recommend_vessel,
            cargo_volume_tonnes,
            origin_port,
            destination_port,
            vessel_classes,
        )
        forecast, vessel_recommendation = await asyncio.gather(forecast_task, vessel_task)

        # Sequential: both depend on the forecast being ready.
        timing_windows = rank_windows(forecast)
        risk_alerts = evaluate_risk_alerts(
            route.route_id, origin_port, destination_port, forecast
        )

        note = None
        if vessel_recommendation.vessel_class != forecast_class_spec.vessel_class:
            note = (
                f"Forecast reflects {forecast_class_spec.vessel_class.value} rates "
                f"(this cargo's natural market segment), but the recommended "
                f"charter vessel is {vessel_recommendation.vessel_class.value} due to "
                f"a port constraint — see the recommendation's own reason for detail."
            )

        result = QueryResult(
            route=route,
            recommended_vessel=vessel_recommendation,
            forecast=forecast,
            timing_windows=timing_windows,
            risk_alerts=risk_alerts,
            forecast_vessel_class_note=note,
        )

        if self._query_repo is not None:
            query_id = self._query_repo.save_query_result(
                cargo_volume_tonnes, duration_type, result
            )
            # QueryResult is frozen (immutable) by design elsewhere in the
            # domain layer, so the persisted ID is attached via a new
            # instance rather than mutating the one just built.
            result = QueryResult(
                route=result.route,
                recommended_vessel=result.recommended_vessel,
                forecast=result.forecast,
                timing_windows=result.timing_windows,
                risk_alerts=result.risk_alerts,
                forecast_vessel_class_note=result.forecast_vessel_class_note,
                query_id=query_id,
            )

        return result
