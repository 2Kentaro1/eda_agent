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

def append_latest_eda_to_notebook(history: List[Dict[str, Any]], output_path: str, round_id: int):
    """
    Notebook を積み上げ方式で更新する Builder（新設計）
    - 初回は append=False で notebook を新規作成
    - 2回目以降は append=True で最新の EDA_AGENT のみ追加
    """

    # ============================
    # 🔍 最新の EDA_AGENT を取得
    # ============================
    latest_eda = None
    for entry in reversed(history):
        if entry.get("role") == "eda_agent":
            latest_eda = entry
            break

    if latest_eda is None:
        raise ValueError("No EDA_AGENT entry found in history.")

    # ============================
    # 📘 NotebookBuilder を初期化
    # ============================
    is_first_round = (round_id == 1)
    builder = NotebookBuilder(append=not is_first_round)

    # ============================
    # 📝 初回のみヘッダーと imports
    # ============================
    if is_first_round:
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


    # ============================
    # 🔵 最新 EDA を追加
    # ============================
    content = latest_eda["output"].get("content", {})

    builder.add_markdown(f"# 🔵 EDA (Round {round_id})")

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

    # ============================
    # 🟠 最新 Analyst の要点を追加
    # ============================
    latest_analyst = None
    for entry in reversed(history):
        if entry.get("role") == "analyst":
            latest_analyst = entry
            break

    if latest_analyst:
        acontent = latest_analyst["output"].get("content", {})

        builder.add_markdown(f"# 🟠 Analyst Summary (Round {round_id})")

        # business insights / key findings / risks
        for section in ["business_insights", "key_findings", "risks"]:
            items = acontent.get(section, [])
            if items:
                builder.add_markdown(f"## {section.replace('_', ' ').title()}")
                for item in items:
                    builder.add_markdown(f"- {item}")

        # new EDA recommendations（最新ラウンドのものだけ）
        new_recs = acontent.get("recommendations", [])
        if new_recs:
            builder.add_markdown("## New EDA Recommendations")
            for rec in new_recs:
                builder.add_markdown(f"- {rec}")

        # modeling suggestions（別 key）
        model_sugs = acontent.get("modeling_suggestions", [])
        if model_sugs:
            builder.add_markdown("## Modeling Suggestions")
            for sug in model_sugs:
                builder.add_markdown(f"- {sug}")

    # Save notebook
    builder.save(output_path)

def build_round_notebook_for_eda(history, output_path, round_id):
    latest_eda = None
    for entry in reversed(history):
        if entry.get("role") == "eda_agent":
            latest_eda = entry
            break

    if latest_eda is None:
        raise ValueError("No EDA_AGENT entry found in history.")

    builder = NotebookBuilder(append=False)

    # Header
    builder.add_markdown(f"# Analysis Notebook - Round {round_id}")
    builder.add_markdown("Generated from JSON Relay Pipeline\n")

    # Imports
    builder.add_code(
        "import pandas as pd\n"
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "import seaborn as sns\n"
        "sns.set_theme(style='whitegrid', font_scale=1.2)\n"
        "plt.rcParams['font.family'] = 'MS Gothic'\n"
        "plt.rcParams['figure.figsize'] = (10, 5)\n"
    )

    # Load df_train
    builder.add_code(
        "df_train = pd.read_parquet('df_train_after_cleaning.parquet')\n"
        "print('df_train loaded:', df_train.shape)"
    )

    # EDA
    content = latest_eda["output"]["content"]
    builder.add_markdown(f"# 🔵 EDA (Round {round_id})")

    for key, code in content.get("code_snippets", {}).items():
        builder.add_markdown(f"### {key}")
        builder.add_code(code)

    for key, code in content.get("plot_snippets", {}).items():
        builder.add_markdown(f"### {key}")
        builder.add_code(code)

    # Save df_train
    builder.add_markdown("## Save updated df_train for next round")
    builder.add_code(
        "df_train.to_parquet('df_train_after_cleaning.parquet', index=False)\n"
        "print('Saved updated df_train_after_cleaning.parquet:', df_train.shape)"
    )

    builder.save(output_path)

def append_analyst_summary_to_notebook(history, output_path, round_id):
    latest_analyst = None
    for entry in reversed(history):
        if entry.get("role") == "analyst":
            latest_analyst = entry
            break

    if latest_analyst is None:
        return  # Analyst がいない場合は何もしない

    builder = NotebookBuilder(append=True)

    content = latest_analyst["output"]["content"]

    builder.add_markdown(f"# 🟠 Analyst Summary (Round {round_id})")

    for section in ["business_insights", "key_findings", "risks"]:
        items = content.get(section, [])
        if items:
            builder.add_markdown(f"## {section.replace('_', ' ').title()}")
            for item in items:
                builder.add_markdown(f"- {item}")

    recs = content.get("recommendations", [])
    if recs:
        builder.add_markdown("## New EDA Recommendations")
        for rec in recs:
            builder.add_markdown(f"- {rec}")

    sugs = content.get("modeling_suggestions", [])
    if sugs:
        builder.add_markdown("## Modeling Suggestions")
        for sug in sugs:
            builder.add_markdown(f"- {sug}")

    builder.save(output_path)
