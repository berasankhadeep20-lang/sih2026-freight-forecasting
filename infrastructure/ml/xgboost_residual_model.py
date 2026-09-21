"""
XGBoost residual-correction model.

Does NOT predict the freight rate directly. It predicts the residual
(actual_rate - prophet_fitted_rate) using lag features of that residual
series, then forecasts are corrected as:

    final_prediction = prophet_yhat + predicted_residual

Why residuals and not the raw rate: Prophet already captures trend and
yearly seasonality well. Asking XGBoost to re-learn the raw rate from
scratch would waste its capacity re-deriving what Prophet already got
right, and small tree ensembles trained on raw price levels tend to
just echo the last few lags rather than adding new information. Residual
modeling focuses XGBoost on exactly what's left to explain.

Multi-step forecasting is done recursively: predict day+1's residual,
append it to the lag history, use it to help predict day+2, and so on.
This is the standard (if imperfect) approach for tree models on
sequential data — errors can compound over a long horizon, which is
part of why the ensemble module backtests whether this actually helps
before trusting it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

MIN_HISTORY_FOR_LAGS = 15  # need at least lag_14 + 1 target row


class InsufficientResidualHistoryError(ValueError):
    pass


def _build_lag_features(residuals: list[float]) -> pd.DataFrame:
    """Builds a supervised-learning frame: each row's features are lags
    of the residual series, target is the residual itself."""
    s = pd.Series(residuals)
    df = pd.DataFrame(
        {
            "lag_1": s.shift(1),
            "lag_7": s.shift(7),
            "lag_14": s.shift(14),
            "rolling_mean_7": s.shift(1).rolling(7).mean(),
            "target": s,
        }
    )
    return df.dropna()


class XGBoostResidualModel:
    def __init__(self, n_estimators: int = 100, max_depth: int = 3):
        # max_depth kept shallow (3) deliberately: this model has only a
        # handful of lag features and a modest amount of training data
        # for a hackathon-scope dataset — a deep tree ensemble here would
        # overfit the residual noise rather than learn real structure.
        self._model = XGBRegressor(
            n_estimators=n_estimators, max_depth=max_depth, verbosity=0
        )
        self._fitted = False
        self._history_residuals: list[float] = []

    def fit(self, residuals: list[float]) -> None:
        if len(residuals) < MIN_HISTORY_FOR_LAGS:
            raise InsufficientResidualHistoryError(
                f"Need at least {MIN_HISTORY_FOR_LAGS} residual points, got {len(residuals)}"
            )
        frame = _build_lag_features(residuals)
        X = frame.drop(columns=["target"])
        y = frame["target"]
        self._model.fit(X, y)
        self._fitted = True
        self._history_residuals = list(residuals)

    def predict_future(self, horizon_days: int) -> list[float]:
        """Recursively predicts `horizon_days` future residuals."""
        if not self._fitted:
            raise RuntimeError("XGBoostResidualModel.fit() must be called before predicting")

        working_series = list(self._history_residuals)
        predictions: list[float] = []

        for _ in range(horizon_days):
            lag_1 = working_series[-1]
            lag_7 = working_series[-7] if len(working_series) >= 7 else np.mean(working_series)
            lag_14 = working_series[-14] if len(working_series) >= 14 else np.mean(working_series)
            rolling_mean_7 = np.mean(working_series[-7:])

            features = pd.DataFrame(
                [{
                    "lag_1": lag_1,
                    "lag_7": lag_7,
                    "lag_14": lag_14,
                    "rolling_mean_7": rolling_mean_7,
                }]
            )
            next_residual = float(self._model.predict(features)[0])
            predictions.append(next_residual)
            working_series.append(next_residual)

        return predictions
