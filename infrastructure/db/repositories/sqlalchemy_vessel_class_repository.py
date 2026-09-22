from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.enums import VesselClass
from domain.models import VesselClassSpec
from infrastructure.db.orm_models import VesselClassORM


class SqlAlchemyVesselClassRepository:
    """Implements VesselClassRepositoryProtocol against a real DB session."""

    def __init__(self, session: Session):
        self._session = session

    def list_vessel_classes(self) -> list[VesselClassSpec]:
        rows = self._session.scalars(select(VesselClassORM)).all()
        return [
            VesselClassSpec(
                vessel_class=VesselClass(row.vessel_class_id),
                min_dwt=row.min_dwt,
                max_dwt=row.max_dwt,
                typical_draft_m=row.typical_draft_m,
                typical_loa_m=row.typical_loa_m,
                typical_beam_m=row.typical_beam_m,
            )
            for row in rows
        ]
