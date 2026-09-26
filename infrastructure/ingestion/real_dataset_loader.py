"""
Loads the team's real dataset (shipping_rates.csv + port_congestion.csv)
into the shapes the rest of the system already expects.

Two honest limitations of this real dataset, handled explicitly rather
than papered over:

1. MONTHLY, NOT DAILY. shipping_rates.csv has one row per month
   (2000-01 through 2024-12, 300 rows). The forecasting pipeline
   (Prophet + the ensemble's backtest split) was built assuming
   day-level granularity. Rather than rewrite that already-tested
   pipeline to be frequency-aware, this loader LINEARLY INTERPOLATES
   the real monthly readings to daily resolution. The monthly points
   are the actual measured data; everything between two monthly points
   is a straight-line interpolation, not an independent observation.
   This is the same "real signal + disclosed derived layer" pattern
   used everywhere else in this project (see route_adjustment.py) —
   say so if asked, don't imply daily granularity was measured.

2. ONLY HANDYSIZE HAS A REAL PER-CLASS RATE. The dataset gives a real
   `bulk_carrier_handysize_usd_day` column and a real `baltic_dry_index`
   composite, but no separate Panamax/Supramax/Capesize series. For
   those three classes, this loader derives a series from the REAL
   baltic_dry_index multiplied by a documented, literature-informed
   constant (CLASS_MULTIPLIERS below) — an assumption, not measured
   data. If your team finds real per-class sub-index data later,
   replace `build_derived_base_index` calls with real ones; nothing
   downstream needs to change, since both paths produce the same
   BaseIndexValue shape.
"""

from __future__ import annotations

import csv
from datetime import date, datetime

import pandas as pd

from domain.enums import VesselClass
from domain.models import BaseIndexValue

# Rough, order-of-magnitude multipliers on the real Baltic Dry Index
# composite, reflecting that larger vessel classes have historically
# commanded higher day-rates. These are NOT fitted or calibrated against
# real per-class data — they're a documented placeholder assumption.
# Replace with calibrated values (or real sub-index data) before citing
# Supramax/Panamax/Capesize forecasts as anything more than illustrative.
CLASS_MULTIPLIERS: dict[VesselClass, float] = {
    VesselClass.SUPRAMAX: 1.15,
    VesselClass.PANAMAX: 1.45,
    VesselClass.CAPESIZE: 2.20,
}

# Port congestion_index in the real dataset ranges roughly 0.6-8.0
# (p50≈1.56, p90≈4.5, checked directly against the CSV). We map that
# onto this system's documented 0(clear)-1(severe) scale by treating
# the empirical 90th percentile as "severe" — anything at or above it
# saturates to 1.0. This is a normalization choice, not a given fact;
# revisit if the real congestion values look off once plotted.
CONGESTION_SEVERE_THRESHOLD = 4.5


def _parse_monthly_shipping_rates(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            year, month = int(row["year"]), int(row["month"])
            rows.append({
                "date": date(year, month, 1),
                "baltic_dry_index": float(row["baltic_dry_index"]),
                "handysize_usd_per_day": float(row["bulk_carrier_handysize_usd_day"]),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


def _interpolate_to_daily(monthly_rows: list[dict], value_key: str) -> pd.Series:
    """Real monthly points in, a daily-indexed pandas Series out, linearly
    interpolated between them (and edge-filled at the very start/end,
    where interpolation has nothing to interpolate between)."""
    s = pd.Series(
        {r["date"]: r[value_key] for r in monthly_rows},
    )
    s.index = pd.to_datetime(s.index)
    daily = s.resample("D").interpolate(method="linear")
    daily = daily.bfill().ffill()  # cover the first/last partial days
    return daily


def build_handysize_base_index(
    csv_path: str, source_label: str = "Real dataset: shipping_rates.csv (bulk_carrier_handysize_usd_day), interpolated to daily"
) -> list[BaseIndexValue]:
    monthly = _parse_monthly_shipping_rates(csv_path)
    daily = _interpolate_to_daily(monthly, "handysize_usd_per_day")
    return [
        BaseIndexValue(
            vessel_class=VesselClass.HANDYSIZE,
            trade_date=idx.date(),
            index_value=round(float(val), 2),
            source=source_label,
        )
        for idx, val in daily.items()
    ]


def build_derived_base_index(
    csv_path: str, vessel_class: VesselClass
) -> list[BaseIndexValue]:
    if vessel_class not in CLASS_MULTIPLIERS:
        raise ValueError(
            f"{vessel_class} has no documented multiplier — only "
            f"{list(CLASS_MULTIPLIERS)} are derivable this way. "
            f"Handysize should use build_handysize_base_index() instead (real data)."
        )
    multiplier = CLASS_MULTIPLIERS[vessel_class]
    monthly = _parse_monthly_shipping_rates(csv_path)
    daily = _interpolate_to_daily(monthly, "baltic_dry_index")
    source_label = (
        f"Derived: real baltic_dry_index (shipping_rates.csv) x {multiplier} "
        f"documented multiplier for {vessel_class.value} — NOT independently measured"
    )
    return [
        BaseIndexValue(
            vessel_class=vessel_class,
            trade_date=idx.date(),
            index_value=round(float(val) * multiplier, 2),
            source=source_label,
        )
        for idx, val in daily.items()
    ]


def build_all_vessel_class_base_index(csv_path: str) -> dict[VesselClass, list[BaseIndexValue]]:
    """Convenience: every vessel class in one call — Handysize real,
    the other three derived (see module docstring)."""
    result = {VesselClass.HANDYSIZE: build_handysize_base_index(csv_path)}
    for vc in CLASS_MULTIPLIERS:
        result[vc] = build_derived_base_index(csv_path, vc)
    return result


def get_real_port_congestion(csv_path: str, port_name: str) -> tuple[float, date] | None:
    """
    Returns (congestion_score in [0,1], last_updated_date) for the most
    recent week on file for `port_name`, or None if that port isn't in
    the dataset at all (most of this project's East Coast India ports
    aren't — this dataset covers major container ports; see README).
    """
    matching = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["port"] == port_name:
                matching.append(row)
    if not matching:
        return None

    latest = max(matching, key=lambda r: r["week_start"])
    raw_index = float(latest["congestion_index"])
    normalized = min(raw_index / CONGESTION_SEVERE_THRESHOLD, 1.0)
    last_updated = datetime.strptime(latest["week_start"], "%Y-%m-%d").date()
    return round(normalized, 3), last_updated
