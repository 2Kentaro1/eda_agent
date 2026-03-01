import json
from builder import extract_latest_eda

# Notebook のパス（あなたの環境に合わせて変更）
NOTEBOOK_PATH = r"C:\Users\aikoc\PythonProjectFolder\eda_agent\notebooks\generated\analysis.ipynb"

def print_cells(cells):
    print("\n=== Extracted Cells ===")
    for i, cell in enumerate(cells):
        print(f"\n--- Cell {i} ---")
        print(f"type: {cell['cell_type']}")
        print("source:")
        for line in cell["source"]:
            print(line.rstrip())

def main():
    print("[TEST] Loading notebook...")
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb_json = json.load(f)

    print("[TEST] Extracting latest EDA section...")
    latest_eda = extract_latest_eda(nb_json)

    if not latest_eda:
        print("[ERROR] No EDA Round found!")
    else:
        print(f"[OK] Extracted {len(latest_eda)} cells.")
        print_cells(latest_eda)

if __name__ == "__main__":
    main()