import pytest

from domain.enums import VesselClass
from domain.models import InsufficientHistoryError
from application.forecasting_service import ForecastingService
from infrastructure.ml.ensemble import EnsembleForecastModel
from tests.fixtures.synthetic_data import generate_synthetic_history


class FakeRateRepository:
    """In-memory fake implementing RateRepositoryProtocol — no DB needed."""

    def __init__(self):
        self._store: dict[tuple[str, VesselClass], list] = {}

    def seed(self, route_id, vessel_class, history):
        self._store[(route_id, vessel_class)] = history

    def get_historical_rates(self, route_id, vessel_class):
        return self._store.get((route_id, vessel_class), [])


def test_raises_when_no_history_at_all():
    repo = FakeRateRepository()
    service = ForecastingService(repo)
    with pytest.raises(InsufficientHistoryError):
        service.generate_forecast("route-1", VesselClass.PANAMAX, horizon_days=60)


def test_raises_when_history_too_short():
    repo = FakeRateRepository()
    short_history = generate_synthetic_history("route-1", VesselClass.PANAMAX, days=30)
    repo.seed("route-1", VesselClass.PANAMAX, short_history)
    service = ForecastingService(repo)
    with pytest.raises(InsufficientHistoryError):
        service.generate_forecast("route-1", VesselClass.PANAMAX, horizon_days=60)


def test_generates_forecast_with_correct_shape():
    repo = FakeRateRepository()
    history = generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730)
    repo.seed("route-1", VesselClass.PANAMAX, history)
    service = ForecastingService(repo)

    forecast = service.generate_forecast("route-1", VesselClass.PANAMAX, horizon_days=60)

    assert forecast.route_id == "route-1"
    assert forecast.vessel_class == VesselClass.PANAMAX
    assert forecast.horizon_days == 60
    assert len(forecast.points) == 60
    assert forecast.model_version in ("prophet_only_v1", "prophet_xgb_residual_v1")

    # day_offsets must be sequential starting at 0
    assert [p.day_offset for p in forecast.points] == list(range(60))

    # bounds must be consistent for every point — this must hold by
    # construction (see ensemble.py's note on shifted bounds), not by luck
    for p in forecast.points:
        assert p.lower_bound <= p.predicted_rate <= p.upper_bound


def test_backtest_mape_is_reasonable_on_clean_synthetic_data():
    """This is the actual evidence the pipeline works, not just runs.
    Our synthetic data has a known trend + seasonality + modest noise,
    so a competent model should backtest well below a generous threshold."""
    history = generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730)
    model = EnsembleForecastModel()
    result = model.fit(history)

    assert result.chosen_mape < 15.0, (
        f"Backtest MAPE {result.chosen_mape:.2f}% is higher than expected for "
        f"clean synthetic data — investigate before trusting real forecasts"
    )


def test_ensemble_only_uses_residual_correction_if_it_actually_helps():
    """On this clean synthetic data (no real nonlinear structure beyond
    what Prophet already models), residual correction may or may not
    win — either outcome is fine, but the recorded MAPE values must be
    internally consistent with whichever was chosen."""
    history = generate_synthetic_history("route-1", VesselClass.PANAMAX, days=730)
    model = EnsembleForecastModel()
    result = model.fit(history)

    if result.used_residual_correction:
        assert result.combined_mape is not None
        assert result.chosen_mape == result.combined_mape
        assert result.combined_mape <= result.prophet_only_mape
    else:
        assert result.chosen_mape == result.prophet_only_mape
