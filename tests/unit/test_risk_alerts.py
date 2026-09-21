from datetime import datetime, timedelta, timezone

from domain.enums import AlertType, Severity, VesselClass
from domain.models import Forecast, ForecastPoint, Port
from application.risk_alert_service import evaluate

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_forecast(interval_ratio: float, predicted: float = 20.0, days: int = 10) -> Forecast:
    """Builds a forecast with a constant confidence-interval width equal
    to `interval_ratio` of the predicted rate, for controllable volatility tests."""
    half_width = predicted * interval_ratio / 2
    return Forecast(
        route_id="route-1",
        vessel_class=VesselClass.PANAMAX,
        horizon_days=days,
        model_version="test",
        points=[
            ForecastPoint(
                day_offset=i,
                predicted_rate=predicted,
                lower_bound=predicted - half_width,
                upper_bound=predicted + half_width,
            )
            for i in range(days)
        ],
    )


def _clear_port(name="Paradip", score=0.1, updated=NOW) -> Port:
    return Port(
        port_id=name, name=name, max_draft_m=18.0, max_loa_m=300.0, max_beam_m=45.0,
        congestion_score=score, congestion_updated_at=updated,
    )


# --- Volatility --------------------------------------------------------

def test_high_volatility_triggers_high_severity_alert():
    forecast = _make_forecast(interval_ratio=0.40)  # well above HIGH threshold (0.30)
    alerts = evaluate("route-1", _clear_port("A"), _clear_port("B"), forecast, evaluated_at=NOW)
    volatility_alerts = [a for a in alerts if a.alert_type == AlertType.VOLATILITY]
    assert len(volatility_alerts) == 1
    assert volatility_alerts[0].severity == Severity.HIGH


def test_moderate_volatility_triggers_medium_severity_alert():
    forecast = _make_forecast(interval_ratio=0.20)  # between MEDIUM (0.15) and HIGH (0.30)
    alerts = evaluate("route-1", _clear_port("A"), _clear_port("B"), forecast, evaluated_at=NOW)
    volatility_alerts = [a for a in alerts if a.alert_type == AlertType.VOLATILITY]
    assert len(volatility_alerts) == 1
    assert volatility_alerts[0].severity == Severity.MEDIUM


def test_low_volatility_triggers_no_alert():
    forecast = _make_forecast(interval_ratio=0.05)  # well under MEDIUM threshold
    alerts = evaluate("route-1", _clear_port("A"), _clear_port("B"), forecast, evaluated_at=NOW)
    volatility_alerts = [a for a in alerts if a.alert_type == AlertType.VOLATILITY]
    assert volatility_alerts == []


# --- Congestion: missing / stale data (NFR-5) ---------------------------

def test_missing_congestion_score_produces_data_unavailable_not_silence():
    forecast = _make_forecast(interval_ratio=0.05)
    port_no_data = Port("X", "Unknown Port", 18.0, 300.0, 45.0, congestion_score=None)
    alerts = evaluate("route-1", port_no_data, _clear_port("B"), forecast, evaluated_at=NOW)
    unavailable = [
        a for a in alerts
        if a.alert_type == AlertType.DATA_UNAVAILABLE and "Unknown Port" in a.message
    ]
    assert len(unavailable) == 1


def test_stale_congestion_data_produces_data_unavailable():
    stale_port = _clear_port("StalePort", score=0.1, updated=NOW - timedelta(days=30))
    forecast = _make_forecast(interval_ratio=0.05)
    alerts = evaluate("route-1", stale_port, _clear_port("B"), forecast, evaluated_at=NOW)
    unavailable = [
        a for a in alerts
        if a.alert_type == AlertType.DATA_UNAVAILABLE and "StalePort" in a.message
    ]
    assert len(unavailable) == 1
    assert "30 days old" in unavailable[0].message


def test_fresh_congestion_data_does_not_trigger_data_unavailable():
    fresh_port = _clear_port("Fresh", score=0.1, updated=NOW - timedelta(days=1))
    forecast = _make_forecast(interval_ratio=0.05)
    alerts = evaluate("route-1", fresh_port, _clear_port("B"), forecast, evaluated_at=NOW)
    unavailable = [a for a in alerts if a.alert_type == AlertType.DATA_UNAVAILABLE]
    assert unavailable == []


# --- Congestion: real scores ---------------------------------------------

def test_high_congestion_triggers_high_severity_alert():
    congested = _clear_port("Busy", score=0.85)
    forecast = _make_forecast(interval_ratio=0.05)
    alerts = evaluate("route-1", congested, _clear_port("B"), forecast, evaluated_at=NOW)
    congestion_alerts = [a for a in alerts if a.alert_type == AlertType.CONGESTION]
    assert len(congestion_alerts) == 1
    assert congestion_alerts[0].severity == Severity.HIGH
    assert "Busy" in congestion_alerts[0].message


def test_low_congestion_triggers_no_alert():
    clear = _clear_port("VeryClear", score=0.05)
    forecast = _make_forecast(interval_ratio=0.05)
    alerts = evaluate("route-1", clear, _clear_port("B"), forecast, evaluated_at=NOW)
    congestion_alerts = [a for a in alerts if a.alert_type == AlertType.CONGESTION]
    assert congestion_alerts == []


def test_both_ports_can_each_produce_their_own_alert():
    busy_origin = _clear_port("OriginBusy", score=0.9)
    busy_dest = _clear_port("DestBusy", score=0.75)
    forecast = _make_forecast(interval_ratio=0.05)
    alerts = evaluate("route-1", busy_origin, busy_dest, forecast, evaluated_at=NOW)
    congestion_alerts = [a for a in alerts if a.alert_type == AlertType.CONGESTION]
    assert len(congestion_alerts) == 2
    messages = " ".join(a.message for a in congestion_alerts)
    assert "OriginBusy" in messages and "DestBusy" in messages


def test_all_alert_route_ids_match_input_route():
    congested = _clear_port("Busy", score=0.9)
    forecast = _make_forecast(interval_ratio=0.40)
    alerts = evaluate("my-route-42", congested, _clear_port("B"), forecast, evaluated_at=NOW)
    assert len(alerts) > 0
    assert all(a.route_id == "my-route-42" for a in alerts)
