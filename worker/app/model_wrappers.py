from __future__ import annotations

import numpy as np


class ReturnBlendModel:
    """
    Blend a machine learning model prediction with a fixed ARIMA next-step forecast.
    The server only needs this class available for joblib loading.
    """

    def __init__(self, ml_model, arima_next_return: float, arima_weight: float = 0.25) -> None:
        self.ml_model = ml_model
        self.arima_next_return = float(arima_next_return)
        self.arima_weight = float(max(0.0, min(1.0, arima_weight)))

    def predict(self, x):
        ml_pred = np.asarray(self.ml_model.predict(x), dtype=float)
        return (1.0 - self.arima_weight) * ml_pred + self.arima_weight * self.arima_next_return
