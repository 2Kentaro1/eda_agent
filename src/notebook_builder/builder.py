"""
builder.py — Template-based Notebook Builder
"""

import json
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from typing import Dict, Any, List


# =========================
# Notebook Builder
# =========================

class NotebookBuilder:

    def __init__(self):
        self.nb = new_notebook()
        self.cells = []

        # 章構成テンプレート
        self.chapter_template = [
            ("manager", "Project Overview"),
            ("data_generation_analyst_initial", "Data Generation Hypotheses (Initial)"),
            ("eda_agent", "Exploratory Data Analysis"),
            ("data_cleaning_agent", "Data Cleaning"),
            ("data_generation_analyst_updated", "Data Generation Hypotheses (Updated)"),
            ("feature_engineer", "Feature Engineering"),
            ("model_designer", "Model Design"),
            ("model_coder", "Model Implementation"),
            ("analyst", "Analyst Insights"),
            ("data_scientist", "Data Scientist Validation"),
            ("reviewer", "Reviewer Notes")
        ]

    # -------------------------
    # Markdown セル追加
    # -------------------------
    def add_markdown(self, text: str):
        self.cells.append(new_markdown_cell(text))

    # -------------------------
    # Code セル追加
    # -------------------------
    def add_code(self, code: str):
        self.cells.append(new_code_cell(code))

    # -------------------------
    # JSON → Notebook セル変換
    # -------------------------
    def add_agent_output(self, title: str, output: Dict[str, Any]):
        role = output.get("role", "UNKNOWN")
        content = output.get("content", {})

        # 章タイトル
        self.add_markdown(f"# {title}\n({role})")

        # content のキーごとに処理
        for key, value in content.items():

            # コード断片
            if key == "code_snippets" and isinstance(value, dict):
                self.add_markdown("## Code Snippets")
                for name, code in value.items():
                    self.add_markdown(f"### {name}")
                    self.add_code(code)

            # 配列 → 箇条書き
            elif isinstance(value, list):
                md = f"## {key}\n" + "\n".join([f"- {v}" for v in value])
                self.add_markdown(md)

            # オブジェクト → 整形して Markdown
            elif isinstance(value, dict):
                md = f"## {key}\n```json\n{json.dumps(value, indent=2, ensure_ascii=False)}\n```"
                self.add_markdown(md)

            # 文字列 → Markdown
            elif isinstance(value, str):
                self.add_markdown(f"## {key}\n{value}")

            else:
                self.add_markdown(f"## {key}\n{value}")

    # -------------------------
    # Notebook 保存
    # -------------------------
    def save(self, path: str):
        self.nb["cells"] = self.cells
        with open(path, "w", encoding="utf-8") as f:
            nbformat.write(self.nb, f)
        print(f"Notebook saved to {path}")


# =========================
# history → Notebook 生成
# =========================

def build_notebook_from_history(history: List[Dict[str, Any]], output_path: str):
    builder = NotebookBuilder()

    builder.add_markdown("# Analysis Notebook")
    builder.add_markdown("Generated from JSON Relay Pipeline\n")

    # 共通 import セル（必要に応じて調整）
    builder.add_code( 
        "import pandas as pd\n"
        "import numpy as np\n" 
        "import matplotlib.pyplot as plt\n" 
        "import seaborn as sns\n" 
        "sns.set(style='whitegrid')\n" 
    )

    # ロールごとに history を整理
    role_map = {}
    for entry in history:
        if entry["type"] == "agent":
            role_map[entry["role"]] = entry["output"]

    # テンプレート順に Notebook を構築
    for role_key, chapter_title in builder.chapter_template:
        if role_key in role_map:
            builder.add_agent_output(chapter_title, role_map[role_key])

    builder.save(output_path)
