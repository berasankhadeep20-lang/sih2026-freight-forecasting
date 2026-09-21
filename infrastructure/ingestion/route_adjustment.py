"""
Applies a RouteAdjustmentFactor to global BaseIndexValue data, producing
route-specific RouteFreightRate rows (Schema §3.6).

Formula (deliberately simple and by-hand verifiable — see chat):

    adjusted_rate = index_value * base_multiplier * (1 + seasonal_amplitude * seasonal_component(date))

where seasonal_component(date) = sin(2*pi * day_of_year / 365.25)

Why a sinusoid: bulk commodity demand (coal for power generation, grain
around harvest) has a real annual cycle, and a single sine term is the
simplest possible model of "one peak, one trough per year" — enough to
produce a defensible synthetic series for a hackathon MVP without
pretending to model anything more sophisticated than we actually know.
seasonal_amplitude is a *knob*, not a fitted parameter — it should be
set conservatively (e.g. 0.05-0.15) and the reasoning documented in
RouteAdjustmentFactor.notes, because unlike the base index this number
is an assumption, not observed data. Tune it later if held-out backtest
error suggests the route has more/less seasonal swing than the current
setting implies.
"""

from __future__ import annotations

import math

from domain.models import BaseIndexValue, RouteAdjustmentFactor, RouteFreightRate


def seasonal_component(day_of_year: int) -> float:
    """Returns a value in [-1, 1], peaking at day ~91 (early April) and
    troughing at day ~274 (early October) — adjust the phase shift here
    if your team's route research points to a different peak season."""
    return math.sin(2 * math.pi * day_of_year / 365.25)


def apply_route_adjustment(
    base_values: list[BaseIndexValue],
    factor: RouteAdjustmentFactor,
) -> list[RouteFreightRate]:
    """
    Transforms global index values into one route's derived rate series.

    Only base_values matching factor.vessel_class are used — the caller
    is expected to have already filtered, or pass a mixed list and let
    this function filter (it does both safely).
    """
    results: list[RouteFreightRate] = []
    for bv in base_values:
        if bv.vessel_class != factor.vessel_class:
            continue

        seasonal = seasonal_component(bv.trade_date.timetuple().tm_yday)
        adjusted = bv.index_value * factor.base_multiplier * (
            1 + factor.seasonal_amplitude * seasonal
        )

        results.append(
            RouteFreightRate(
                route_id=factor.route_id,
                vessel_class=factor.vessel_class,
                trade_date=bv.trade_date,
                adjusted_rate_usd_per_tonne=round(adjusted, 2),
            )
        )
    return results
