"""
task_runner.py

- CLI または Notebook から単一タスク実行
- 各タスクの output を outputs/ に保存
- 後続タスクは自動で前タスクの output をロードして payload に渡す
- JSON Schema バリデーション
- Reviewer も自動実行
"""
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
import os
import json
import pandas as pd
from typing import Dict, Any, Optional

from google import genai
from jsonschema import validate, ValidationError

# run_orchestrator.py → examples → eda_agent（1つ上）
ROOT = Path(__file__).resolve().parents[1]

# src ディレクトリを追加
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))  # ★ insert(0) が重要

# Notebook Builder
from notebook_builder.builder import build_notebook_from_history


# =========================
# 設定
# =========================

GEMINI_MODEL = "gemini-2.5-flash"
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GENAI_API_KEY:
    raise RuntimeError("環境変数 GEMINI_API_KEY が設定されていません。")

# genai.configure(api_key=GENAI_API_KEY)
client = genai.Client(api_key=GENAI_API_KEY)

# =========================
# パス設定
# =========================

BASE_DIR = os.path.dirname(__file__)
PROMPT_DIR = os.path.join(BASE_DIR, "..", "src", "prompts")
SCHEMA_DIR = os.path.join(BASE_DIR, "..", "src", "schemas")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs")
NOTEBOOK_OUTPUT = os.path.join(BASE_DIR, "..", "notebooks", "generated", "analysis.ipynb")
FEATURE_OUTPUT_DIR = os.path.join(BASE_DIR, "..", "notebooks", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FEATURE_OUTPUT_DIR, exist_ok=True)


# =========================
# Markdown 読み込み
# =========================

def load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, f"{name}.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# =========================
# Schema Cache
# =========================

class SchemaCache:
    def __init__(self, schema_dir: str):
        self.schema_dir = schema_dir
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get(self, name: str) -> Dict[str, Any]:
        if name in self.cache:
            return self.cache[name]

        path = os.path.join(self.schema_dir, f"{name}.schema.json")
        with open(path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self.cache[name] = schema
        return schema


schema_cache = SchemaCache(SCHEMA_DIR)


# =========================
# Gemini 呼び出し
# =========================

def call_gemini(prompt: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:

    if payload is None:
        user_input = "入力コンテキストはありません。"
    else:
        user_input = "以下が入力コンテキスト(JSON)です。\n" + json.dumps(payload, ensure_ascii=False, indent=2)

    response = client.models.generate_content(
        model = GEMINI_MODEL,
        contents=[prompt, user_input],
        config={"response_mime_type": "application/json"},
    )

    return json.loads(response.text)

DEPENDENCY_MAP = {
    "manager": [],
    "data_generation_analyst_initial": ["manager"],
    "data_cleaning_agent": ["manager"],
    "eda_agent": ["manager","data_cleaning_agent","data_generation_analyst_initial"],
    "analyst": ["manager","eda_agent", "data_cleaning_agent"],
    "data_generation_analyst_updated": ["manager","analyst", "data_cleaning_agent"],
    "data_scientist": ["manager","analyst", "model_coder"],
    "feature_engineer": ["manager","data_generation_analyst_updated", "data_cleaning_agent"],
    "model_designer": ["manager","feature_engineer"],
    "model_coder": ["model_designer"],
    "reviewer": []  # reviewer は常に agent_output を直接受け取る
}

ROLES_THAT_REQUIRE_DATA = {
    "eda_agent": True,
    "data_cleaning_agent": True,
    "feature_engineer": True,
    "model_coder": True,
    "model_designer": False,
    "manager": False,
    "data_generation_analyst_initial": False,
    "data_generation_analyst_updated": False,
    "analyst": False,
    "data_scientist": False,
}


# =========================
# TaskRunner
# =========================

class TaskRunner:

    ROLE_LIST = [
        "manager",
        "data_generation_analyst_initial",
        "eda_agent",
        "data_cleaning_agent",
        "data_generation_analyst_updated",
        "analyst",
        "data_scientist",
        "feature_engineer",
        "model_designer",
        "model_coder",
    ]

    def __init__(self, train_path="data/train.csv", test_path="data/test.csv"):
        self.history = []

        # 保存済みのクリーニング後データがあれば優先 
        cleaned_train = os.path.join(BASE_DIR, "..", "notebooks", "generated", "df_train_after_cleaning.parquet")
        cleaned_test = os.path.join(BASE_DIR, "..", "notebooks", "generated", "df_test_after_cleaning.parquet")   

        if os.path.exists(cleaned_train): 
            print("[INFO] Loading cleaned train data") 
            self.df_train = pd.read_parquet(cleaned_train) 
        else: 
            self.df_train = pd.read_csv(train_path) 
            
        if os.path.exists(cleaned_test): 
            print("[INFO] Loading cleaned test data") 
            self.df_test = pd.read_parquet(cleaned_test) 
        else: 
            self.df_test = pd.read_csv(test_path)

        self.notebook_output_path = os.path.join(
            BASE_DIR, "..", "notebooks", "generated", "analysis.ipynb"
        )

        print(f"[INFO] Loaded train: {self.df_train.shape}, test: {self.df_test.shape}")
    # -------------------------
    # Schema バリデーション
    # -------------------------
    def validate_schema(self, role_key: str, output: Dict[str, Any]):
        schema = schema_cache.get(role_key)
        try:
            validate(instance=output, schema=schema)
            return {"valid": True, "errors": []}
        except ValidationError as e:
            return {"valid": False, "errors": [e.message]}

    # -------------------------
    # output 保存
    # -------------------------
    def save_output(self, role_key: str, output: Dict[str, Any]):
        path = os.path.join(OUTPUT_DIR, f"{role_key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    # -------------------------
    # output ロード
    # -------------------------
    def load_previous_outputs(self) -> Dict[str, Any]:
        payload = {}
        for role in self.ROLE_LIST:
            path = os.path.join(OUTPUT_DIR, f"{role}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    payload[role] = json.load(f)
        return payload

    def save_reviewer_output(self, reviewer_output: Dict[str, Any]):
        reviewed_role = reviewer_output["metadata"].get("reviewed_role", "unknown")
        filename = f"reviewer_{reviewed_role.lower()}.json"
        path = os.path.join(OUTPUT_DIR, filename)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(reviewer_output, f, ensure_ascii=False, indent=2)

        print(f"[REVIEWER] Saved reviewer output to {path}")

    def save_cleaned_dataframes(self):
        out_dir = os.path.join(BASE_DIR, "..", "notebooks", "generated")
        os.makedirs(out_dir, exist_ok=True)

        train_path = os.path.join(out_dir, "df_train_after_cleaning.parquet")
        test_path = os.path.join(out_dir, "df_test_after_cleaning.parquet")

        self.df_train.to_parquet(train_path, index=False)
        self.df_test.to_parquet(test_path, index=False)

        print(f"[CLEANING] Saved cleaned df_train to {train_path}")
        print(f"[CLEANING] Saved cleaned df_test to {test_path}")


    # -------------------------------
    # Reviewer結果をagent_outputに統合
    # -------------------------------
    def merge_reviewer_feedback(self, agent_output, reviewer_output):
        """
        Reviewer の結果を任意の agent_output に統合する。
        """
        feedback = reviewer_output.get("content", {})
        agent_output["content"]["review_feedback"] = feedback
        return agent_output

    # -------------------------------
    # notebook実行処理
    # ------------------------------
    def generate_notebook(self):
        """
        history をもとに Notebook を生成する
        """
        print("[NOTEBOOK] Building analysis notebook...")
        build_notebook_from_history(self.history, self.notebook_output_path)

    # -------------------------
    # 単一タスク実行（CLI/Notebook 共通）
    # -------------------------
    def run_single(self, role_key: str):
        if role_key not in self.ROLE_LIST:
            raise ValueError(f"Unknown role: {role_key}")

        prompt = load_prompt(role_key)

        # 依存関係から payload を自動構築
        payload = self.build_payload_for_role(role_key)

        # === データが必要なロールには DataFrame を渡す ===
        if ROLES_THAT_REQUIRE_DATA.get(role_key, False): 
            payload["df_train_head"] = self.df_train.head(20).to_dict(orient="list") 
            payload["df_train_info"] = { 
                "rows": len(self.df_train), 
                "columns": list(self.df_train.columns) 
                }    

        print(f"\n=== Running Agent: {role_key} ===")
        agent_output = call_gemini(prompt, payload)

        validation = self.validate_schema(role_key, agent_output)

        # === Cleaning Agent の場合は code_snippets を実行 ===
        if role_key == "data_cleaning_agent": 
            content = agent_output.get("content", {})
            code_snippets = content.get("code_snippets", {}) 
            self.apply_cleaning_code(code_snippets)
            self.save_cleaned_dataframes()
        
        # === EDA Agent の場合は code_snippets を実行 ===
        if role_key == "eda_agent":
            content = agent_output.get("content", {})
            code_snippets = content.get("code_snippets", {})
            # eda_results = self.execute_eda_code(code_snippets)

            # EDA 結果を agent_output に追加
            # agent_output["content"]["eda_results"] = eda_results

        # === Feature Engineer の場合 ===
        if role_key == "feature_engineer": 
            content = agent_output.get("content", {})
            code_snippets = content.get("code_snippets", {}) 
            self.apply_feature_code(code_snippets)

        if role_key == "feature_engineer": 
            content = agent_output.get("content", {})
            code_snippets = content.get("code_snippets", {}) 
            self.apply_feature_code(code_snippets) 
            
            # === 特徴量追加後の df を保存 === 
            self.save_feature_dataframes()

        # 保存
        self.save_output(role_key, agent_output)

        # Reviewer 実行
        # reviewer_output = self.run_reviewer(agent_output, validation)

        # === Reviewer の結果を agent_output に統合 ===
        # agent_output = self.merge_reviewer_feedback(agent_output, reviewer_output)

        # === 統合後の agent_output を保存 ===
        # self.save_output(role_key, agent_output)

        # history に追加
        self.history.append({
            "type": "agent",
            "role": role_key,
            "output": agent_output,
            "schema_validation": validation
        })

        # === Notebook 自動生成 ===
        self.generate_notebook()

        return agent_output

    def apply_cleaning_code(self, code_snippets: Dict[str, str]):
        """
        Cleaning Agent の code_snippets を実行し、
        df_train / df_test を更新する。
        """
        local_vars = {
            "df": self.df_train
        }

        for name, code in code_snippets.items():
            print(f"[CLEANING] Executing snippet: {name}")
            try:
                exec(code, {}, local_vars)
            except Exception as e:
                print(f"[ERROR] Cleaning code failed: {name}")
                print(code)
                print(e)
                continue

        # df_train を更新
        self.df_train = local_vars["df"]

    def apply_feature_code(self, code_snippets: Dict[str, str]):
        """
        Feature Engineer の code_snippets を実行し、
        df_train / df_test に特徴量を追加する。
        """
        for name, code in code_snippets.items():
            print(f"[FEATURE] Executing snippet: {name}")

            # --- train ---
            local_vars_train = {"df": self.df_train}
            try:
                exec(code, {}, local_vars_train)
                self.df_train = local_vars_train["df"]
            except Exception as e:
                print(f"[ERROR] Feature code failed on train: {name}")
                print(code)
                print(e)

            # --- test ---
            local_vars_test = {"df": self.df_test}
            try:
                exec(code, {}, local_vars_test)
                self.df_test = local_vars_test["df"]
            except Exception as e:
                print(f"[ERROR] Feature code failed on test: {name}")
                print(code)
                print(e)

    def save_feature_dataframes(self):
        """
        特徴量追加後の df_train / df_test を  として保存する。
        """
        train_path = os.path.join(FEATURE_OUTPUT_DIR, "df_train_after_features.parquet")
        test_path = os.path.join(FEATURE_OUTPUT_DIR, "df_test_after_features.parquet")

        self.df_train.to_parquet(train_path, index=False)
        self.df_test.to_parquet(test_path, index=False)

        print(f"[FEATURE] Saved df_train to {train_path}")
        print(f"[FEATURE] Saved df_test to {test_path}")


    # -------------------------
    # Reviewer 実行
    # -------------------------
    def run_reviewer(self, agent_output: Dict[str, Any], validation: Dict[str, Any]):
        prompt = load_prompt("reviewer")

        payload = {
            "agent_output": agent_output,
            "schema_validation": validation
        }

        reviewer_output = call_gemini(prompt, payload)

        # === Reviewer の出力を保存（reviewer_{role}.json） ===
        self.save_reviewer_output(reviewer_output)

        return reviewer_output

    def build_payload_for_role(self, role_key: str) -> Dict[str, Any]:
        """
        依存関係に基づいて必要な output を自動ロードして payload を構築する
        """
        deps = DEPENDENCY_MAP.get(role_key, [])
        payload = {}

        for dep in deps:
            path = os.path.join(OUTPUT_DIR, f"{dep}.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    payload[dep] = json.load(f)
            # reviewer_{dep}.json も読み込む
            # reviewer_path = os.path.join(OUTPUT_DIR, f"reviewer_{dep}.json") 
            # if os.path.exists(reviewer_path): 
            #     with open(reviewer_path, "r", encoding="utf-8") as f: 
            #         payload[f"reviewer_{dep}"] = json.load(f)

        # ★ EDA Agent に Analyst の recommendations を渡す
        if role_key == "eda_agent":
            analyst_path = os.path.join(OUTPUT_DIR, "analyst.json")
            if os.path.exists(analyst_path):
                with open(analyst_path, "r", encoding="utf-8") as f:
                    analyst_json = json.load(f)
                    payload["analyst_recommendations"] = analyst_json["content"]["recommendations"]

        # ★ Analyst に Notebook のパスを渡す 
        if role_key == "analyst": 
            payload["notebook_path"] = self.notebook_output_path

            # notebook の中身を読み込んで渡す
            with open(self.notebook_output_path, "r", encoding="utf-8") as f:
                payload["notebook_json"] = json.load(f)

        return payload


# =========================
# CLI 実行
# =========================

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python task_runner.py TASK_NAME")
        print("TASK_NAME:", ", ".join(TaskRunner.ROLE_LIST))
        exit(1)

    task = sys.argv[1]

    runner = TaskRunner()
    runner.run_single(task)

    print(f"\nTask '{task}' completed.")
