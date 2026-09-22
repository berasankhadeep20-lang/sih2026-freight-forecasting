from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas.reference_data import RouteOut
from infrastructure.db.repositories.sqlalchemy_route_repository import SqlAlchemyRouteRepository
from infrastructure.db.session import get_db_session

router = APIRouter(tags=["reference-data"])


@router.get("/routes", response_model=list[RouteOut])
def list_routes(db: Session = Depends(get_db_session)):
    routes = SqlAlchemyRouteRepository(db).list_routes()
    return [
        RouteOut(
            route_id=r.route_id, origin_port_id=r.origin_port_id,
            destination_port_id=r.destination_port_id, commodity=r.commodity,
        )
        for r in routes
    ]
