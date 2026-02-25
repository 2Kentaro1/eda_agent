import datetime
import subprocess
import os

README_TEMPLATE = """
# EDA Agent Pipeline

自動 EDA Notebook 生成パイプライン。  
Gemini API を用いて、Notebook 形式の EDA を自動生成し、  
Google Drive へ保存・GitHub で管理できる構成になっています。

---

## 🚀 機能一覧

- 初回 EDA Notebook の自動生成（Markdown + Code セル）
- 追加 EDA（user_instruction）による Notebook 追記
- 図表スタイルの統一（seaborn + matplotlib）
- Google Drive への Notebook 保存
- プロンプトのファイル分割管理
- Notebook 自動生成パイプラインのクラス化
- GitHub Actions による EDA 自動実行

---

## 📁 ディレクトリ構成
{tree}

---

## 🧩 主なファイル

| ファイル | 説明 |
|---------|------|
| `src/eda_agent/pipeline.py` | Notebook 自動生成パイプライン（クラス化） |
| `src/eda_agent/prompts/base_eda_prompt.txt` | 初回 EDA 用プロンプト |
| `src/eda_agent/prompts/additional_prompt.txt` | 追加 EDA 用プロンプト |
| `src/eda_agent/prompts/style_block.txt` | 図表スタイル統一コード |
| `src/eda_agent/utils/notebook_builder.py` | Notebook 生成ユーティリティ |
| `src/eda_agent/utils/drive_io.py` | Google Drive 読み書き |
| `.github/workflows/auto_eda.yml` | GitHub Actions による自動 EDA |

---

## 🕒 最終更新日時

{updated}

"""

def generate_readme():
    # tree コマンドでディレクトリ構造を取得
    try:
        tree = subprocess.check_output(
            ["tree", "-I", "venv|__pycache__|.git"],
            text=True
        )
    except Exception:
        tree = "(tree コマンドが利用できません)"

    updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    readme = README_TEMPLATE.format(tree=tree, updated=updated)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    print("README.md を生成しました。")


if __name__ == "__main__":
    generate_readme()