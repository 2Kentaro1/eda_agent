"""
task_runner.py

- CLI または Notebook から単一タスク実行
- 各タスクの output を outputs/ に保存
- 後続タスクは自動で前タスクの output をロードして payload に渡す
- JSON Schema バリデーション
- Reviewer も自動実行
"""

import os
import json
from typing import Dict, Any, Optional

import google.generativeai as genai
from jsonschema import validate, ValidationError

# Notebook Builder
from src.notebook_builder.builder import build_notebook_from_history


# =========================
# 設定
# =========================

GEMINI_MODEL = "gemini-3-pro"
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GENAI_API_KEY:
    raise RuntimeError("環境変数 GEMINI_API_KEY が設定されていません。")

genai.configure(api_key=GENAI_API_KEY)


# =========================
# パス設定
# =========================

BASE_DIR = os.path.dirname(__file__)
PROMPT_DIR = os.path.join(BASE_DIR, "..", "src", "prompts")
SCHEMA_DIR = os.path.join(BASE_DIR, "..", "src", "schemas")
OUTPUT_DIR = os.path.join(BASE_DIR, "..", "outputs")
NOTEBOOK_OUTPUT = os.path.join(BASE_DIR, "..", "notebooks", "generated", "analysis.ipynb")

os.makedirs(OUTPUT_DIR, exist_ok=True)


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
    model = genai.GenerativeModel(GEMINI_MODEL)

    if payload is None:
        user_input = "入力コンテキストはありません。"
    else:
        user_input = "以下が入力コンテキスト(JSON)です。\n" + json.dumps(payload, ensure_ascii=False, indent=2)

    response = model.generate_content(
        [prompt, user_input],
        generation_config={"response_mime_type": "application/json"},
    )

    return json.loads(response.text)

DEPENDENCY_MAP = {
    "manager": [],
    "data_generation_analyst_initial": ["manager"],
    "eda_agent": ["data_generation_analyst_initial"],
    "data_cleaning_agent": ["eda_agent"],
    "data_generation_analyst_updated": ["eda_agent", "data_cleaning_agent"],
    "feature_engineer": ["data_generation_analyst_updated", "data_cleaning_agent"],
    "model_designer": ["feature_engineer"],
    "model_coder": ["model_designer"],
    "analyst": ["eda_agent", "data_cleaning_agent", "feature_engineer", "model_designer"],
    "data_scientist": ["analyst", "model_coder"],
    "reviewer": []  # reviewer は常に agent_output を直接受け取る
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




    def __init__(self):
        self.history = []

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

    # -------------------------
    # 単一タスク実行（CLI/Notebook 共通）
    # -------------------------
    def run_single(self, role_key: str):
        if role_key not in self.ROLE_LIST:
            raise ValueError(f"Unknown role: {role_key}")

        prompt = load_prompt(role_key)

        # 依存関係から payload を自動構築
        payload = self.build_payload_for_role(role_key)

        print(f"\n=== Running Agent: {role_key} ===")
        agent_output = call_gemini(prompt, payload)

        validation = self.validate_schema(role_key, agent_output)

        # 保存
        self.save_output(role_key, agent_output)

        # Reviewer 実行
        reviewer_output = self.run_reviewer(agent_output, validation)

        # history に追加
        self.history.append({
            "type": "agent",
            "role": role_key,
            "output": agent_output,
            "schema_validation": validation
        })

        return agent_output


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

        self.save_output("reviewer", reviewer_output)

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
