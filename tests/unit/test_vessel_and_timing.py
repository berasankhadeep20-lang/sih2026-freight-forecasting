import pytest

from domain.enums import VesselClass
from domain.models import (
    Forecast,
    ForecastPoint,
    NoVesselCapacityError,
    Port,
    VesselClassSpec,
)
from application.vessel_matching_service import recommend_vessel
from application.timing_recommendation_service import rank_windows

# Contiguous DWT ranges for deterministic matching (real-world classes
# overlap somewhat; this simplification is documented and intentional).
VESSEL_CLASSES = [
    VesselClassSpec(VesselClass.HANDYSIZE, min_dwt=10_000, max_dwt=40_000,
                     typical_draft_m=10.0, typical_loa_m=190.0, typical_beam_m=30.0),
    VesselClassSpec(VesselClass.SUPRAMAX, min_dwt=40_001, max_dwt=60_000,
                     typical_draft_m=12.0, typical_loa_m=200.0, typical_beam_m=32.0),
    VesselClassSpec(VesselClass.PANAMAX, min_dwt=60_001, max_dwt=80_000,
                     typical_draft_m=14.0, typical_loa_m=225.0, typical_beam_m=32.3),
    VesselClassSpec(VesselClass.CAPESIZE, min_dwt=80_001, max_dwt=180_000,
                     typical_draft_m=18.0, typical_loa_m=290.0, typical_beam_m=45.0),
]

DEEP_PORT = Port("p1", "Newcastle", max_draft_m=20.0, max_loa_m=320.0, max_beam_m=50.0)
PARADIP = Port("p2", "Paradip", max_draft_m=18.0, max_loa_m=300.0, max_beam_m=45.0)
SHALLOW_PORT = Port("p3", "Gopalpur", max_draft_m=12.5, max_loa_m=200.0, max_beam_m=32.0)


# --- VesselMatchingService ------------------------------------------------

def test_recommends_natural_class_when_both_ports_fit():
    rec = recommend_vessel(70_000, DEEP_PORT, PARADIP, VESSEL_CLASSES)
    assert rec.vessel_class == VesselClass.PANAMAX
    assert rec.is_constrained is False


def test_never_recommends_larger_than_natural_class():
    """A 70,000t cargo must never get recommended a Capesize, even though
    a Capesize could physically carry it — this is the exact bug caught
    and fixed before writing these tests."""
    rec = recommend_vessel(70_000, DEEP_PORT, DEEP_PORT, VESSEL_CLASSES)
    assert rec.vessel_class != VesselClass.CAPESIZE
    assert rec.vessel_class == VesselClass.PANAMAX


def test_steps_down_when_destination_port_is_shallow():
    """70,000t naturally wants Panamax (draft 14.0m), but Gopalpur's max
    draft is 12.5m — Panamax doesn't fit, so it must step down to
    Supramax (draft 12.0m), not fail and not silently pick Panamax anyway."""
    rec = recommend_vessel(70_000, DEEP_PORT, SHALLOW_PORT, VESSEL_CLASSES)
    assert rec.vessel_class == VesselClass.SUPRAMAX
    assert rec.is_constrained is True
    assert "Gopalpur" in rec.reason or "draft" in rec.reason


def test_raises_when_cargo_exceeds_largest_class():
    with pytest.raises(NoVesselCapacityError):
        recommend_vessel(500_000, DEEP_PORT, PARADIP, VESSEL_CLASSES)


def test_raises_on_empty_vessel_class_list():
    with pytest.raises(ValueError):
        recommend_vessel(50_000, DEEP_PORT, PARADIP, [])


def test_small_cargo_gets_smallest_class():
    rec = recommend_vessel(15_000, DEEP_PORT, PARADIP, VESSEL_CLASSES)
    assert rec.vessel_class == VesselClass.HANDYSIZE
    assert rec.is_constrained is False


def test_reason_names_the_binding_constraint_when_infeasible():
    """Even Handysize (draft 10.0m) fits Gopalpur (12.5m), so build an
    impossibly shallow port to force the true infeasibility branch."""
    impossible_port = Port("p4", "TooShallow", max_draft_m=5.0, max_loa_m=100.0, max_beam_m=15.0)
    rec = recommend_vessel(15_000, DEEP_PORT, impossible_port, VESSEL_CLASSES)
    assert rec.is_constrained is True
    assert "TooShallow" in rec.reason
    assert "draft" in rec.reason.lower()


# --- TimingRecommendationService -------------------------------------------

def _make_forecast(rates: list[float]) -> Forecast:
    return Forecast(
        route_id="route-1",
        vessel_class=VesselClass.PANAMAX,
        horizon_days=len(rates),
        model_version="test",
        points=[
            ForecastPoint(day_offset=i, predicted_rate=r, lower_bound=r - 1, upper_bound=r + 1)
            for i, r in enumerate(rates)
        ],
    )


def test_top_window_covers_the_known_dip():
    # Flat at 20 except a clear 5-day dip to 10 starting at day 15.
    rates = [20.0] * 15 + [10.0] * 5 + [20.0] * 20
    forecast = _make_forecast(rates)

    windows = rank_windows(forecast, window_size_days=5, top_n=3)

    assert windows[0].rank == 1
    assert windows[0].start_day_offset == 15
    assert windows[0].end_day_offset == 19
    assert windows[0].avg_predicted_rate == 10.0


def test_windows_are_non_overlapping():
    rates = [20.0] * 15 + [10.0] * 5 + [20.0] * 5 + [12.0] * 5 + [20.0] * 10
    forecast = _make_forecast(rates)

    windows = rank_windows(forecast, window_size_days=5, top_n=3)

    for i in range(len(windows)):
        for j in range(i + 1, len(windows)):
            a, b = windows[i], windows[j]
            assert not (a.start_day_offset <= b.end_day_offset and b.start_day_offset <= a.end_day_offset)


def test_windows_ranked_ascending_by_avg_rate():
    rates = [20.0] * 10 + [15.0] * 5 + [20.0] * 10 + [10.0] * 5 + [20.0] * 10
    forecast = _make_forecast(rates)

    windows = rank_windows(forecast, window_size_days=5, top_n=2)

    assert windows[0].avg_predicted_rate <= windows[1].avg_predicted_rate
    assert windows[0].rank == 1
    assert windows[1].rank == 2


def test_returns_empty_list_when_forecast_shorter_than_window():
    forecast = _make_forecast([20.0, 21.0])
    assert rank_windows(forecast, window_size_days=5) == []


def test_rejects_invalid_window_size():
    forecast = _make_forecast([20.0] * 10)
    with pytest.raises(ValueError):
        rank_windows(forecast, window_size_days=0)
