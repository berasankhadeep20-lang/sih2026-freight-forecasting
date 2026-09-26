"""
Generates a synthetic RouteFreightRate history for testing the
forecasting pipeline WITHOUT needing the real Kaggle dataset yet.

This is test-only scaffolding — it exists so the forecasting service,
Prophet wrapper, and XGBoost residual model can all be verified to work
correctly end-to-end before real data is wired in. It is intentionally
kept out of infrastructure/ so nobody mistakes it for production
ingestion code.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from domain.enums import VesselClass
from domain.models import RouteFreightRate


def generate_synthetic_history(
    route_id: str,
    vessel_class: VesselClass,
    days: int = 730,
    start: date = date(2023, 1, 1),
    seed: int = 42,
) -> list[RouteFreightRate]:
    rng = np.random.default_rng(seed)
    base = 20.0  # USD\/day-ish baseline (Handysize time-charter rate)
    trend_per_day = 0.01
    seasonal_amplitude = 3.0
    noise_std = 0.8

    history = []
    for i in range(days):
        d = start + timedelta(days=i)
        day_of_year = d.timetuple().tm_yday
        seasonal = seasonal_amplitude * np.sin(2 * np.pi * day_of_year / 365.25)
        trend = trend_per_day * i
        noise = rng.normal(0, noise_std)
        rate = max(base + trend + seasonal + noise, 1.0)  # rates can't go negative

        history.append(
            RouteFreightRate(
                route_id=route_id,
                vessel_class=vessel_class,
                trade_date=d,
                adjusted_rate_usd_per_day=round(rate, 2),
            )
        )
    return history
