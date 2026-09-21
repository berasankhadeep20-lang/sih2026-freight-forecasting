"""
Loads a Baltic Dry Index (or sub-index) CSV into BaseIndexValue objects.

Deliberately format-agnostic about *which* Kaggle dataset you use — Kaggle
listings for BDI data change over time, and different exports use different
column names. What's fixed is the SHAPE this loader expects:

    Date column + one column per vessel class, e.g.:

        Date,       Capesize, Panamax, Supramax, Handysize
        2024-01-02, 4120,     1850,    980,      670
        2024-01-03, 4050,     1830,    ,         665      <- blank = market gap, dropped
        (weekends simply absent from the file — that's correct, not a bug)

If your downloaded dataset only has a single "BDI" composite column rather
than per-class sub-indices, see the note at the bottom of this file.

Design choice (see chat): we do NOT interpolate missing values. A blank
cell is either a genuine data gap or a market closure already excluded by
the source — either way, fabricating a number there would inject a fake
trend into training data. We drop incomplete rows and report how many,
so the team can decide if that's acceptable rather than it happening silently.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from domain.enums import VesselClass
from domain.models import BaseIndexValue

logger = logging.getLogger(__name__)


class IngestionError(ValueError):
    """Raised when the input CSV doesn't match the expected shape at all
    (e.g. missing date column) — as opposed to individual bad rows, which
    are dropped and counted instead of raising."""


def load_base_index_csv(
    csv_path: str | Path,
    column_map: dict[str, VesselClass],
    date_column: str = "Date",
    source_label: str = "Kaggle BDI historical dataset",
) -> list[BaseIndexValue]:
    """
    Parse a wide-format BDI CSV into a flat list of BaseIndexValue.

    Args:
        csv_path: path to the downloaded CSV.
        column_map: maps each sub-index column name in the CSV to the
            VesselClass it represents, e.g.
            {"Capesize": VesselClass.CAPESIZE, "Panamax": VesselClass.PANAMAX}
        date_column: name of the date column in the CSV.
        source_label: recorded on every BaseIndexValue for traceability
            (Schema §3.4's `source` field) — this is what lets anyone
            looking at the DB later see exactly which dataset a number
            came from.

    Returns:
        Flat list of BaseIndexValue, one per (date, vessel_class) pair
        that had a complete, parseable value.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise IngestionError(f"CSV not found at {csv_path}")

    results: list[BaseIndexValue] = []
    dropped_rows = 0
    seen_keys: set[tuple[VesselClass, datetime]] = set()

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None or date_column not in reader.fieldnames:
            raise IngestionError(
                f"Expected a '{date_column}' column; found columns: {reader.fieldnames}"
            )
        missing_cols = [c for c in column_map if c not in reader.fieldnames]
        if missing_cols:
            raise IngestionError(
                f"column_map references columns not in the CSV: {missing_cols}. "
                f"CSV columns are: {reader.fieldnames}"
            )

        for row_num, row in enumerate(reader, start=2):  # header is row 1
            raw_date = row.get(date_column, "").strip()
            trade_date = _parse_date(raw_date)
            if trade_date is None:
                logger.warning("Row %d: unparseable date %r — dropped", row_num, raw_date)
                dropped_rows += 1
                continue

            for column_name, vessel_class in column_map.items():
                raw_value = (row.get(column_name) or "").strip()
                if raw_value == "":
                    # Genuine gap — don't fabricate a value (see module docstring).
                    dropped_rows += 1
                    continue
                try:
                    value = float(raw_value.replace(",", ""))
                except ValueError:
                    logger.warning(
                        "Row %d: unparseable value %r for %s — dropped",
                        row_num, raw_value, column_name,
                    )
                    dropped_rows += 1
                    continue
                if value <= 0:
                    logger.warning(
                        "Row %d: non-positive index value %s for %s — dropped",
                        row_num, value, column_name,
                    )
                    dropped_rows += 1
                    continue

                key = (vessel_class, trade_date)
                if key in seen_keys:
                    logger.warning(
                        "Duplicate (date, vessel_class) %s — keeping first occurrence", key
                    )
                    continue
                seen_keys.add(key)

                results.append(
                    BaseIndexValue(
                        vessel_class=vessel_class,
                        trade_date=trade_date,
                        index_value=value,
                        source=source_label,
                    )
                )

    logger.info(
        "Loaded %d index values from %s (%d rows/cells dropped)",
        len(results), csv_path.name, dropped_rows,
    )
    return results


def _parse_date(raw: str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# If your dataset only has a single composite "BDI" column instead of
# per-class sub-indices, you have two honest options — do NOT invent a
# split:
#   1. Map that single column to just ONE VesselClass (e.g. Panamax, since
#      it historically tracks closest to the composite BDI) and document
#      that choice in the RouteAdjustmentFactor.notes field.
#   2. Find a dataset with the four sub-indices (BCI/BPI/BSI/BHSI) — these
#      are what map cleanly to Capesize/Panamax/Supramax/Handysize.
# Option 2 is strongly preferred if you can find it; it's what the schema
# and forecasting design assume.
# ---------------------------------------------------------------------------
