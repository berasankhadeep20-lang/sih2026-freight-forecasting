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

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
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
    adjusted_rate_usd_per_tonne: Mapped[float] = mapped_column(Float)
