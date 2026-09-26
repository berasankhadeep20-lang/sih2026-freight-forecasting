"""
Combines ProphetModel + XGBoostResidualModel, but — critically — only
uses the XGBoost correction if backtesting shows it actually reduces
error on held-out data. This is the concrete implementation of the
"validate before you trust an ensemble" principle from the architecture
doc: we don't assume combining models helps, we check.

Backtest procedure:
  1. Split history into train / validation (validation = most recent
     N days, since that's the realistic use case — forecasting forward
     from "today").
  2. Fit Prophet on train only; measure MAPE on validation.
  3. Fit the residual model on train's residuals; use it to predict
     validation-period residuals; measure MAPE of (prophet + residual)
     on validation.
  4. Whichever has lower validation MAPE wins. If the residual model
     can't be fit (not enough data), Prophet-only wins by default.
  5. Refit the winning configuration on the FULL history (train +
     validation) before generating the actual future forecast — the
     backtest split was only for model selection, not for throwing
     away usable training data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from domain.enums import VesselClass
from domain.models import ForecastPoint, InsufficientHistoryError, RouteFreightRate
from infrastructure.ml.prophet_model import ProphetModel
from infrastructure.ml.xgboost_residual_model import (
    InsufficientResidualHistoryError,
    XGBoostResidualModel,
)

MIN_TOTAL_HISTORY_DAYS = 180  # ~6 months minimum before we trust any seasonal fit
VALIDATION_DAYS = 60  # matches the 60-day forecast horizon we actually need


def _mape(actual: list[float], predicted: list[float]) -> float:
    a = np.array(actual)
    p = np.array(predicted)
    return float(np.mean(np.abs((a - p) / a)) * 100)


@dataclass
class BacktestResult:
    used_residual_correction: bool
    prophet_only_mape: float
    combined_mape: float | None
    chosen_mape: float
    model_version: str


class EnsembleForecastModel:
    def __init__(self):
        self._final_prophet: ProphetModel | None = None
        self._final_xgb: XGBoostResidualModel | None = None
        self._use_residual_correction = False
        self._history: list[RouteFreightRate] = []
        self.backtest_result: BacktestResult | None = None

    def fit(self, history: list[RouteFreightRate]) -> BacktestResult:
        history = sorted(history, key=lambda r: r.trade_date)
        if len(history) < MIN_TOTAL_HISTORY_DAYS:
            raise InsufficientHistoryError(
                f"Need at least {MIN_TOTAL_HISTORY_DAYS} days of history for a "
                f"responsible seasonal fit, got {len(history)}"
            )

        train = history[:-VALIDATION_DAYS]
        validation = history[-VALIDATION_DAYS:]

        # --- Step 1: Prophet on train, measure on validation -------------
        prophet_train = ProphetModel()
        prophet_train.fit(train)
        val_pred = prophet_train.predict_future(train[-1].trade_date, len(validation))
        prophet_only_mape = _mape(
            [r.adjusted_rate_usd_per_day for r in validation], val_pred["yhat"].tolist()
        )

        # --- Step 2: residual model on train, try to beat step 1 ----------
        combined_mape = None
        can_use_residual = False
        try:
            train_fit = prophet_train.predict_in_sample(train)
            train_residuals = [
                actual.adjusted_rate_usd_per_day - fitted
                for actual, fitted in zip(train, train_fit["yhat"].tolist())
            ]
            xgb_train = XGBoostResidualModel()
            xgb_train.fit(train_residuals)
            residual_forecast = xgb_train.predict_future(len(validation))
            combined_pred = [
                p + r for p, r in zip(val_pred["yhat"].tolist(), residual_forecast)
            ]
            combined_mape = _mape(
                [r.adjusted_rate_usd_per_day for r in validation], combined_pred
            )
            can_use_residual = True
        except InsufficientResidualHistoryError:
            pass  # not enough data for lag features — Prophet-only will be used

        # --- Step 3: choose ------------------------------------------------
        if can_use_residual and combined_mape < prophet_only_mape:
            self._use_residual_correction = True
            chosen_mape = combined_mape
            model_version = "prophet_xgb_residual_v1"
        else:
            self._use_residual_correction = False
            chosen_mape = prophet_only_mape
            model_version = "prophet_only_v1"

        self.backtest_result = BacktestResult(
            used_residual_correction=self._use_residual_correction,
            prophet_only_mape=prophet_only_mape,
            combined_mape=combined_mape,
            chosen_mape=chosen_mape,
            model_version=model_version,
        )

        # --- Step 4: refit chosen configuration on FULL history -----------
        self._final_prophet = ProphetModel()
        self._final_prophet.fit(history)

        if self._use_residual_correction:
            full_fit = self._final_prophet.predict_in_sample(history)
            full_residuals = [
                actual.adjusted_rate_usd_per_day - fitted
                for actual, fitted in zip(history, full_fit["yhat"].tolist())
            ]
            self._final_xgb = XGBoostResidualModel()
            self._final_xgb.fit(full_residuals)

        self._history = history
        return self.backtest_result

    def generate(
        self, route_id: str, vessel_class: VesselClass, horizon_days: int
    ) -> list[ForecastPoint]:
        if self._final_prophet is None:
            raise RuntimeError("EnsembleForecastModel.fit() must be called before generate()")

        last_date = self._history[-1].trade_date
        future = self._final_prophet.predict_future(last_date, horizon_days)

        if self._use_residual_correction:
            residual_forecast = self._final_xgb.predict_future(horizon_days)
        else:
            residual_forecast = [0.0] * horizon_days

        points = []
        for day_offset, (row, residual) in enumerate(
            zip(future.itertuples(), residual_forecast)
        ):
            predicted = row.yhat + residual
            # Bounds are Prophet's interval shifted by the same residual
            # correction — an approximation (the residual model has its
            # own uncertainty we're not separately quantifying yet), but
            # a documented, defensible one rather than a silent one.
            points.append(
                ForecastPoint(
                    day_offset=day_offset,
                    predicted_rate=round(predicted, 2),
                    lower_bound=round(row.yhat_lower + residual, 2),
                    upper_bound=round(row.yhat_upper + residual, 2),
                )
            )
        return points
