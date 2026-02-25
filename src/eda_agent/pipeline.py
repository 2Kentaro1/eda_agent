import io
import nbformat as nbf
from pathlib import Path

class EDAAgentPipeline:
    """
    Gemini API を使って EDA Notebook を自動生成するパイプライン。
    - 初回 EDA Notebook 生成
    - 追加 EDA セル生成
    - Notebook への追記
    - プロンプトファイルの読み込み
    """

    def __init__(self, client, df, prompt_dir="src/eda_agent/prompts"):
        self.client = client
        self.df = df
        self.prompt_dir = Path(prompt_dir)

        # プロンプト読み込み
        self.base_prompt = self._load_prompt("base_eda_prompt.txt")
        self.add_prompt = self._load_prompt("additional_eda_prompt.txt")
        self.style_block = self._load_prompt("style_block.txt")

    # -------------------------
    # プロンプト読み込み
    # -------------------------
    def _load_prompt(self, filename):
        path = self.prompt_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # -------------------------
    # DataFrame info を文字列化
    # -------------------------
    def _df_info(self):
        buf = io.StringIO()
        self.df.info(buf=buf)
        return buf.getvalue()

    # -------------------------
    # Gemini API 呼び出し
    # -------------------------
    def _call_api(self, prompt):
        response = self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )
        return response.text

    # -------------------------
    # 初回 EDA Notebook 生成
    # -------------------------
    def generate_initial_notebook(self):
        prompt = self.base_prompt.format(
            df_head=self.df.head().to_markdown(),
            df_info=self._df_info(),
            style_block=self.style_block
        )
        return self._call_api(prompt)

    # -------------------------
    # 追加 EDA セル生成
    # -------------------------
    def generate_additional_cells(self, instruction):
        prompt = self.add_prompt.format(
            user_instruction=instruction,
            df_head=self.df.head().to_markdown(),
            df_info=self._df_info()
        )
        return self._call_api(prompt)

    # -------------------------
    # Notebook を新規作成
    # -------------------------
    def save_notebook(self, notebook_text, output_path):
        nb = self._convert_to_notebook(notebook_text)
        with open(output_path, "w", encoding="utf-8") as f:
            nbf.write(nb, f)

    # -------------------------
    # Notebook に追記
    # -------------------------
    def append_to_notebook(self, notebook_path, new_cells_text):
        with open(notebook_path, "r", encoding="utf-8") as f:
            nb = nbf.read(f, as_version=4)

        new_cells = self._parse_cells(new_cells_text)
        nb.cells.extend(new_cells)

        with open(notebook_path, "w", encoding="utf-8") as f:
            nbf.write(nb, f)

    # -------------------------
    # Notebook 変換ロジック
    # -------------------------
    def _convert_to_notebook(self, text):
        nb = nbf.v4.new_notebook()
        nb.cells = self._parse_cells(text)
        return nb

    # -------------------------
    # Markdown / Code セルのパース
    # -------------------------
    def _parse_cells(self, text):
        cells = []
        blocks = text.split("```")

        for block in blocks:
            if block.startswith("markdown"):
                content = block.replace("markdown", "", 1).strip()
                cells.append(nbf.v4.new_markdown_cell(content))
            elif block.startswith("python"):
                content = block.replace("python", "", 1).strip()
                cells.append(nbf.v4.new_code_cell(content))

        return cells