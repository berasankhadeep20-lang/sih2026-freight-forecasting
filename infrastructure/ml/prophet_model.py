"""
Thin wrapper around Prophet.

Kept deliberately small: this class's only job is to translate between
our domain types (list[RouteFreightRate]) and Prophet's required
DataFrame shape (columns 'ds', 'y'), and back. All the actual modeling
decisions (which seasonalities to enable, interval width) live here as
named, documented arguments — not scattered through the service layer.
"""

from __future__ import annotations

import pandas as pd
from prophet import Prophet

from domain.models import RouteFreightRate


class ProphetModel:
    def __init__(self, interval_width: float = 0.80):
        """
        interval_width=0.80 means Prophet's yhat_lower/yhat_upper form an
        80% confidence interval. We use 80% rather than the library's
        default 80% ... actually the library default IS 0.80 — kept
        explicit here rather than relying on an implicit default, so a
        future reader doesn't have to check Prophet's source to know
        what our bounds mean.
        """
        # yearly_seasonality=True: freight demand has a real annual cycle
        #   (coal/power demand, harvest-driven grain shipments).
        # weekly_seasonality=False: bulk charter rates don't have a
        #   meaningful day-of-week pattern the way, say, retail sales do —
        #   enabling it would just fit noise.
        # daily_seasonality=False: our data is daily-resolution already,
        #   there's no sub-day pattern to speak of.
        self._model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            interval_width=interval_width,
        )
        self._fitted = False

    def fit(self, history: list[RouteFreightRate]) -> None:
        df = pd.DataFrame(
            {
                "ds": [r.trade_date for r in history],
                "y": [r.adjusted_rate_usd_per_day for r in history],
            }
        )
        self._model.fit(df)
        self._fitted = True

    def predict_in_sample(self, history: list[RouteFreightRate]) -> pd.DataFrame:
        """Returns Prophet's fitted values for the SAME dates as `history`
        — used by the residual model to compute (actual - fitted)."""
        self._require_fitted()
        df = pd.DataFrame({"ds": [r.trade_date for r in history]})
        return self._model.predict(df)[["ds", "yhat"]]

    def predict_future(self, last_date, horizon_days: int) -> pd.DataFrame:
        """Returns yhat/yhat_lower/yhat_upper for the `horizon_days`
        AFTER last_date (not including in-sample dates)."""
        self._require_fitted()
        future_dates = pd.date_range(
            start=pd.Timestamp(last_date) + pd.Timedelta(days=1),
            periods=horizon_days,
            freq="D",
        )
        future_df = pd.DataFrame({"ds": future_dates})
        forecast = self._model.predict(future_df)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    def _require_fitted(self):
        if not self._fitted:
            raise RuntimeError("ProphetModel.fit() must be called before predicting")
