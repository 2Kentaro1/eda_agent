"""
task_runner.py

Human-in-the-loop JSON Relay TaskRunner
- すべてのロールは JSON で入出力
- 各タスク実行後に必ず Reviewer を通す
- 次に何を実行するかは常に人間が決める
"""
from dotenv import load_dotenv
load_dotenv()
import os
import json
import textwrap
from typing import Dict, Any, Optional

import google.generativeai as genai


# =========================
# 設定
# =========================

# GEMINI_MODEL = "gemini-3-pro"  # or "gemini-3-flash"
# GEMINI_MODEL = "gemini-3-pro"  # or "gemini-3-flash"
GEMINI_MODEL = "gemini-1.5-flash"  # or "gemini-3-flash"

# 環境変数から API キーを読む想定
GENAI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GENAI_API_KEY:
    raise RuntimeError("環境変数 GEMINI_API_KEY が設定されていません。")

genai.configure(api_key=GENAI_API_KEY)


# =========================
# プロンプト定義（最小版）
# 実際は別ファイルの Markdown にしてもOK
# =========================

ROLE_PROMPTS: Dict[str, str] = {
    "DATA_GENERATION_ANALYST_INITIAL": textwrap.dedent("""
        あなたは Data Generation Analyst です。
        モード: INITIAL

        目的:
        - 与えられたデータ概要やビジネス文脈から、
          「このデータがどのような生成プロセスで生まれたか」を仮説として構造化すること。

        出力要件:
        - 必ず JSON のみを返すこと。
        - 前後に説明文やマークダウンを含めないこと。

        出力フォーマット例:
        {
          "role": "DATA_GENERATION_ANALYST",
          "version": "1.0",
          "mode": "INITIAL",
          "content": {
            "hypotheses": [...],
            "expected_patterns": [...],
            "risks": [...]
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "DATA_GENERATION_ANALYST_UPDATED": textwrap.dedent("""
        あなたは Data Generation Analyst です。
        モード: UPDATED

        目的:
        - EDA や Data Cleaning の結果を踏まえ、
          データ生成プロセスに関する仮説を更新し、特徴量設計への含意を整理すること。

        出力要件:
        - 必ず JSON のみを返すこと。
        - 前後に説明文やマークダウンを含めないこと。

        出力フォーマット例:
        {
          "role": "DATA_GENERATION_ANALYST",
          "version": "1.0",
          "mode": "UPDATED",
          "content": {
            "validated_hypotheses": [...],
            "rejected_hypotheses": [...],
            "new_hypotheses": [...],
            "feature_implications": [...]
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "EDA_AGENT": textwrap.dedent("""
        あなたは EDA Agent です。

        目的:
        - データの構造・分布・相関・欠損・外れ値を整理し、
          後続の Data Cleaning / Feature Engineering / Modeling に役立つ情報を JSON で返すこと。

        出力要件:
        - 必ず JSON のみを返すこと。
        - 前後に説明文やマークダウンを含めないこと。

        出力フォーマット例:
        {
          "role": "EDA_AGENT",
          "version": "1.0",
          "content": {
            "summary": "...",
            "column_analysis": {...},
            "missing_values": {...},
            "outliers": {...},
            "correlations": {...},
            "recommended_plots": [...],
            "code_snippets": {...}
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "DATA_CLEANING_AGENT": textwrap.dedent("""
        あなたは Data Cleaning Agent です。

        目的:
        - EDA 結果やデータ概要をもとに、クリーニング方針とその影響を JSON で返すこと。

        出力要件:
        - 必ず JSON のみを返すこと。

        出力フォーマット例:
        {
          "role": "DATA_CLEANING_AGENT",
          "version": "1.0",
          "content": {
            "cleaning_plan": [...],
            "cleaned_data_description": {...},
            "code_snippets": {...}
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "FEATURE_ENGINEER": textwrap.dedent("""
        あなたは Feature Engineering Agent です。

        目的:
        - Data Generation Analyst / EDA / Cleaning の情報をもとに、
          有効な特徴量設計案とコード断片を JSON で返すこと。

        出力要件:
        - 必ず JSON のみを返すこと。

        出力フォーマット例:
        {
          "role": "FEATURE_ENGINEER",
          "version": "1.0",
          "content": {
            "feature_plan": [...],
            "code_snippets": {...}
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "MODEL_DESIGNER": textwrap.dedent("""
        あなたは Model Designer です。

        目的:
        - 与えられた目的・特徴量・データ構造に基づき、
          モデルの設計思想・アルゴリズム選択・評価戦略を JSON で返すこと。

        出力要件:
        - 必ず JSON のみを返すこと。
        - コードは書かない。設計のみ。

        出力フォーマット例:
        {
          "role": "MODEL_DESIGNER",
          "version": "1.0",
          "content": {
            "model_type": "lightgbm",
            "design_rationale": [...],
            "feature_set": [...],
            "hyperparameter_plan": {...},
            "training_strategy": {...}
          },
          "metadata": {
            "input_summary": "...",
            "timestamp": "..."
          }
        }
    """),

    "MODEL_CODER": textwrap.dedent("""
        あなたは Model Coder です。

        目的:
        - Model Designer の JSON を受け取り、
          実行可能な Python コード断片を JSON で返すこと。

        出力要件:
        - 必ず JSON のみを返すこと。
        - Notebook 自動生成に適した形でコード断片を返すこと。

        出力フォーマット例:
        {
          "role": "MODEL_CODER",
          "version": "1.0",
          "content": {
            "imports": [...],
            "data_prep_code": "...",
            "training_code": [...],
            "evaluation_code": [...]
          },
          "metadata": {
            "designer_reference": "MODEL_DESIGNER",
            "timestamp": "..."
          }
        }
    """),
}

REVIEWER_PROMPT = textwrap.dedent("""
    あなたは Reviewer です。

    目的:
    - 与えられたエージェント出力(JSON)をレビューし、
      構造の妥当性・論理性・一貫性・不足点を指摘し、必要なら改善提案を行うこと。

    出力要件:
    - 必ず JSON のみを返すこと。

    出力フォーマット例:
    {
      "role": "REVIEWER",
      "version": "1.0",
      "content": {
        "valid": true,
        "issues": [
          "..."
        ],
        "suggestions": [
          "..."
        ]
      },
      "metadata": {
        "reviewed_role": "...",
        "timestamp": "..."
      }
    }
""")


# =========================
# Gemini 呼び出しヘルパ
# =========================

def call_gemini(prompt: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    prompt + payload(JSON) を渡して、JSON を返す。
    """
    model = genai.GenerativeModel(GEMINI_MODEL)

    # payload はそのまま JSON 文字列として渡す
    if payload is None:
        user_input = "入力コンテキストはありません。"
    else:
        user_input = "以下が入力コンテキスト(JSON)です。\n" + json.dumps(payload, ensure_ascii=False, indent=2)

    response = model.generate_content(
        [prompt, user_input],
        generation_config={
            "response_mime_type": "application/json",
        },
    )

    # Gemini 3 系は JSON のみ返す前提
    text = response.text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # もし壊れたらログして例外
        print("=== Gemini 出力(JSONデコード失敗) ===")
        print(text)
        raise


# =========================
# TaskRunner 本体
# =========================

class TaskRunner:
    def __init__(self):
        # ログとして全出力を保持（必要に応じてファイル保存も可）
        self.history = []

    def run_agent(self, role_key: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if role_key not in ROLE_PROMPTS:
            raise ValueError(f"未知のロール: {role_key}")

        prompt = ROLE_PROMPTS[role_key]
        print(f"\n=== Running Agent: {role_key} ===")
        output = call_gemini(prompt, payload)
        self.history.append({"type": "agent", "role": role_key, "output": output})
        return output

    def run_reviewer(self, agent_output: Dict[str, Any]) -> Dict[str, Any]:
        print("\n=== Running Reviewer ===")
        payload = {
            "agent_output": agent_output
        }
        output = call_gemini(REVIEWER_PROMPT, payload)
        self.history.append({"type": "reviewer", "role": "REVIEWER", "output": output})
        return output

    def print_json(self, title: str, data: Dict[str, Any]):
        print(f"\n--- {title} ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))

    def interactive_loop(self):
        """
        人間がタスクを選び、各タスク後に Reviewer を必ず通すループ。
        """
        print("Human-in-the-loop TaskRunner 開始")
        print("Ctrl+C で終了できます。\n")

        current_payload: Optional[Dict[str, Any]] = None

        while True:
            print("\n=== 実行するロールを選択してください ===")
            print("1: DATA_GENERATION_ANALYST_INITIAL")
            print("2: DATA_GENERATION_ANALYST_UPDATED")
            print("3: EDA_AGENT")
            print("4: DATA_CLEANING_AGENT")
            print("5: FEATURE_ENGINEER")
            print("6: MODEL_DESIGNER")
            print("7: MODEL_CODER")
            print("h: 直近の payload を表示")
            print("q: 終了")

            choice = input("> ").strip().lower()

            if choice == "q":
                print("終了します。")
                break
            if choice == "h":
                self.print_json("Current Payload", current_payload or {"info": "payload はまだありません"})
                continue

            role_map = {
                "1": "DATA_GENERATION_ANALYST_INITIAL",
                "2": "DATA_GENERATION_ANALYST_UPDATED",
                "3": "EDA_AGENT",
                "4": "DATA_CLEANING_AGENT",
                "5": "FEATURE_ENGINEER",
                "6": "MODEL_DESIGNER",
                "7": "MODEL_CODER",
            }

            if choice not in role_map:
                print("無効な選択です。")
                continue

            role_key = role_map[choice]

            # 必要ならここで payload を編集する UI を追加してもよい
            # ひとまず current_payload をそのまま渡す
            agent_output = self.run_agent(role_key, current_payload)
            self.print_json(f"Agent Output ({role_key})", agent_output)

            reviewer_output = self.run_reviewer(agent_output)
            self.print_json("Reviewer Output", reviewer_output)

            # 次のタスクに渡す payload は、
            # 「エージェント出力 + レビュー結果」をまとめたものにする
            current_payload = {
                "agent_output": agent_output,
                "review_output": reviewer_output,
            }

            print("\nこの結果を踏まえて、次に実行するロールを再度選択してください。")


# =========================
# エントリポイント
# =========================

if __name__ == "__main__":
    runner = TaskRunner()
    runner.interactive_loop()