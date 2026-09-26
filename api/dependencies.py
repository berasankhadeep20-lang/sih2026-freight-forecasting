"""
Dependency wiring — this file's whole job is constructing the same
services/orchestrator that the unit tests construct with fakes, but with
real SQLAlchemy repositories instead. If application-layer code needs to
change to make this file work, something leaked through the Protocol
boundary; it shouldn't.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from application.forecasting_service import ForecastingService
from application.query_orchestrator import QueryOrchestrator
from infrastructure.db.repositories.sqlalchemy_port_repository import SqlAlchemyPortRepository
from infrastructure.db.repositories.sqlalchemy_query_repository import SqlAlchemyQueryRepository
from infrastructure.db.repositories.sqlalchemy_rate_repository import SqlAlchemyRateRepository
from infrastructure.db.repositories.sqlalchemy_route_repository import SqlAlchemyRouteRepository
from infrastructure.db.repositories.sqlalchemy_vessel_class_repository import (
    SqlAlchemyVesselClassRepository,
)
from infrastructure.db.session import get_db_session


def get_query_orchestrator(db: Session = Depends(get_db_session)) -> QueryOrchestrator:
    route_repo = SqlAlchemyRouteRepository(db)
    port_repo = SqlAlchemyPortRepository(db)
    vessel_class_repo = SqlAlchemyVesselClassRepository(db)
    rate_repo = SqlAlchemyRateRepository(db)
    query_repo = SqlAlchemyQueryRepository(db)
    forecasting_service = ForecastingService(rate_repo)
    return QueryOrchestrator(
        route_repo, port_repo, vessel_class_repo, forecasting_service, query_repo
    )


def get_query_repository(db: Session = Depends(get_db_session)) -> SqlAlchemyQueryRepository:
    return SqlAlchemyQueryRepository(db)
