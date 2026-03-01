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

def build_notebook_from_history(history: List[Dict[str, Any]], output_path: str, round_id):
    """
    EDA → Analyst → EDA → Analyst … のループに対応した Notebook Builder
    - ラウンドごとに EDA と Analyst の内容をまとめて表示
    - code_snippets / plot_snippets をラウンド単位で整理
    """

    builder = NotebookBuilder(append=False)

    # Header
    builder.add_markdown(f"# Analysis Notebook - Round {round_id}")
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

    # Load cleaned df
    builder.add_code(
        "df_train = pd.read_parquet('df_train_after_cleaning.parquet')\n"
        "print('df_train loaded:', df_train.shape)"
    )

    # --- 指定ラウンドの EDA と Analyst のみ抽出 ---
    eda_index = None
    analyst_index = None

    # history の中から round_id の EDA/Analyst を探す
    eda_count = 0
    for i, entry in enumerate(history):
        if entry["type"] == "agent" and entry["role"] == "eda_agent":
            eda_count += 1
            if eda_count == round_id:
                eda_index = i
                # Analyst は次の entry
                if i + 1 < len(history) and history[i+1]["role"] == "analyst":
                    analyst_index = i + 1
                break

    # --- EDA セクション ---
    if eda_index is not None:
        entry = history[eda_index]
        content = entry["output"]["content"]

        builder.add_markdown(f"# 🔵 EDA Round {round_id}")

        code_snippets = content.get("code_snippets", {})
        plot_snippets = content.get("plot_snippets", {})

        if code_snippets:
            builder.add_markdown("## Code Snippets")
            for key, code in code_snippets.items():
                builder.add_markdown(f"### {key}")
                builder.add_code(code)

        if plot_snippets:
            builder.add_markdown("## Plots")
            for key, code in plot_snippets.items():
                builder.add_markdown(f"### {key}")
                builder.add_code(code)

    # --- Analyst セクション ---
    if analyst_index is not None:
        entry = history[analyst_index]
        content = entry["output"]["content"]

        builder.add_markdown(f"# 🟠 Analyst Feedback (Round {round_id})")

        for section in ["business_insights", "key_findings", "risks", "recommendations"]:
            items = content.get(section, [])
            if items:
                builder.add_markdown(f"## {section.replace('_', ' ').title()}")
                for item in items:
                    builder.add_markdown(f"- {item}")

    builder.save(output_path)
