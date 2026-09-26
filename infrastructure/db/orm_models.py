"""
SQLAlchemy ORM models — the ONLY place in the codebase that knows about
Postgres/SQLite table structure. Every repository maps between these and
the plain domain dataclasses; no application-layer code ever imports
from this file directly.

Scope note: this covers the four tables needed for a working query flow
(ports, vessel_classes, routes, route_freight_rates). Schema v0.1 also
specifies base_index_values, route_adjustment_factors, forecasts,
forecast_points, recommended_timing_windows, risk_alerts, and queries —
those support FR-8.3's full audit logging and the raw-ingestion-data
traceability, which are real requirements but not blocking a working
demo. Add them the same way (declarative model + repository) when you
get to persisting forecast history rather than just serving live queries.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PortORM(Base):
    __tablename__ = "ports"

    port_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    max_draft_m: Mapped[float] = mapped_column(Float)
    max_loa_m: Mapped[float] = mapped_column(Float)
    max_beam_m: Mapped[float] = mapped_column(Float)
    congestion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    congestion_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class VesselClassORM(Base):
    __tablename__ = "vessel_classes"

    vessel_class_id: Mapped[str] = mapped_column(String(50), primary_key=True)  # matches VesselClass enum value
    min_dwt: Mapped[int] = mapped_column(Integer)
    max_dwt: Mapped[int] = mapped_column(Integer)
    typical_draft_m: Mapped[float] = mapped_column(Float)
    typical_loa_m: Mapped[float] = mapped_column(Float)
    typical_beam_m: Mapped[float] = mapped_column(Float)


class RouteORM(Base):
    __tablename__ = "routes"

    route_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    origin_port_id: Mapped[str] = mapped_column(ForeignKey("ports.port_id"))
    destination_port_id: Mapped[str] = mapped_column(ForeignKey("ports.port_id"))
    commodity: Mapped[str] = mapped_column(String(50), default="coal")


class RouteFreightRateORM(Base):
    __tablename__ = "route_freight_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.route_id"), index=True)
    vessel_class_id: Mapped[str] = mapped_column(String(50), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    adjusted_rate_usd_per_day: Mapped[float] = mapped_column(Float)


class ForecastORM(Base):
    """Schema §3.7. One row per forecast run — logged for FR-8.3 traceability."""
    __tablename__ = "forecasts"

    forecast_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.route_id"))
    vessel_class_id: Mapped[str] = mapped_column(String(50))
    generated_at: Mapped[datetime] = mapped_column(DateTime)
    horizon_days: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(50))


class ForecastPointORM(Base):
    """Schema §3.8. Day-by-day predicted curve for one forecast."""
    __tablename__ = "forecast_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.forecast_id"), index=True)
    day_offset: Mapped[int] = mapped_column(Integer)
    predicted_rate: Mapped[float] = mapped_column(Float)
    lower_bound: Mapped[float] = mapped_column(Float)
    upper_bound: Mapped[float] = mapped_column(Float)


class RecommendedTimingWindowORM(Base):
    """Schema §3.9."""
    __tablename__ = "recommended_timing_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.forecast_id"), index=True)
    start_day_offset: Mapped[int] = mapped_column(Integer)
    end_day_offset: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    avg_predicted_rate: Mapped[float] = mapped_column(Float)


class RiskAlertORM(Base):
    """Schema §3.10."""
    __tablename__ = "risk_alerts"

    alert_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.forecast_id"), nullable=True)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.route_id"))
    alert_type: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(String(500))
    generated_at: Mapped[datetime] = mapped_column(DateTime)


class QueryORM(Base):
    """Schema §3.11. Logs each dashboard query — FR-8.3.

    Deviation from Schema v0.1, found while implementing this: the
    original schema only specified `recommended_vessel_class_id`, which
    is enough to know WHAT was recommended but not WHY — reloading a past
    query would silently lose the recommendation's reason text,
    is_constrained flag, and the forecast/recommendation vessel-class
    mismatch note. Rather than ship a history feature that quietly loses
    information the live query response actually has, these three extra
    columns are added here. Worth carrying this fix back into the schema
    doc itself if anyone re-reads it.
    """
    __tablename__ = "queries"

    query_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cargo_volume_tonnes: Mapped[int] = mapped_column(Integer)
    route_id: Mapped[str] = mapped_column(ForeignKey("routes.route_id"))
    desired_duration_type: Mapped[str] = mapped_column(String(20))
    recommended_vessel_class_id: Mapped[str] = mapped_column(String(50))
    recommendation_reason: Mapped[str] = mapped_column(String(500))
    is_constrained: Mapped[bool] = mapped_column(Boolean)
    forecast_vessel_class_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.forecast_id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime)
