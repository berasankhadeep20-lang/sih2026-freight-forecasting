"""
Integration tests: real FastAPI app + real SQLAlchemy models + a real
(in-memory) SQLite DB. This is what proves the whole stack wires
together correctly — the unit tests only prove each piece works against
fakes, which is necessary but not sufficient.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_query_orchestrator
from application.forecasting_service import ForecastingService
from application.query_orchestrator import QueryOrchestrator
from infrastructure.db.orm_models import Base, PortORM, RouteFreightRateORM, RouteORM, VesselClassORM
from infrastructure.db.repositories.sqlalchemy_port_repository import SqlAlchemyPortRepository
from infrastructure.db.repositories.sqlalchemy_rate_repository import SqlAlchemyRateRepository
from infrastructure.db.repositories.sqlalchemy_route_repository import SqlAlchemyRouteRepository
from infrastructure.db.repositories.sqlalchemy_vessel_class_repository import (
    SqlAlchemyVesselClassRepository,
)
from infrastructure.db.session import get_db_session
from main import app
from tests.fixtures.synthetic_data import generate_synthetic_history
from domain.enums import VesselClass

# Shared in-memory DB across connections/threads — needed because
# QueryOrchestrator dispatches work via asyncio.to_thread, which uses a
# different thread than the request handler.
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=TEST_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=TEST_ENGINE)
    db = TestSessionLocal()
    now = datetime.now(timezone.utc)

    db.add_all([
        PortORM(port_id="AUS", name="Newcastle", max_draft_m=20.0, max_loa_m=320.0,
                 max_beam_m=50.0, congestion_score=0.1, congestion_updated_at=now),
        PortORM(port_id="PARADIP", name="Paradip", max_draft_m=18.0, max_loa_m=300.0,
                 max_beam_m=45.0, congestion_score=0.1, congestion_updated_at=now),
    ])
    db.add_all([
        VesselClassORM(vessel_class_id="Handysize", min_dwt=10_000, max_dwt=40_000,
                        typical_draft_m=10.0, typical_loa_m=190.0, typical_beam_m=30.0),
        VesselClassORM(vessel_class_id="Supramax", min_dwt=40_001, max_dwt=60_000,
                        typical_draft_m=12.0, typical_loa_m=200.0, typical_beam_m=32.0),
        VesselClassORM(vessel_class_id="Panamax", min_dwt=60_001, max_dwt=80_000,
                        typical_draft_m=14.0, typical_loa_m=225.0, typical_beam_m=32.3),
        VesselClassORM(vessel_class_id="Capesize", min_dwt=80_001, max_dwt=180_000,
                        typical_draft_m=18.0, typical_loa_m=290.0, typical_beam_m=45.0),
    ])
    db.add(RouteORM(route_id="route-1", origin_port_id="AUS", destination_port_id="PARADIP"))
    db.flush()

    history = generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730)
    db.add_all([
        RouteFreightRateORM(
            route_id="route-1", vessel_class_id="Panamax",
            trade_date=r.trade_date, adjusted_rate_usd_per_day=r.adjusted_rate_usd_per_day,
        )
        for r in history
    ])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=TEST_ENGINE)


def _override_get_db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db_session] = _override_get_db_session
client = TestClient(app)


def test_get_ports_returns_seeded_ports():
    resp = client.get("/ports")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert names == {"Newcastle", "Paradip"}


def test_get_vessel_classes_returns_all_four():
    resp = client.get("/vessel-classes")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_get_routes_returns_seeded_route():
    resp = client.get("/routes")
    assert resp.status_code == 200
    assert resp.json()[0]["route_id"] == "route-1"


def test_post_queries_happy_path():
    resp = client.post("/queries", json={
        "cargo_volume_tonnes": 70000,
        "origin_port_id": "AUS",
        "destination_port_id": "PARADIP",
        "horizon_days": 60,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["recommended_vessel"]["vessel_class"] == "Panamax"
    assert len(body["forecast"]["points"]) == 60
    assert 0 < len(body["timing_windows"]) <= 3
    assert body["forecast_vessel_class_note"] is None


def test_post_queries_unknown_route_returns_422_with_reason():
    resp = client.post("/queries", json={
        "cargo_volume_tonnes": 70000,
        "origin_port_id": "MOZAMBIQUE",
        "destination_port_id": "GOPALPUR",
    })
    assert resp.status_code == 422
    assert "No route configured" in resp.json()["detail"]


def test_post_queries_rejects_non_positive_cargo_volume():
    resp = client.post("/queries", json={
        "cargo_volume_tonnes": -5,
        "origin_port_id": "AUS",
        "destination_port_id": "PARADIP",
    })
    assert resp.status_code == 422


def test_post_queries_response_includes_a_real_query_id():
    """This is what proves persistence actually happened through the real
    API + real SQLAlchemy repository, not just the in-memory fake used in
    the unit tests."""
    resp = client.post("/queries", json={
        "cargo_volume_tonnes": 70000, "origin_port_id": "AUS",
        "destination_port_id": "PARADIP", "horizon_days": 60,
    })
    assert resp.status_code == 201
    assert isinstance(resp.json()["query_id"], int)


def test_get_query_by_id_reconstructs_the_same_result():
    post_resp = client.post("/queries", json={
        "cargo_volume_tonnes": 70000, "origin_port_id": "AUS",
        "destination_port_id": "PARADIP", "horizon_days": 60,
    })
    query_id = post_resp.json()["query_id"]

    get_resp = client.get(f"/queries/{query_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["query_id"] == query_id
    assert body["recommended_vessel"]["vessel_class"] == post_resp.json()["recommended_vessel"]["vessel_class"]
    assert body["recommended_vessel"]["reason"] == post_resp.json()["recommended_vessel"]["reason"]
    assert len(body["forecast"]["points"]) == 60


def test_get_query_unknown_id_returns_404():
    resp = client.get("/queries/999999")
    assert resp.status_code == 404


def test_list_queries_returns_recent_entries_newest_first():
    client.post("/queries", json={
        "cargo_volume_tonnes": 50000, "origin_port_id": "AUS",
        "destination_port_id": "PARADIP", "horizon_days": 30,
    })
    resp = client.get("/queries?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    # newest first: the most recently posted query_id should lead
    assert body[0]["query_id"] >= body[-1]["query_id"]
