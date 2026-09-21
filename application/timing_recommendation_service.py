"""
Application-layer service implementing FR-4 (market entry timing).

Takes no constructor dependencies at all — it's a pure function of a
Forecast, which the module breakdown doc flags as deliberately the
simplest possible unit to test. It doesn't forecast anything itself;
it only ranks windows within a forecast someone else already produced.

Windows are chosen to be NON-OVERLAPPING: presenting a user with three
top-ranked windows that all cover the same three days isn't three
options, it's one option said three times. Non-overlap is what makes
the ranked list actually useful.
"""

from __future__ import annotations

from domain.models import Forecast, TimingWindow


def rank_windows(
    forecast: Forecast, window_size_days: int = 5, top_n: int = 3
) -> list[TimingWindow]:
    if window_size_days < 1:
        raise ValueError("window_size_days must be at least 1")
    if len(forecast.points) < window_size_days:
        return []  # forecast too short to form even one window

    points = sorted(forecast.points, key=lambda p: p.day_offset)

    candidates = []
    for start in range(0, len(points) - window_size_days + 1):
        window_points = points[start : start + window_size_days]
        avg_rate = sum(p.predicted_rate for p in window_points) / window_size_days
        candidates.append(
            (window_points[0].day_offset, window_points[-1].day_offset, avg_rate)
        )

    # Cheapest average first — these are the windows we'd rank highest.
    candidates.sort(key=lambda c: c[2])

    selected: list[tuple[int, int, float]] = []
    for start_offset, end_offset, avg_rate in candidates:
        if any(_overlaps(start_offset, end_offset, s, e) for s, e, _ in selected):
            continue
        selected.append((start_offset, end_offset, avg_rate))
        if len(selected) == top_n:
            break

    return [
        TimingWindow(
            rank=i + 1,
            start_day_offset=start,
            end_day_offset=end,
            avg_predicted_rate=round(avg, 2),
        )
        for i, (start, end, avg) in enumerate(selected)
    ]


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end
