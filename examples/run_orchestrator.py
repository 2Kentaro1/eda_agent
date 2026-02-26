"""
VSCode 上で Orchestrator を実行するための使用例。

- input.json を読み込む
- Orchestrator を実行する
- output.json に結果を書き出す
- Notebook は notebooks/generated/ に保存される

実行方法:
    python examples/run_orchestrator.py
"""
import sys
from pathlib import Path

sys.path.append(r"C:\Users\aikoc\PythonProjectFolder\eda_agent\src")

import json
import pandas as pd
from pathlib import Path

from src.eda_agent.orchestrator.orchestrator import Orchestrator

# -----------------------------
# 1. 入力データの読み込み
# -----------------------------
# 例: ローカルの CSV を読み込む
df_train = pd.read_csv("data/train.csv")
df_test = pd.read_csv("data/test.csv")



# -----------------------------
# 2. input.json の読み込み
# -----------------------------
INPUT_JSON = "src/eda_agent/orchestrator/io/input.json"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    input_data = json.load(f)

print("=== Input JSON ===")
print(json.dumps(input_data, indent=2, ensure_ascii=False))

# -----------------------------
# 3. Orchestrator の実行
# -----------------------------
orchestrator = Orchestrator(df_train, df_test)
result = orchestrator.run()

# -----------------------------
# 4. output.json に保存
# -----------------------------
OUTPUT_JSON = "src/eda_agent/orchestrator/io/output.json"

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print("\n=== Workflow Completed ===")
print(f"結果を {OUTPUT_JSON} に保存しました。")
print("Notebook は notebooks/generated/ に保存されています。")