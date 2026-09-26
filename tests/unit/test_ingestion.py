import math
from datetime import date
from pathlib import Path

import pytest

from domain.enums import VesselClass
from domain.models import BaseIndexValue, RouteAdjustmentFactor
from infrastructure.ingestion.kaggle_loader import IngestionError, load_base_index_csv
from infrastructure.ingestion.route_adjustment import (
    apply_route_adjustment,
    seasonal_component,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_bdi.csv"

COLUMN_MAP = {
    "Capesize": VesselClass.CAPESIZE,
    "Panamax": VesselClass.PANAMAX,
    "Supramax": VesselClass.SUPRAMAX,
    "Handysize": VesselClass.HANDYSIZE,
}


def test_loads_expected_row_count():
    """10 rows x 4 columns = 40 cells; fixture has 1 blank + 1 negative
    value deliberately planted, so we expect exactly 38 valid readings."""
    values = load_base_index_csv(FIXTURE, COLUMN_MAP)
    assert len(values) == 38


def test_drops_blank_cell_not_fabricates_it():
    """The blank Supramax cell on 2024-01-02 must be ABSENT, not filled
    with an interpolated/zero value — per the ingestion design principle."""
    values = load_base_index_csv(FIXTURE, COLUMN_MAP)
    supramax_jan2 = [
        v for v in values
        if v.vessel_class == VesselClass.SUPRAMAX and v.trade_date == date(2024, 1, 2)
    ]
    assert supramax_jan2 == []


def test_drops_non_positive_value():
    """The planted -50 Capesize value on 2024-01-10 must be rejected."""
    values = load_base_index_csv(FIXTURE, COLUMN_MAP)
    bad = [
        v for v in values
        if v.vessel_class == VesselClass.CAPESIZE and v.trade_date == date(2024, 1, 10)
    ]
    assert bad == []


def test_every_value_has_source_and_positive_value():
    values = load_base_index_csv(FIXTURE, COLUMN_MAP)
    assert len(values) > 0
    for v in values:
        assert v.index_value > 0
        assert v.source == "Kaggle BDI historical dataset"
        assert isinstance(v, BaseIndexValue)


def test_missing_csv_raises_ingestion_error():
    with pytest.raises(IngestionError):
        load_base_index_csv("does_not_exist.csv", COLUMN_MAP)


def test_missing_column_in_map_raises_ingestion_error():
    bad_map = {"NotAColumn": VesselClass.CAPESIZE}
    with pytest.raises(IngestionError):
        load_base_index_csv(FIXTURE, bad_map)


# --- route_adjustment.py -----------------------------------------------

def test_seasonal_component_bounded():
    for day in range(1, 366):
        assert -1.0 <= seasonal_component(day) <= 1.0


def test_route_adjustment_formula_by_hand():
    """Verify the transform against a hand-computed expectation for one
    known input — this is the 'can a human check this in one line' test
    the design is meant to support."""
    base = [
        BaseIndexValue(
            vessel_class=VesselClass.PANAMAX,
            trade_date=date(2024, 1, 1),
            index_value=1000.0,
            source="test",
        )
    ]
    factor = RouteAdjustmentFactor(
        route_id="route-1",
        vessel_class=VesselClass.PANAMAX,
        base_multiplier=1.5,
        seasonal_amplitude=0.1,
        notes="test factor",
    )
    result = apply_route_adjustment(base, factor)
    assert len(result) == 1

    expected_seasonal = math.sin(2 * math.pi * 1 / 365.25)  # day-of-year 1
    expected_rate = round(1000.0 * 1.5 * (1 + 0.1 * expected_seasonal), 2)
    assert result[0].adjusted_rate_usd_per_day == expected_rate
    assert result[0].route_id == "route-1"


def test_route_adjustment_filters_by_vessel_class():
    """A Capesize base value must not leak into a Panamax route's output."""
    base = [
        BaseIndexValue(VesselClass.CAPESIZE, date(2024, 1, 1), 4000.0, "test"),
        BaseIndexValue(VesselClass.PANAMAX, date(2024, 1, 1), 1800.0, "test"),
    ]
    factor = RouteAdjustmentFactor(
        route_id="route-1", vessel_class=VesselClass.PANAMAX,
        base_multiplier=1.0, seasonal_amplitude=0.0,
    )
    result = apply_route_adjustment(base, factor)
    assert len(result) == 1
    assert result[0].vessel_class == VesselClass.PANAMAX
