"""
builder.py — Analyst-focused Notebook Builder (EDA only)
"""

import json
import os
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
from typing import Dict, Any, List
# Collect role outputs 
from collections import defaultdict

class NotebookBuilder:

    def __init__(self, append=False):
        self.nb = new_notebook()
        self.cells = []
        self.append = append

    def add_markdown(self, text: str):
        self.cells.append(new_markdown_cell(text))

    def add_code(self, code: str):
        self.cells.append(new_code_cell(code))

    def add_plot_snippets(self, plot_snippets: Dict[str, str]):
        self.add_markdown("## 6. EDA Plots")
        for name, code in plot_snippets.items():
            self.add_markdown(f"### Plot: {name}")
            self.add_code(code)

    def save(self, path: str):
        # append モードなら既存notebookを読み込む
        if self.append and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing_nb = nbformat.read(f, as_version=4)
            # 既存セル + 新規セル
            self.nb["cells"] = existing_nb["cells"] + self.cells
        else:
            # 新規 notebook
            self.nb["cells"] = self.cells
    
        with open(path, "w", encoding="utf-8") as f:
            nbformat.write(self.nb, f)
        print(f"Notebook saved to {path} (append={self.append})")


def build_notebook_from_history(history: List[Dict[str, Any]], output_path: str):
    builder = NotebookBuilder(append=True)

    # Header
    builder.add_markdown("# Analysis Notebook (EDA Only)")
    builder.add_markdown("Generated from JSON Relay Pipeline\n")

    # Common imports
    builder.add_code(
        "import pandas as pd\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "import seaborn as sns\n"
        "# 図表のスタイル統一\n"
        "sns.set_theme(style='whitegrid', font_scale=1.2)\n"
        "plt.rcParams['font.family'] = 'MS Gothic'\n"
        "plt.rcParams['figure.figsize'] = (10, 5)\n"
        "plt.rcParams['axes.titlesize'] = 16\n"
        "plt.rcParams['axes.labelsize'] = 14\n"
        "plt.rcParams['xtick.labelsize'] = 12\n"
        "plt.rcParams['ytick.labelsize'] = 12\n"
    )
    
    # df_train の読み込みセルを追加
    builder.add_code(
        "df_train = pd.read_csv('df_train_after_cleaning.parquet')\n"
        "print('df_train loaded:', df_train.shape)"
    )

    # Collect role outputs
    
    role_map = defaultdict(list)

    for entry in history:
        if entry.get("type") == "agent":
            role = entry.get("role","").lower() #小文字化
            output = entry.get("output", {})
            role_map[role].append(output)

    section_counter = 1

    if "eda_agent" in role_map:
        for output in role_map["eda_agent"]:
            code_snippets = output.get("content", {}).get("code_snippets", {})
            for key, code in code_snippets.items():
                title = key.replace("_", " ").title()
                builder.add_markdown(f"# {section_counter}. {title}")
                builder.add_code(code)
                section_counter += 1

    if "eda_agent" in role_map:
        for output in role_map["eda_agent"]:
            plot_snippets = output.get("content", {}).get("plot_snippets", {})
            for name, code in plot_snippets.items():
                builder.add_markdown(f"# {section_counter}. Plot: {name}")
                builder.add_code(code)
                section_counter += 1

    # 7. Cleaning Summary（EDA に影響する範囲のみ）
    if "data_cleaning_agent" in role_map:
        builder.add_markdown("# 7. Cleaning Summary")
        for _ in role_map["data_cleaning_agent"]:
            builder.add_code("df_train.info()")
            builder.add_code("df_train.isnull().sum()")

    # 8. Analyst Notes
    builder.add_markdown("# 8. Analyst Notes")
    builder.add_markdown(
        "この Notebook は ANALYST ロールが参照するために生成されています。\n"
        "以下の章を参照して分析を行ってください：\n"
        "- 1. Overview\n"
        "- 2. Missing Values\n"
        "- 3. Numerical Statistics\n"
        "- 4. Categorical Statistics\n"
        "- 5. Correlation\n"
        "- 6. EDA Plots\n"
        "- 7. Cleaning Summary\n"
    )

    builder.save(output_path)