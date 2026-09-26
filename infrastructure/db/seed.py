"""
Seeds ports, vessel classes, routes, and rate history from the team's
real dataset (data/raw/shipping_rates.csv + data/raw/port_congestion.csv).

What's real here vs. what's still a documented placeholder:

- Handysize freight rates: REAL (bulk_carrier_handysize_usd_day),
  interpolated from monthly to daily — see real_dataset_loader.py.
- Supramax/Panamax/Capesize freight rates: DERIVED from the real
  baltic_dry_index via a documented multiplier, not independently
  measured — see real_dataset_loader.py's CLASS_MULTIPLIERS.
- Route-specific adjustment: NOT YET APPLIED (multiplier=1.0,
  amplitude=0.0 — an identity transform). We don't have real
  route-specific rate differential data, so every route currently sees
  the same global index/derived series. This is an honest MVP
  simplification, not a hidden shortcut — revisit
  route_adjustment.py's factors once real route-level data exists.
- Port congestion: REAL only for Tanjung Priok, Indonesia (present in
  port_congestion.csv). None of the named East Coast India ports or
  Newcastle, Australia appear in that dataset (it covers major
  container ports — Shanghai, Rotterdam, LA, etc. — not our specific
  bulk ports), so those fall back to a documented placeholder value.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.enums import VesselClass
from infrastructure.db.orm_models import (
    PortORM,
    RouteFreightRateORM,
    RouteORM,
    VesselClassORM,
)
from infrastructure.db.session import SessionLocal, init_db
from infrastructure.ingestion.real_dataset_loader import (
    build_all_vessel_class_base_index,
    get_real_port_congestion,
)
from infrastructure.ingestion.route_adjustment import apply_route_adjustment
from domain.models import RouteAdjustmentFactor

SHIPPING_RATES_CSV = "data/raw/shipping_rates.csv"
PORT_CONGESTION_CSV = "data/raw/port_congestion.csv"

# Placeholder for any port not present in the real congestion dataset —
# a mid-range, clearly-labeled default rather than pretending it's real.
PLACEHOLDER_CONGESTION_SCORE = 0.20


def seed():
    init_db()
    db = SessionLocal()
    try:
        if db.get(PortORM, "AUS_NEWCASTLE") is not None:
            print("Already seeded — skipping. Delete cargonex.db to reseed from scratch.")
            return

        now = datetime.now(timezone.utc)

        # --- Ports: real congestion where the dataset has it, a labeled
        # placeholder everywhere else ---------------------------------
        tanjung_priok = get_real_port_congestion(PORT_CONGESTION_CSV, "Tanjung Priok")
        tp_score, tp_updated = tanjung_priok if tanjung_priok else (PLACEHOLDER_CONGESTION_SCORE, now.date())

        ports = [
            PortORM(port_id="AUS_NEWCASTLE", name="Newcastle", max_draft_m=20.0,
                     max_loa_m=320.0, max_beam_m=50.0,
                     congestion_score=PLACEHOLDER_CONGESTION_SCORE,  # not in real dataset
                     congestion_updated_at=now),
            PortORM(port_id="IDN_TANJUNGPRIOK", name="Tanjung Priok", max_draft_m=17.0,
                     max_loa_m=280.0, max_beam_m=45.0,
                     congestion_score=tp_score,  # REAL, from port_congestion.csv
                     congestion_updated_at=datetime.combine(tp_updated, datetime.min.time(), tzinfo=timezone.utc)),
            PortORM(port_id="IN_PARADIP", name="Paradip", max_draft_m=18.0,
                     max_loa_m=300.0, max_beam_m=45.0,
                     congestion_score=PLACEHOLDER_CONGESTION_SCORE,  # not in real dataset
                     congestion_updated_at=now),
            PortORM(port_id="IN_VIZAG", name="Vizag", max_draft_m=17.0,
                     max_loa_m=280.0, max_beam_m=43.0,
                     congestion_score=PLACEHOLDER_CONGESTION_SCORE,
                     congestion_updated_at=now),
            PortORM(port_id="IN_GANGAVARAM", name="Gangavaram", max_draft_m=18.5,
                     max_loa_m=300.0, max_beam_m=45.0,
                     congestion_score=PLACEHOLDER_CONGESTION_SCORE,
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

        routes = [
            RouteORM(route_id="AUS_NEWCASTLE-IN_PARADIP", origin_port_id="AUS_NEWCASTLE",
                      destination_port_id="IN_PARADIP", commodity="coal"),
            RouteORM(route_id="IDN_TANJUNGPRIOK-IN_PARADIP", origin_port_id="IDN_TANJUNGPRIOK",
                      destination_port_id="IN_PARADIP", commodity="coal"),
        ]
        db.add_all(routes)
        db.flush()  # ensure route_id FKs exist before inserting rates

        # --- Rate history: real Handysize + BDI-derived other classes,
        # applied identically to both routes (see module docstring for
        # why route-specific differentiation isn't in place yet) -------
        base_index_by_class = build_all_vessel_class_base_index(SHIPPING_RATES_CSV)

        for route in routes:
            for vessel_class, base_values in base_index_by_class.items():
                factor = RouteAdjustmentFactor(
                    route_id=route.route_id,
                    vessel_class=vessel_class,
                    base_multiplier=1.0,
                    seasonal_amplitude=0.0,
                    notes="Identity transform — no real route-specific differential data yet.",
                )
                rates = apply_route_adjustment(base_values, factor)
                db.add_all(
                    RouteFreightRateORM(
                        route_id=route.route_id,
                        vessel_class_id=vessel_class.value,
                        trade_date=r.trade_date,
                        adjusted_rate_usd_per_day=r.adjusted_rate_usd_per_day,
                    )
                    for r in rates
                )

        db.commit()
        print(
            f"Seeded: {len(ports)} ports, {len(vessel_classes)} vessel classes, "
            f"{len(routes)} routes, {len(base_index_by_class) * len(routes)} "
            f"route/vessel-class rate series from the real dataset."
        )
        print(f"Tanjung Priok real congestion score: {tp_score} (source: port_congestion.csv)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
