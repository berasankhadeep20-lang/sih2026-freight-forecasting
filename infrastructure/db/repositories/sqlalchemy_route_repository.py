from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models import Route
from infrastructure.db.orm_models import RouteORM


class SqlAlchemyRouteRepository:
    """Implements RouteRepositoryProtocol against a real DB session."""

    def __init__(self, session: Session):
        self._session = session

    def get_route(self, origin_port_id: str, destination_port_id: str) -> Route | None:
        stmt = select(RouteORM).where(
            RouteORM.origin_port_id == origin_port_id,
            RouteORM.destination_port_id == destination_port_id,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return self._to_domain(row)

    def list_routes(self) -> list[Route]:
        """Not part of RouteRepositoryProtocol — exists for GET /routes,
        same reasoning as SqlAlchemyPortRepository.list_ports()."""
        rows = self._session.scalars(select(RouteORM)).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: RouteORM) -> Route:
        return Route(
            route_id=row.route_id,
            origin_port_id=row.origin_port_id,
            destination_port_id=row.destination_port_id,
            commodity=row.commodity,
        )
