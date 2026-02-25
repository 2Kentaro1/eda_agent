"""
Colab で EDAAgentPipeline を実行するための使用例。

- 初回 EDA Notebook の生成
- 追加 EDA の追記
- Google Drive への保存

このファイルは GitHub に保存しておき、
Colab での利用方法を明確にするためのサンプルコードです。
"""

import os
from google import genai
import pandas as pd

from src.eda_agent.pipeline import EDAAgentPipeline

# -----------------------------
# 1. API クライアントの準備
# -----------------------------
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# -----------------------------
# 2. データ読み込み（例）
# -----------------------------
df = pd.read_csv("/content/drive/MyDrive/eda_project/input/data.csv")

# -----------------------------
# 3. パイプライン初期化
# -----------------------------
pipeline = EDAAgentPipeline(client, df)

# -----------------------------
# 4. 初回 EDA Notebook 生成
# -----------------------------
text = pipeline.generate_initial_notebook()
pipeline.save_notebook(
    text,
    "/content/drive/MyDrive/eda_project/output/eda.ipynb"
)

# -----------------------------
# 5. 追加 EDA の実行
# -----------------------------
instruction = "曜日 × 天気 × 気温のクロス集計を追加して"
cells = pipeline.generate_additional_cells(instruction)

pipeline.append_to_notebook(
    "/content/drive/MyDrive/eda_project/output/eda.ipynb",
    cells
)

print("EDA Notebook updated successfully.")