import sys
from pathlib import Path
import json

# ============================================
# パス設定
# ============================================

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# src ディレクトリを import path に追加
sys.path.insert(0, str(SRC))  # ★ insert(0) が重要

from notebook_builder.builder_model import build_model_notebook


# ============================================
# Notebook 生成処理
# ============================================

def build():
    json_path = ROOT / "outputs/model_coder.json"
    output_path = ROOT / "notebooks/generated/model_training.ipynb"

    # JSON ファイル存在チェック
    if not json_path.exists():
        raise FileNotFoundError(f"Model Coder JSON が見つかりません: {json_path}")

    print(f"[INFO] Loading Model Coder JSON: {json_path}")
    print(f"[INFO] Output Notebook: {output_path}")

    try:
        build_model_notebook(
            model_coder_json_path=str(json_path),
            output_path=str(output_path)
        )
        print("[SUCCESS] Notebook generation completed.")
    except Exception as e:
        print("[ERROR] Notebook generation failed.")
        raise e


# ============================================
# CLI 実行
# ============================================

if __name__ == "__main__":
    print("=== Model Notebook Builder ===")
    build()
