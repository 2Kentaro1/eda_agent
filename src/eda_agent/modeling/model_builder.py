import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_squared_error
import numpy as np
from pathlib import Path
import json

class ModelBuilder:
    """
    Feature Engineer と Modeler の JSON 出力をもとに
    実際に LightGBM モデルを構築するクラス。
    """

    def __init__(self, df, feature_json, model_json):
        self.df = df.copy()
        self.feature_json = feature_json
        self.model_json = model_json

    # -------------------------
    # 特徴量生成
    # -------------------------
    def generate_features(self):
        feature_list = self.feature_json["feature_list"]

        for f in feature_list:
            name = f["name"]
            formula = f["formula"]

            # ★ formula を Python として実行する
            # 例: "df['temp_ma3'] = df['temperature'].rolling(3).mean()"
            exec(formula, {"df": self.df})

        return self.df

    # -------------------------
    # モデル構築
    # -------------------------
    def train_model(self):
        model_plan = self.model_json["model_plan"]

        features = model_plan["features_to_use"]
        target = "y"

        train_df = self.df.dropna(subset=[target])

        X = train_df[features]
        y = train_df[target]

        train_data = lgb.Dataset(X, label=y)

        params = {
            "objective": "regression",
            "metric": "rmse",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "seed": 42
        }

        model = lgb.train(params, train_data, num_boost_round=300)

        self.model = model
        self.features = features

        return model

    # -------------------------
    # 評価（RMSE）
    # -------------------------
    def evaluate(self):
        train_df = self.df.dropna(subset=["y"])
        preds = self.model.predict(train_df[self.features])
        rmse = np.sqrt(mean_squared_error(train_df["y"], preds))
        return rmse

    # -------------------------
    # 予測
    # -------------------------
    def predict(self, df_test):
        return self.model.predict(df_test[self.features])

    # -------------------------
    # 提出ファイル生成
    # -------------------------
    def save_submission(self, df_test, preds, path="submission.csv"):
        sub = pd.DataFrame({
            "datetime": df_test["datetime"],
            "pred": preds
        })

        # SIGNATE仕様：yyyy-m-d（ゼロ埋めなし）
        sub["datetime"] = pd.to_datetime(sub["datetime"]).dt.strftime("%Y-%-m-%-d")

        sub.to_csv(path, index=False, header=False, encoding="utf-8")
        print(f"Saved submission to {path}")