import asyncio

from domain.enums import DurationType, VesselClass
from application.forecasting_service import ForecastingService
from application.query_orchestrator import QueryOrchestrator
from domain.models import Route
from tests.fixtures.synthetic_data import generate_synthetic_history
from tests.unit.test_forecasting_service import FakeRateRepository
from tests.unit.test_query_orchestrator import (
    AUS_PORT,
    PARADIP_PORT,
    FakePortRepository,
    FakeRouteRepository,
    FakeVesselClassRepository,
)
from tests.unit.test_vessel_and_timing import VESSEL_CLASSES


class FakeQueryRepository:
    """In-memory fake implementing QueryRepositoryProtocol — proves the
    orchestrator calls it correctly without needing a real DB."""

    def __init__(self):
        self.saved = []
        self._next_id = 1

    def save_query_result(self, cargo_volume_tonnes, duration_type, result):
        query_id = self._next_id
        self._next_id += 1
        self.saved.append((query_id, cargo_volume_tonnes, duration_type, result))
        return query_id

    def get_query(self, query_id):
        for saved_id, _, _, result in self.saved:
            if saved_id == query_id:
                return result
        return None

    def list_queries(self, limit=25, offset=0):
        return []


def test_orchestrator_persists_when_query_repo_provided():
    rate_repo = FakeRateRepository()
    rate_repo.seed(
        "route-1", VesselClass.PANAMAX,
        generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730),
    )
    route_repo = FakeRouteRepository()
    route_repo.seed(Route("route-1", "AUS", "PARADIP"))
    port_repo = FakePortRepository()
    port_repo.seed(AUS_PORT)
    port_repo.seed(PARADIP_PORT)
    vessel_class_repo = FakeVesselClassRepository(VESSEL_CLASSES)
    query_repo = FakeQueryRepository()

    orchestrator = QueryOrchestrator(
        route_repo, port_repo, vessel_class_repo,
        ForecastingService(rate_repo), query_repo,
    )

    result = asyncio.run(
        orchestrator.handle_query(
            cargo_volume_tonnes=70_000, origin_port_id="AUS",
            destination_port_id="PARADIP", horizon_days=60,
            duration_type=DurationType.SHORT_TERM,
        )
    )

    assert result.query_id == 1
    assert len(query_repo.saved) == 1
    saved_id, saved_cargo, saved_duration, saved_result = query_repo.saved[0]
    assert saved_cargo == 70_000
    assert saved_duration == DurationType.SHORT_TERM
    assert saved_result.recommended_vessel.vessel_class == VesselClass.PANAMAX


def test_orchestrator_works_without_query_repo_backward_compatible():
    """Every earlier test in test_query_orchestrator.py relies on this:
    query_repo defaults to None and nothing breaks."""
    rate_repo = FakeRateRepository()
    rate_repo.seed(
        "route-1", VesselClass.PANAMAX,
        generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730),
    )
    route_repo = FakeRouteRepository()
    route_repo.seed(Route("route-1", "AUS", "PARADIP"))
    port_repo = FakePortRepository()
    port_repo.seed(AUS_PORT)
    port_repo.seed(PARADIP_PORT)
    vessel_class_repo = FakeVesselClassRepository(VESSEL_CLASSES)

    orchestrator = QueryOrchestrator(
        route_repo, port_repo, vessel_class_repo, ForecastingService(rate_repo)
    )
    result = asyncio.run(
        orchestrator.handle_query(
            cargo_volume_tonnes=70_000, origin_port_id="AUS", destination_port_id="PARADIP",
        )
    )
    assert result.query_id is None
