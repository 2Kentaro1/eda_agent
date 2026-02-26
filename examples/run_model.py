import json
import pandas as pd

from src.eda_agent.modeling.model_builder import ModelBuilder

# データ読み込み
df = pd.read_csv("data/train.csv")
df_test = pd.read_csv("data/test.csv")

# JSON 読み込み
feature_json = json.load(open("src/eda_agent/orchestrator/io/output.json"))["feature_engineer"]
model_json = json.load(open("src/eda_agent/orchestrator/io/output.json"))["modeler"]

# モデル構築
builder = ModelBuilder(df, feature_json, model_json)

df_feat = builder.generate_features()
model = builder.train_model()

rmse = builder.evaluate()
print("RMSE:", rmse)

# 予測
preds = builder.predict(df_test)

# 提出ファイル生成
builder.save_submission(df_test, preds, "submission.csv")