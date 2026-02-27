from dotenv import load_dotenv
load_dotenv()

import re
import json
from pathlib import Path
import json
from google import genai
import os
import pandas as pd
import numpy as np
from eda_agent.pipeline import EDAAgentPipeline
from eda_agent.modeling.model_builder import ModelBuilder
from eda_agent.orchestrator.notebook_builder import build_notebook
import time
from google.genai.errors import ServerError

from datetime import datetime

ts = datetime.now().strftime("%Y%m%d_%H%M%S")


print(os.environ.get("GEMINI_API_KEY"))

def extract_next_role(markdown_text: str) -> str:
    pattern = r"次に担当すべきロール[\s\u3000]*\n[\s\u3000]*([A-Z_]+)"
    match = re.search(pattern, markdown_text)
    if match:
        return match.group(1).strip()
    return "END"




class Orchestrator:
    """
    Manager → Data Cleaning Agent → EDA Agent → Analyst → Data Scientist → Feature Engineer → Modeler
    のワークフローを自動で回す orchestrator。
    """

    def __init__(self, df_train, df_test,
                roles_dir="src/eda_agent/orchestrator/roles",
                io_dir="src/eda_agent/orchestrator/io"):
        self.df_train = df_train
        self.df_test = df_test
        self.roles_dir = Path(roles_dir)
        self.io_dir = Path(io_dir)
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.pipeline = EDAAgentPipeline(self.client, df_train)

    # -------------------------
    # Utility
    # -------------------------
    def load_md(self, filename):
        return (self.roles_dir / filename).read_text(encoding="utf-8")

    def save_json(self, filename, data):
        (self.io_dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def call_api(self, prompt: str, max_retries=5, backoff=2) -> str:
        """
        Gemini API 呼び出し（503 対策の自動リトライ付き）
        """
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                return response.text

            except ServerError as e:
                # 503 のときだけリトライ
                if "503" in str(e):
                    wait = backoff ** attempt
                    print(f"[WARN] Gemini が高負荷のためリトライします ({attempt+1}/{max_retries}) ... {wait}秒待機")
                    time.sleep(wait)
                    continue
                else:
                    raise e

        raise RuntimeError("Gemini API が最大リトライ回数を超えて応答しませんでした。")


    def load_prompt(self, filename: str) -> str:
        path = self.roles_dir / filename
        return path.read_text(encoding="utf-8")
        
    def save_md(self, filename: str, content: str):
        md_dir = self.io_dir / "md"
        md_dir.mkdir(parents=True, exist_ok=True)
        (md_dir / filename).write_text(content, encoding="utf-8")

    def load_input_json(self):
        path = Path(r"src\eda_agent\orchestrator\io\input.json")
        return json.loads(path.read_text(encoding="utf-8"))

    # -------------------------
    # Main workflow
    # -------------------------
    def run(self):
        # 初期化
        manager_output = None
        cleaning_output = None
        eda_output = None
        analyst_output = None
        ds_output = None
        fe_output = None
        modeler_output = None

        input_data = self.load_input_json()
        project_goal = input_data.get("project_goal", "")

        # --- Manager ---
        print("====Manager Run====")
        manager_prompt_template = self.load_prompt("manager.md")
        manager_prompt = manager_prompt_template.replace(
            "{{project_goal}}",
            project_goal
        )
        manager_output = self.call_api(manager_prompt)
        self.save_md(f"manager_{ts}.md", manager_output)      
        next_role = extract_next_role(manager_output)

        # --- Data Cleaning Agent ---
        print("====DATA_CLEANING_AGENT RUN====")
        if next_role == "DATA_CLEANING_AGENT":
            cleaning_prompt = f"""
# Instructions from Manager

{manager_output}

# DataFrame Preview
以下はクリーニング対象の DataFrame の先頭5行です：
{self.df_train.head().to_markdown()}

# DataFrame Columns
{list(self.df_train.columns)}

# Your Task
上記の DataFrame をクリーニングしてください。
"""
            cleaning_output = self.call_api(cleaning_prompt)
            self.save_md(f"cleaning_{ts}.md", cleaning_output)
            next_role = extract_next_role(cleaning_output)

        # --- EDA Agent ---
        print("====EDA_AGENT RUN====")
        if next_role == "EDA_AGENT":
            eda_prompt = f"""
# Instructions from Data Cleaning Agent

{cleaning_output}

# DataFrame Preview
以下はEDA対象の DataFrame の先頭5行です：
{self.df_train.head().to_markdown()}

# DataFrame Columns
{list(self.df_train.columns)}

# Your Task
上記の DataFrame を用いて EDA を実施してください。
"""
            eda_output = self.call_api(eda_prompt)
            self.save_md(f"eda_{ts}.md", eda_output)
            next_role = extract_next_role(eda_output)

        # --- Analyst ---
        print("====ANALYST_AGENT RUN====")
        if next_role == "ANALYST":
            analyst_prompt = f"""
# Instructions from EDA Agent

{eda_output}

# Your Task
EDA 結果を読み解き、洞察をまとめてください。
"""
            analyst_output = self.call_api(analyst_prompt)
            self.save_md(f"analyst_{ts}.md", analyst_output)

            next_role = extract_next_role(analyst_output)

        # --- Data Scientist ---
        print("====DATA_SCIENTIST RUN====")
        if next_role == "DATA_SCIENTIST":
            ds_prompt = f"""
# Instructions from Analyst

{analyst_output}

# Your Task
モデル構築に向けた分析方針を設計してください。
"""
            ds_output = self.call_api(ds_prompt)
            self.save_md(f"data_scientist_{ts}.md", ds_output)

            next_role = extract_next_role(ds_output)

        # --- Feature Engineer ---
        print("====FEATURE_ENGINEER RUN====")
        if next_role == "FEATURE_ENGINEER":
            fe_prompt = f"""
# Instructions from Data Scientist

{ds_output}

# Your Task
特徴量を生成する Python コードを作成してください。
"""
            fe_output = self.call_api(fe_prompt)
            self.save_md(f"feature_engineer_{ts}.md", fe_output)

            next_role = extract_next_role(fe_output)

        # --- Modeler ---
        print("====MODELER RUN====")
        if next_role == "MODELER":
            modeler_prompt = f"""
# Instructions from Feature Engineer

{fe_output}

# Your Task
モデルを構築し、評価し、結果をまとめてください。
"""
            modeler_output = self.call_api(modeler_prompt)
            self.save_md(f"modeler_{ts}.md", modeler_output)

            next_role = extract_next_role(modeler_output)

        result = {
            "manager": manager_output,
            "cleaning": cleaning_output,
            "eda": eda_output,
            "analyst": analyst_output,
            "data_scientist": ds_output,
            "feature_engineer": fe_output,
            "modeler": modeler_output
        }

        notebook_path = build_notebook(result, r"eda_agent\notebooks\generated\eda_pipeline.ipynb")
        print("Notebook generated:", notebook_path)

        return result