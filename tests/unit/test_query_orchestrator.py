import asyncio

import pytest

from domain.enums import VesselClass
from domain.models import Port, Route, RouteNotFoundError
from application.forecasting_service import ForecastingService
from application.query_orchestrator import QueryOrchestrator
from tests.fixtures.synthetic_data import generate_synthetic_history
from tests.unit.test_forecasting_service import FakeRateRepository
from tests.unit.test_vessel_and_timing import VESSEL_CLASSES


class FakeRouteRepository:
    def __init__(self):
        self._routes: dict[tuple[str, str], Route] = {}

    def seed(self, route: Route):
        self._routes[(route.origin_port_id, route.destination_port_id)] = route

    def get_route(self, origin_port_id, destination_port_id):
        return self._routes.get((origin_port_id, destination_port_id))


class FakePortRepository:
    def __init__(self):
        self._ports: dict[str, Port] = {}

    def seed(self, port: Port):
        self._ports[port.port_id] = port

    def get_port(self, port_id):
        return self._ports.get(port_id)


class FakeVesselClassRepository:
    def __init__(self, classes):
        self._classes = classes

    def list_vessel_classes(self):
        return self._classes


AUS_PORT = Port("AUS", "Newcastle", max_draft_m=20.0, max_loa_m=320.0, max_beam_m=50.0,
                congestion_score=0.1)
PARADIP_PORT = Port("PARADIP", "Paradip", max_draft_m=18.0, max_loa_m=300.0, max_beam_m=45.0,
                     congestion_score=0.1)
GOPALPUR_PORT = Port("GOPALPUR", "Gopalpur", max_draft_m=12.5, max_loa_m=200.0, max_beam_m=32.0,
                      congestion_score=0.1)


def _build_orchestrator(rate_repo, route_repo, port_repo, vessel_class_repo):
    forecasting_service = ForecastingService(rate_repo)
    return QueryOrchestrator(route_repo, port_repo, vessel_class_repo, forecasting_service)


def test_successful_query_end_to_end():
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

    orchestrator = _build_orchestrator(rate_repo, route_repo, port_repo, vessel_class_repo)

    result = asyncio.run(
        orchestrator.handle_query(
            cargo_volume_tonnes=70_000,
            origin_port_id="AUS",
            destination_port_id="PARADIP",
            horizon_days=60,
        )
    )

    assert result.route.route_id == "route-1"
    assert result.recommended_vessel.vessel_class == VesselClass.PANAMAX
    assert result.recommended_vessel.is_constrained is False
    assert len(result.forecast.points) == 60
    assert 0 < len(result.timing_windows) <= 3
    assert result.forecast_vessel_class_note is None
    # both ports have fresh, low congestion — no alerts expected
    assert result.risk_alerts == []


def test_unknown_route_raises_route_not_found():
    rate_repo = FakeRateRepository()
    route_repo = FakeRouteRepository()  # nothing seeded
    port_repo = FakePortRepository()
    vessel_class_repo = FakeVesselClassRepository(VESSEL_CLASSES)
    orchestrator = _build_orchestrator(rate_repo, route_repo, port_repo, vessel_class_repo)

    with pytest.raises(RouteNotFoundError):
        asyncio.run(
            orchestrator.handle_query(
                cargo_volume_tonnes=70_000,
                origin_port_id="MOZAMBIQUE",
                destination_port_id="GOPALPUR",
            )
        )


def test_forecast_vessel_class_note_appears_when_port_forces_stepdown():
    """70,000t naturally wants Panamax, but Gopalpur's shallow draft
    forces a step-down to Supramax (same scenario as
    test_vessel_and_timing.test_steps_down_when_destination_port_is_shallow).
    The forecast should still be for Panamax (the natural class), and the
    mismatch with the final Supramax recommendation must be surfaced."""
    rate_repo = FakeRateRepository()
    rate_repo.seed(
        "route-2", VesselClass.PANAMAX,
        generate_synthetic_history("route-2", VesselClass.PANAMAX, days=730),
    )
    route_repo = FakeRouteRepository()
    route_repo.seed(Route("route-2", "AUS", "GOPALPUR"))
    port_repo = FakePortRepository()
    port_repo.seed(AUS_PORT)
    port_repo.seed(GOPALPUR_PORT)
    vessel_class_repo = FakeVesselClassRepository(VESSEL_CLASSES)

    orchestrator = _build_orchestrator(rate_repo, route_repo, port_repo, vessel_class_repo)

    result = asyncio.run(
        orchestrator.handle_query(
            cargo_volume_tonnes=70_000,
            origin_port_id="AUS",
            destination_port_id="GOPALPUR",
            horizon_days=60,
        )
    )

    assert result.recommended_vessel.vessel_class == VesselClass.SUPRAMAX
    assert result.recommended_vessel.is_constrained is True
    assert result.forecast.vessel_class == VesselClass.PANAMAX  # forecast used the natural class
    assert result.forecast_vessel_class_note is not None
    assert "Panamax" in result.forecast_vessel_class_note
    assert "Supramax" in result.forecast_vessel_class_note
