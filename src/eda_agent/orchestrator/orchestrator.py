import json
from pathlib import Path
from google import genai
import os
import pandas as pd
import numpy as np
from src.eda_agent.pipeline import EDAAgentPipeline
from src.eda_agent.modeling.model_builder import ModelBuilder


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

    def call_api(self, prompt):
        response = self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return response.text

    # -------------------------
    # Main workflow
    # -------------------------
    def run(self):
        output = {}

        # ============================================================
        # 1. Manager
        # ============================================================
        manager_prompt = self.load_md("manager.md")
        manager_output = json.loads(self.call_api(manager_prompt))
        output["manager"] = manager_output


        # ============================================================
        # 2. Data Cleaning Agent（★ 新規追加）
        # ============================================================
       
        cleaning_prompt = (
            self.load_md("data_cleaning.md")
            .replace("{MANAGER_OUTPUT}", json.dumps(manager_output, ensure_ascii=False))
        )

        cleaning_output = json.loads(self.call_api(cleaning_prompt))
        output["data_cleaning"] = cleaning_output

        # クリーニング前のコピー
        before_train = self.df_train.copy()
        before_test = self.df_test.copy()

        # cleaning_code を train に適用
        exec(cleaning_output["cleaning_code"], {"df": self.df_train, "pd": pd})

        # test にも同じ cleaning_code を適用
        exec(cleaning_output["cleaning_code"], {"df": self.df_test, "pd": pd})

        # ★ クリーニング後の df を保存
        self.df_train.to_csv("notebooks/generated/train_cleaned.csv", index=False, encoding="utf-8")
        self.df_test.to_csv("notebooks/generated/test_cleaned.csv", index=False, encoding="utf-8")
        output["data_cleaning"]["cleaned_data_path"] = "notebooks/generated/train_cleaned.csv"
        
        # ============================================================
        # 3. EDA Agent（既存）
        # ============================================================
        self.pipeline.df = self.df_train  # ★ クリーニング後の df を渡す
        initial_notebook = self.pipeline.generate_initial_notebook()
        self.pipeline.save_notebook(
            initial_notebook,
            "notebooks/generated/eda_initial.ipynb"
        )
        output["eda_agent"] = {"notebook": "notebooks/generated/eda_initial.ipynb"}

        # ============================================================
        # 4. Analyst
        # ============================================================
        analyst_prompt = self.load_md("analyst.md").replace(
            "{EDA_NOTEBOOK_PATH}", "notebooks/generated/eda_initial.ipynb"
        )
        analyst_output = json.loads(self.call_api(analyst_prompt))
        output["analyst"] = analyst_output

        # ============================================================
        # 5. Data Scientist
        # ============================================================
        ds_prompt = self.load_md("data_scientist.md").replace(
            "{ANALYST_OUTPUT}", json.dumps(analyst_output, ensure_ascii=False)
        )
        ds_output = json.loads(self.call_api(ds_prompt))
        output["data_scientist"] = ds_output

        # ============================================================
        # 6. Additional EDA（Data Scientist → EDA Agent）
        # ============================================================
        add_cells = self.pipeline.generate_additional_cells(
            ds_output["instruction_for_eda"]
        )
        self.pipeline.append_to_notebook(
            "notebooks/generated/eda_initial.ipynb",
            add_cells
        )

        # ============================================================
        # 7. Feature Engineer
        # ============================================================
        fe_prompt = self.load_md("feature_engineer.md").replace(
            "{DS_OUTPUT}", json.dumps(ds_output, ensure_ascii=False)
        )
        fe_output = json.loads(self.call_api(fe_prompt))
        output["feature_engineer"] = fe_output

        # ============================================================
        # 8. Modeler
        # ============================================================
        modeler_prompt = self.load_md("modeler.md").replace(
            "{FE_OUTPUT}", json.dumps(fe_output, ensure_ascii=False)
        )
        modeler_output = json.loads(self.call_api(modeler_prompt))
        output["modeler"] = modeler_output

        # ============================================================
        # Save all outputs
        # ============================================================
        self.save_json("output.json", output)

        # ============================================================
        # ModelBuilder
        # ============================================================

        builder = ModelBuilder(
            df=self.df_train,
            feature_json=output["feature_engineer"],
            model_json=output["modeler"]
        )

        df_feat = builder.generate_features()
        model = builder.train_model()
        rmse = builder.evaluate()

        df_test_feat = builder.generate_features_for_test(self.df_test)
        preds = builder.predict(df_test_feat)

        builder.save_submission(
            df_test_feat,
            preds,
            path="submission.csv"
        )

        return output