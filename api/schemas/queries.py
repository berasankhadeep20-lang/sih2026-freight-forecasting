from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    cargo_volume_tonnes: int = Field(gt=0)
    origin_port_id: str
    destination_port_id: str
    horizon_days: int = Field(default=60, gt=0, le=180)


class ForecastPointOut(BaseModel):
    day_offset: int
    predicted_rate: float
    lower_bound: float
    upper_bound: float


class ForecastOut(BaseModel):
    route_id: str
    vessel_class: str
    horizon_days: int
    model_version: str
    points: list[ForecastPointOut]


class VesselRecommendationOut(BaseModel):
    vessel_class: str
    reason: str
    is_constrained: bool


class TimingWindowOut(BaseModel):
    rank: int
    start_day_offset: int
    end_day_offset: int
    avg_predicted_rate: float


class RiskAlertOut(BaseModel):
    alert_type: str
    severity: str
    message: str


class RouteSummaryOut(BaseModel):
    route_id: str
    origin_port_id: str
    destination_port_id: str


class QueryResponse(BaseModel):
    route: RouteSummaryOut
    recommended_vessel: VesselRecommendationOut
    forecast: ForecastOut
    timing_windows: list[TimingWindowOut]
    risk_alerts: list[RiskAlertOut]
    forecast_vessel_class_note: str | None


class ErrorDetail(BaseModel):
    """Every error response includes a plain-language reason — per API
    Design v0.1's cross-cutting rule, not just the happy path."""
    detail: str
