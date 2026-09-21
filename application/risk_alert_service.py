"""
Application-layer service implementing FR-6 (risk alerts).

Pure function over a Forecast and the two ports involved — no repository
dependency, same reasoning as vessel_matching_service.py: the orchestrator
already has these objects, so injecting a repository here would only add
an untestable dependency for no benefit.

The congestion-staleness check is the concrete implementation of NFR-5
("graceful degradation... a visible notice, rather than failing
entirely"): missing or stale congestion data becomes its own alert
(AlertType.DATA_UNAVAILABLE), not a silent skip. Silently omitting an
alert because the underlying data was stale would look identical to
"we checked and it's fine" — which is a worse failure mode than saying
"we don't know."
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from domain.enums import AlertType, Severity
from domain.models import Forecast, Port, RiskAlert

# Volatility thresholds: mean (upper_bound - lower_bound) / predicted_rate
# across the forecast horizon. These are starting points, not tuned
# constants — revisit once you have real backtest data showing what
# "normal" interval width looks like for your actual routes.
VOLATILITY_HIGH_THRESHOLD = 0.30
VOLATILITY_MEDIUM_THRESHOLD = 0.15

# Congestion thresholds, on the 0 (clear) to 1 (severe) scale from Schema §3.1.
CONGESTION_HIGH_THRESHOLD = 0.7
CONGESTION_MEDIUM_THRESHOLD = 0.4

CONGESTION_STALENESS_DAYS = 14


def evaluate(
    route_id: str,
    origin_port: Port,
    destination_port: Port,
    forecast: Forecast,
    evaluated_at: datetime | None = None,
) -> list[RiskAlert]:
    """
    evaluated_at is injectable (defaults to now) specifically so tests
    can control "the current time" without depending on the real clock —
    otherwise a staleness test would be flaky depending on when it runs.
    """
    now = evaluated_at or datetime.now(timezone.utc)
    alerts: list[RiskAlert] = []

    volatility_alert = _check_volatility(route_id, forecast)
    if volatility_alert:
        alerts.append(volatility_alert)

    for port, role in [(origin_port, "origin"), (destination_port, "destination")]:
        alerts.append(_check_congestion(route_id, port, role, now))

    # _check_congestion always returns something for a stale/missing port,
    # but returns None when congestion is simply low — filter those out.
    return [a for a in alerts if a is not None]


def _check_volatility(route_id: str, forecast: Forecast) -> RiskAlert | None:
    if not forecast.points:
        return None

    ratios = [
        (p.upper_bound - p.lower_bound) / p.predicted_rate
        for p in forecast.points
        if p.predicted_rate > 0
    ]
    if not ratios:
        return None
    avg_ratio = sum(ratios) / len(ratios)

    if avg_ratio >= VOLATILITY_HIGH_THRESHOLD:
        severity = Severity.HIGH
    elif avg_ratio >= VOLATILITY_MEDIUM_THRESHOLD:
        severity = Severity.MEDIUM
    else:
        return None

    return RiskAlert(
        route_id=route_id,
        alert_type=AlertType.VOLATILITY,
        severity=severity,
        message=(
            f"Forecast uncertainty is elevated for this route: the confidence "
            f"interval averages {avg_ratio * 100:.0f}% of the predicted rate over "
            f"the horizon. Treat point estimates with more caution than usual."
        ),
    )


def _check_congestion(
    route_id: str, port: Port, role: str, now: datetime
) -> RiskAlert | None:
    if port.congestion_score is None:
        return RiskAlert(
            route_id=route_id,
            alert_type=AlertType.DATA_UNAVAILABLE,
            severity=Severity.LOW,
            message=(
                f"No congestion data is on file for {port.name} ({role} port). "
                f"Congestion risk for this port could not be assessed."
            ),
        )

    if port.congestion_updated_at is not None:
        age = now - port.congestion_updated_at
        if age > timedelta(days=CONGESTION_STALENESS_DAYS):
            return RiskAlert(
                route_id=route_id,
                alert_type=AlertType.DATA_UNAVAILABLE,
                severity=Severity.LOW,
                message=(
                    f"Congestion data for {port.name} ({role} port) is "
                    f"{age.days} days old (last updated {port.congestion_updated_at.date()}), "
                    f"older than the {CONGESTION_STALENESS_DAYS}-day freshness threshold. "
                    f"Treat current congestion status as unknown rather than assuming it's clear."
                ),
            )

    score = port.congestion_score
    if score >= CONGESTION_HIGH_THRESHOLD:
        severity = Severity.HIGH
    elif score >= CONGESTION_MEDIUM_THRESHOLD:
        severity = Severity.MEDIUM
    else:
        return None  # low congestion — nothing worth flagging

    return RiskAlert(
        route_id=route_id,
        alert_type=AlertType.CONGESTION,
        severity=severity,
        message=(
            f"{port.name} ({role} port) has an elevated congestion score of "
            f"{score:.2f}. Expect possible delays affecting turnaround time."
        ),
    )
