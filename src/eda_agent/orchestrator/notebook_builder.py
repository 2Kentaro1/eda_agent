import nbformat
import re
from pathlib import Path

def markdown_to_cells(markdown_text: str):
    """
    Markdown テキストを Notebook の Markdown セルと Code セルに分割する。
    """
    cells = []
    code_pattern = r"```python([\s\S]*?)```"

    pos = 0
    for match in re.finditer(code_pattern, markdown_text):
        start, end = match.span()

        # --- Markdown セル（コードブロック前の部分） ---
        md_chunk = markdown_text[pos:start].strip()
        if md_chunk:
            cells.append(nbformat.v4.new_markdown_cell(md_chunk))

        # --- Code セル ---
        code_chunk = match.group(1).strip()
        cells.append(nbformat.v4.new_code_cell(code_chunk))

        pos = end

    # --- 最後の Markdown セル ---
    tail_md = markdown_text[pos:].strip()
    if tail_md:
        cells.append(nbformat.v4.new_markdown_cell(tail_md))

    return cells

def build_notebook(role_outputs: dict, output_path="generated_notebook.ipynb"):
    """
    role_outputs = {
        "manager": "...",
        "cleaning": "...",
        "eda": "...",
        "analyst": "...",
        "data_scientist": "...",
        "feature_engineer": "...",
        "modeler": "..."
    }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    nb = nbformat.v4.new_notebook()
    all_cells = []

    # --- Notebook の冒頭 ---
    all_cells.append(nbformat.v4.new_markdown_cell("# 自動生成 EDA Notebook\n---"))

    # --- 各ロールの出力を Notebook に追加 ---
    for role, md in role_outputs.items():
        if md is None:
            continue

        # セクションタイトル
        all_cells.append(nbformat.v4.new_markdown_cell(f"## {role.replace('_', ' ').title()} Output"))

        # Markdown → セル変換
        cells = markdown_to_cells(md)
        all_cells.extend(cells)

    nb["cells"] = all_cells

    # 保存
    with open(output_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    return output_path