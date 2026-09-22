from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas.reference_data import PortOut
from infrastructure.db.repositories.sqlalchemy_port_repository import SqlAlchemyPortRepository
from infrastructure.db.session import get_db_session

router = APIRouter(tags=["reference-data"])


@router.get("/ports", response_model=list[PortOut])
def list_ports(db: Session = Depends(get_db_session)):
    ports = SqlAlchemyPortRepository(db).list_ports()
    return [
        PortOut(
            port_id=p.port_id, name=p.name, max_draft_m=p.max_draft_m,
            max_loa_m=p.max_loa_m, max_beam_m=p.max_beam_m,
            congestion_score=p.congestion_score,
        )
        for p in ports
    ]
