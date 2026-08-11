import csv
import glob
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# Chuyển FinMind_Vnstock_<MA>.json (dạng lồng nhau) sang CSV "long
# format" (statement, quarter, item, value) để đưa lên Google Sheet
# (Sheet chỉ hiển thị tốt bảng phẳng, không hiển thị JSON lồng nhau).
# =====================================================================


def flatten_symbol_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    symbol = data.get("symbol", "")
    rows = []

    for statement in ["fundamental_ratios", "income_statement", "balance_sheet", "cash_flow"]:
        block = data.get(statement, {})
        source = block.get("source", "")

        for item, value in (block.get("latest") or {}).items():
            rows.append({
                "symbol": symbol,
                "statement": statement,
                "source": source,
                "quarter": "latest",
                "item": item,
                "value": value,
            })

        for snapshot in block.get("quarterly_history") or []:
            quarter = snapshot.get("quarter", "")
            for item, value in snapshot.items():
                if item == "quarter":
                    continue
                rows.append({
                    "symbol": symbol,
                    "statement": statement,
                    "source": source,
                    "quarter": quarter,
                    "item": item,
                    "value": value,
                })

    return rows


def main():
    json_files = glob.glob("FinMind_Vnstock_*.json")
    if not json_files:
        print("[!] Không tìm thấy file FinMind_Vnstock_*.json nào để flatten.")
        return

    for json_path in json_files:
        rows = flatten_symbol_json(json_path)
        if not rows:
            continue
        csv_path = json_path.replace(".json", "_flat.csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "statement", "source", "quarter", "item", "value"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"[v] Đã flatten {json_path} -> {csv_path} ({len(rows)} dòng)")


if __name__ == "__main__":
    main()
