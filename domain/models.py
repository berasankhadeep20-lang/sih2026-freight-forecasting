"""
Domain models — plain dataclasses with no framework dependencies.

These mirror the tables in Schema v0.1 but are NOT ORM models. The
infrastructure layer maps between these and SQLAlchemy rows; the
application layer (services) only ever sees these. That separation is
what lets every service in the module breakdown be unit-tested without
a database.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from domain.enums import AlertType, Severity, VesselClass


@dataclass(frozen=True)
class BaseIndexValue:
    """
    One real, freely-sourced data point (Schema §3.4 `base_index_values`).
    Global — not tied to any route. `vessel_class` here identifies which
    BDI sub-index this is (e.g. Capesize maps to the BCI sub-index).
    """

    vessel_class: VesselClass
    trade_date: date
    index_value: float
    source: str


@dataclass(frozen=True)
class RouteAdjustmentFactor:
    """
    The synthetic layer's parameters (Schema §3.5). Deliberately plain
    data, not hardcoded logic — see route_adjustment.py for why.
    """

    route_id: str
    vessel_class: VesselClass
    base_multiplier: float
    seasonal_amplitude: float
    notes: str = ""


@dataclass(frozen=True)
class Port:
    """Physical constraints of one port (Schema §3.1)."""

    port_id: str
    name: str
    max_draft_m: float
    max_loa_m: float
    max_beam_m: float
    congestion_score: float | None = None  # 0=clear, 1=severe; None = no data
    congestion_updated_at: datetime | None = None


@dataclass(frozen=True)
class RiskAlert:
    """Output of RiskAlertService (Schema §3.10, FR-6)."""

    route_id: str
    alert_type: AlertType
    severity: Severity
    message: str


@dataclass(frozen=True)
class VesselClassSpec:
    """Physical envelope of one vessel class (Schema §3.2)."""

    vessel_class: VesselClass
    min_dwt: int
    max_dwt: int
    typical_draft_m: float
    typical_loa_m: float
    typical_beam_m: float


@dataclass(frozen=True)
class VesselRecommendation:
    """Output of VesselMatchingService (FR-3)."""

    vessel_class: VesselClass
    reason: str
    is_constrained: bool = False  # True if no class fit cleanly and this is a fallback


@dataclass(frozen=True)
class TimingWindow:
    """One ranked entry-timing window (Schema §3.9, FR-4)."""

    rank: int
    start_day_offset: int
    end_day_offset: int
    avg_predicted_rate: float


class NoVesselCapacityError(ValueError):
    """Raised when cargo volume exceeds every known vessel class's capacity."""


@dataclass(frozen=True)
class Route:
    """One origin-destination pair the system covers (Schema §3.3)."""

    route_id: str
    origin_port_id: str
    destination_port_id: str
    commodity: str = "coal"


@dataclass(frozen=True)
class QueryResult:
    """
    Full output of QueryOrchestrator.handle_query() — implements the
    POST /queries response shape from API Design v0.1.

    forecast_vessel_class_note is populated ONLY when the forecast's
    vessel class (the cargo's natural market segment) differs from the
    final recommended vessel class (which may have been stepped down due
    to port constraints) — see query_orchestrator.py's docstring for why
    this split exists and why the mismatch needs to be surfaced rather
    than silently left for the user to notice.
    """

    route: Route
    recommended_vessel: VesselRecommendation
    forecast: "Forecast"
    timing_windows: list[TimingWindow]
    risk_alerts: list[RiskAlert]
    forecast_vessel_class_note: str | None = None


class RouteNotFoundError(ValueError):
    """Raised when the requested origin/destination pair isn't a known
    route (FR-1.2) — maps to a 422 in the API layer, per API Design v0.1."""


@dataclass(frozen=True)
class RouteFreightRate:
    """Derived, route-specific rate (Schema §3.6) — what the Forecasting
    Service actually trains on."""

    route_id: str
    vessel_class: VesselClass
    trade_date: date
    adjusted_rate_usd_per_tonne: float
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ForecastPoint:
    """One day of a forecast curve (Schema §3.8 `forecast_points`)."""

    day_offset: int
    predicted_rate: float
    lower_bound: float
    upper_bound: float


@dataclass(frozen=True)
class Forecast:
    """One forecast run (Schema §3.7 `forecasts`). model_version records
    which configuration was actually used — see ensemble.py for why this
    isn't always the same string."""

    route_id: str
    vessel_class: VesselClass
    horizon_days: int
    model_version: str
    points: list[ForecastPoint]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InsufficientHistoryError(ValueError):
    """Raised when there isn't enough historical data to fit a seasonal
    model responsibly. Better to fail loudly here than hand back a
    forecast built on too little data with no way for the caller to know."""

