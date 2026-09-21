"""
Application-layer service implementing FR-2 (freight rate forecasting).

Depends only on RateRepositoryProtocol and the ensemble model — never
touches FastAPI, Postgres, or JSON. This is what makes it possible to
test (and even demo) the actual forecasting logic in a plain Python
script or notebook, independent of the web layer.
"""

from __future__ import annotations

from domain.enums import VesselClass
from domain.models import Forecast, InsufficientHistoryError
from application.interfaces.rate_repository import RateRepositoryProtocol
from infrastructure.ml.ensemble import EnsembleForecastModel


class ForecastingService:
    def __init__(self, rate_repo: RateRepositoryProtocol):
        self._rate_repo = rate_repo

    def generate_forecast(
        self, route_id: str, vessel_class: VesselClass, horizon_days: int = 60
    ) -> Forecast:
        history = self._rate_repo.get_historical_rates(route_id, vessel_class)
        if not history:
            raise InsufficientHistoryError(
                f"No historical data found for route={route_id}, vessel_class={vessel_class}"
            )

        model = EnsembleForecastModel()
        backtest = model.fit(history)  # raises InsufficientHistoryError if too little data
        points = model.generate(route_id, vessel_class, horizon_days)

        return Forecast(
            route_id=route_id,
            vessel_class=vessel_class,
            horizon_days=horizon_days,
            model_version=backtest.model_version,
            points=points,
        )
