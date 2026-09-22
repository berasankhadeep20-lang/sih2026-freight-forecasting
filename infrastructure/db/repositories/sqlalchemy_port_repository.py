from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models import Port
from infrastructure.db.orm_models import PortORM


class SqlAlchemyPortRepository:
    """Implements PortRepositoryProtocol against a real DB session."""

    def __init__(self, session: Session):
        self._session = session

    def get_port(self, port_id: str) -> Port | None:
        row = self._session.get(PortORM, port_id)
        if row is None:
            return None
        return self._to_domain(row)

    def list_ports(self) -> list[Port]:
        """Not part of PortRepositoryProtocol (the application layer never
        needs "all ports") — exists for the GET /ports reference-data
        endpoint, which reads directly from this repository rather than
        going through a use-case service, since listing is not a decision
        that needs application-layer logic."""
        rows = self._session.scalars(select(PortORM)).all()
        return [self._to_domain(row) for row in rows]

    @staticmethod
    def _to_domain(row: PortORM) -> Port:
        # SQLite doesn't preserve timezone info — a value stored as UTC
        # comes back as a naive datetime. Without this fix, comparing it
        # against a timezone-aware "now" in RiskAlertService raises
        # TypeError, which only surfaces with a real DB, never with the
        # in-memory fakes the unit tests use. Postgres would round-trip
        # this correctly, but we normalize here anyway so the domain
        # layer never has to know which DB backend is in use.
        congestion_updated_at = row.congestion_updated_at
        if congestion_updated_at is not None and congestion_updated_at.tzinfo is None:
            congestion_updated_at = congestion_updated_at.replace(tzinfo=timezone.utc)

        return Port(
            port_id=row.port_id,
            name=row.name,
            max_draft_m=row.max_draft_m,
            max_loa_m=row.max_loa_m,
            max_beam_m=row.max_beam_m,
            congestion_score=row.congestion_score,
            congestion_updated_at=congestion_updated_at,
        )
