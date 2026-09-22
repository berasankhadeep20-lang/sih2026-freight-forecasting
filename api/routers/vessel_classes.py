from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas.reference_data import VesselClassOut
from infrastructure.db.repositories.sqlalchemy_vessel_class_repository import (
    SqlAlchemyVesselClassRepository,
)
from infrastructure.db.session import get_db_session

router = APIRouter(tags=["reference-data"])


@router.get("/vessel-classes", response_model=list[VesselClassOut])
def list_vessel_classes(db: Session = Depends(get_db_session)):
    classes = SqlAlchemyVesselClassRepository(db).list_vessel_classes()
    return [
        VesselClassOut(
            vessel_class=vc.vessel_class.value, min_dwt=vc.min_dwt, max_dwt=vc.max_dwt
        )
        for vc in classes
    ]
