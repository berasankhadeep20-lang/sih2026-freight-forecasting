from pydantic import BaseModel


class PortOut(BaseModel):
    port_id: str
    name: str
    max_draft_m: float
    max_loa_m: float
    max_beam_m: float
    congestion_score: float | None


class VesselClassOut(BaseModel):
    vessel_class: str
    min_dwt: int
    max_dwt: int


class RouteOut(BaseModel):
    route_id: str
    origin_port_id: str
    destination_port_id: str
    commodity: str
