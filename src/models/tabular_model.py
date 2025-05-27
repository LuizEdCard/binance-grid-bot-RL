import os
import pickle

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

MODEL_PATH = os.path.join(os.path.dirname(__file__), "tabular_model.pkl")


class TabularTradingModel:
    def __init__(self):
        self.model = None
        if os.path.exists(MODEL_PATH):
            self.load()

    def train(self, X: np.ndarray, y: np.ndarray):
        self.model = XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        self.model.fit(X, y)
        self.save()

    def predict(self, X: np.ndarray):
        if self.model is None:
            raise Exception("Model not trained!")
        return self.model.predict(X)

    def save(self):
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)

    def load(self):
        with open(MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)


# Função utilitária para preparar dados (exemplo)


def prepare_features(df: pd.DataFrame):
    features = (
        df[["close", "volume", "rsi", "macd", "macd_hist", "volatility"]]
        .fillna(0)
        .values
    )
    return features


def prepare_target(df: pd.DataFrame):
    # Exemplo: prever se o preço vai subir (1) ou cair (0) no próximo candle
    return (df["close"].shift(-1) > df["close"]).astype(int).values
