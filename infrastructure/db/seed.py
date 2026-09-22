"""
Seeds ports, vessel classes, one demo route, and a placeholder rate
history so the API is runnable end-to-end without the real Kaggle
dataset wired in yet.

IMPORTANT: the rate history seeded here is a self-contained synthetic
generator — NOT the real ingestion pipeline (kaggle_loader.py +
route_adjustment.py). It exists purely so `python -m infrastructure.db.seed`
gives you a working demo immediately. Replace this with a real script
that runs load_base_index_csv() -> apply_route_adjustment() -> bulk
insert into route_freight_rates once your team has the actual dataset.
The port/vessel-class specs below are illustrative placeholders too —
replace with your team's compiled real port authority data before
using this for anything beyond a local smoke test.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np

from infrastructure.db.orm_models import (
    PortORM,
    RouteFreightRateORM,
    RouteORM,
    VesselClassORM,
)
from infrastructure.db.session import SessionLocal, init_db


def _generate_placeholder_rates(days: int = 730, seed: int = 42) -> list[tuple[date, float]]:
    rng = np.random.default_rng(seed)
    base, trend_per_day, seasonal_amp, noise_std = 20.0, 0.01, 3.0, 0.8
    start = date(2023, 1, 1)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        seasonal = seasonal_amp * math.sin(2 * math.pi * d.timetuple().tm_yday / 365.25)
        rate = max(base + trend_per_day * i + seasonal + rng.normal(0, noise_std), 1.0)
        out.append((d, round(rate, 2)))
    return out


def seed():
    init_db()
    db = SessionLocal()
    try:
        if db.get(PortORM, "AUS_NEWCASTLE") is not None:
            print("Already seeded — skipping. Delete cargonex.db to reseed from scratch.")
            return

        now = datetime.now(timezone.utc)

        ports = [
            PortORM(port_id="AUS_NEWCASTLE", name="Newcastle", max_draft_m=20.0,
                     max_loa_m=320.0, max_beam_m=50.0, congestion_score=0.15,
                     congestion_updated_at=now),
            PortORM(port_id="IDN_TABONEO", name="Taboneo Anchorage", max_draft_m=17.0,
                     max_loa_m=280.0, max_beam_m=45.0, congestion_score=0.20,
                     congestion_updated_at=now),
            PortORM(port_id="IN_PARADIP", name="Paradip", max_draft_m=18.0,
                     max_loa_m=300.0, max_beam_m=45.0, congestion_score=0.30,
                     congestion_updated_at=now),
            PortORM(port_id="IN_VIZAG", name="Vizag", max_draft_m=17.0,
                     max_loa_m=280.0, max_beam_m=43.0, congestion_score=0.25,
                     congestion_updated_at=now),
            PortORM(port_id="IN_GANGAVARAM", name="Gangavaram", max_draft_m=18.5,
                     max_loa_m=300.0, max_beam_m=45.0, congestion_score=0.10,
                     congestion_updated_at=now),
        ]
        db.add_all(ports)

        vessel_classes = [
            VesselClassORM(vessel_class_id="Handysize", min_dwt=10_000, max_dwt=40_000,
                            typical_draft_m=10.0, typical_loa_m=190.0, typical_beam_m=30.0),
            VesselClassORM(vessel_class_id="Supramax", min_dwt=40_001, max_dwt=60_000,
                            typical_draft_m=12.0, typical_loa_m=200.0, typical_beam_m=32.0),
            VesselClassORM(vessel_class_id="Panamax", min_dwt=60_001, max_dwt=80_000,
                            typical_draft_m=14.0, typical_loa_m=225.0, typical_beam_m=32.3),
            VesselClassORM(vessel_class_id="Capesize", min_dwt=80_001, max_dwt=180_000,
                            typical_draft_m=18.0, typical_loa_m=290.0, typical_beam_m=45.0),
        ]
        db.add_all(vessel_classes)

        route = RouteORM(
            route_id="AUS_NEWCASTLE-IN_PARADIP", origin_port_id="AUS_NEWCASTLE",
            destination_port_id="IN_PARADIP", commodity="coal",
        )
        db.add(route)
        db.flush()  # ensure route_id FK is satisfied before inserting rates

        for trade_date, rate in _generate_placeholder_rates():
            db.add(RouteFreightRateORM(
                route_id=route.route_id, vessel_class_id="Panamax",
                trade_date=trade_date, adjusted_rate_usd_per_tonne=rate,
            ))

        db.commit()
        print("Seeded: 5 ports, 4 vessel classes, 1 route, 730 days of placeholder rates.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
