import json
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

def build_model_notebook(model_coder_json_path: str, output_path: str):
    """
    Model Coder の JSON 出力から、実行可能な Notebook を生成する。
    """

    # -----------------------------
    # 1. JSON の読み込み
    # -----------------------------
    with open(model_coder_json_path, "r", encoding="utf-8") as f:
        mc = json.load(f)

    imports = mc["content"]["imports"]
    data_prep_code = mc["content"]["data_prep_code"]
    training_code = mc["content"]["training_code"]
    evaluation_code = mc["content"]["evaluation_code"]

    # -----------------------------
    # 2. Notebook の初期化
    # -----------------------------
    nb = new_notebook()
    cells = []

    # -----------------------------
    # 3. Header
    # -----------------------------
    cells.append(new_markdown_cell("# 📘 Model Training Notebook\nGenerated from Model Coder Output"))

    # -----------------------------
    # 4. Imports セル
    # -----------------------------
    import_block = "\n".join(imports)
    cells.append(new_markdown_cell("## 🔧 Imports"))
    cells.append(new_code_cell(import_block))

    # -----------------------------
    # 5. Data Preparation セル
    # -----------------------------
    cells.append(new_markdown_cell("## 📊 Data Preparation"))
    cells.append(new_code_cell(data_prep_code))

    # -----------------------------
    # 6. Training セル
    # -----------------------------
    cells.append(new_markdown_cell("## 🤖 Model Training"))
    training_block = "\n".join(training_code)
    cells.append(new_code_cell(training_block))

    # -----------------------------
    # 7. Evaluation セル
    # -----------------------------
    cells.append(new_markdown_cell("## 📈 Evaluation"))
    evaluation_block = "\n".join(evaluation_code)
    cells.append(new_code_cell(evaluation_block))

    # -----------------------------
    # 8. Notebook 保存
    # -----------------------------
    nb["cells"] = cells
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print(f"Notebook saved to: {output_path}")

# 推論用Notebook生成コード
def build_predict_notebook(model_coder_json_path: str, output_path: str):
    """
    Model Coder の JSON 出力をもとに、推論用 Notebook (predict.ipynb) を生成する。
    """

    # -----------------------------
    # 1. JSON の読み込み
    # -----------------------------
    with open(model_coder_json_path, "r", encoding="utf-8") as f:
        mc = json.load(f)

    imports = mc["content"]["imports"]

    # -----------------------------
    # 2. Notebook 初期化
    # -----------------------------
    nb = new_notebook()
    cells = []

    # -----------------------------
    # 3. Header
    # -----------------------------
    cells.append(new_markdown_cell("# 🔮 Model Prediction Notebook\nGenerated from Model Coder Output"))

    # -----------------------------
    # 4. Imports セル
    # -----------------------------
    import_block = "\n".join(imports + [
        "import pickle",
        "import pandas as pd",
        "import numpy as np"
    ])
    cells.append(new_markdown_cell("## 🔧 Imports"))
    cells.append(new_code_cell(import_block))

    # -----------------------------
    # 5. モデル読み込み
    # -----------------------------
    load_model_code = """
# Load trained models
with open("trained_lightgbm.pkl", "rb") as f:
    model_lgb = pickle.load(f)

with open("trained_ridge.pkl", "rb") as f:
    model_ridge = pickle.load(f)

print("Models loaded successfully.")
"""
    cells.append(new_markdown_cell("## 📦 Load Trained Models"))
    cells.append(new_code_cell(load_model_code))

    # -----------------------------
    # 6. 推論データ準備
    # -----------------------------
    prep_code = """
# Load inference data
df_pred = pd.read_csv("inference_data.csv")

# Feature construction (same as training)
# ※ 必要に応じて Model Coder の data_prep_code を再利用
# ここでは例として特徴量を抽出
feature_cols = [
    "days_since_start",
    "is_monday",
    "temperature_capped",
    "is_cold",
    "is_payday",
    "is_otanoshimi",
    "menu_category",
    "cooking_method",
    "lag1_y",
    "lag7_y",
    "rolling_mean_7d"
]

X_pred = df_pred[feature_cols]

print("Prediction dataset prepared:", X_pred.shape)
"""
    cells.append(new_markdown_cell("## 📊 Prepare Inference Dataset"))
    cells.append(new_code_cell(prep_code))

    # -----------------------------
    # 7. 推論実行
    # -----------------------------
    predict_code = """
# Predict with both models
pred_lgb = model_lgb.predict(X_pred)
pred_ridge = model_ridge.predict(X_pred)

# Ensemble (simple average)
pred_final = (pred_lgb + pred_ridge) / 2

df_pred["prediction"] = pred_final

print(df_pred[["prediction"]].head())
"""
    cells.append(new_markdown_cell("## 🤖 Run Predictions"))
    cells.append(new_code_cell(predict_code))

    # -----------------------------
    # 8. 結果保存
    # -----------------------------
    save_code = """
df_pred.to_csv("prediction_output.csv", index=False)
print("Saved predictions to prediction_output.csv")
"""
    cells.append(new_markdown_cell("## 💾 Save Prediction Results"))
    cells.append(new_code_cell(save_code))

    # -----------------------------
    # 9. Notebook 保存
    # -----------------------------
    nb["cells"] = cells
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print(f"Prediction notebook saved to: {output_path}")
