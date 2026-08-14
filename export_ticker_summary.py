import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# GOM KET QUA 1 LAN CHAY THANH 1 FILE JSON DUY NHAT
#
# Sau khi run_full_pipeline.ps1 chay xong, du lieu cua 1 ma co phieu bi
# nam rai rac o nhieu noi khac nhau:
#   - data_ingestion/structured_data/           (BCTC, chi so, gia OHLCV)
#   - data_ingestion/news_scraper/              (tin tuc, cong bo BCTC)
#   - data_ingestion/news_scraper/FinMind_Data_Lake/<MA>/...
#         (vi finmind_file_organizer.py chay voi cwd=news_scraper nen no
#          CHI don dep file trong thu muc do, khong phai goc du an)
#   - data_ingestion/brokerage_reports/data/    (bao cao phan tich CTCK)
#
# Script nay quet het cac vi tri tren, gom lai thanh 1 file JSON de nguoi
# chay xem duoc ngay ket qua ma KHONG can mo Google Sheet.
#
# Mac dinh file JSON chi nhung phan du lieu vua doc (VD 30 phien gia gan
# nhat) de con mo duoc bang Notepad; dung --full de nhung toan bo.
# =====================================================================

ROOT = Path(__file__).resolve().parent
STRUCTURED_DIR = ROOT / "data_ingestion" / "structured_data"
NEWS_DIR = ROOT / "data_ingestion" / "news_scraper"
BROKERAGE_DATA_DIR = ROOT / "data_ingestion" / "brokerage_reports" / "data"

PREVIEW_ROWS = 30  # so dong nhung vao JSON khi khong dung --full


def find_file(search_dirs, filename):
    """Tim file theo ten trong nhieu thu muc (ke ca thu muc con, vi
    finmind_file_organizer.py co the da chuyen file vao FinMind_Data_Lake)."""
    for directory in search_dirs:
        if not directory.exists():
            continue
        candidate = directory / filename
        if candidate.is_file():
            return candidate
        for found in directory.rglob(filename):
            if found.is_file():
                return found
    return None


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"   [!] Khong doc duoc {path.name}: {e}")
        return None


def read_csv(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"   [!] Khong doc duoc {path.name}: {e}")
        return []


def read_jsonl(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except Exception as e:
        print(f"   [!] Khong doc duoc {path.name}: {e}")
    return rows


def pick(row, keys):
    """Giu lai vai truong quan trong, bo bot cho JSON de doc."""
    return {key: row.get(key) for key in keys if key in row}


def shrink_news(rows):
    """Tin tuc: bo truong content (rat dai) nhung giu do dai de biet co
    noi dung that hay khong."""
    result = []
    for row in rows:
        item = pick(row, ["title", "url", "publish_date", "sapo", "char_count", "source"])
        if "char_count" not in item:
            item["char_count"] = len(str(row.get("content", "")))
        result.append(item)
    return result


def build(ticker, full):
    data, summary, files, warnings = {}, {}, [], []
    news_search = [NEWS_DIR]
    structured_search = [STRUCTURED_DIR, NEWS_DIR]

    def note(path, count=None):
        try:
            files.append({
                "duong_dan": str(path.relative_to(ROOT)),
                "kich_thuoc_kb": round(path.stat().st_size / 1024, 1),
                "so_ban_ghi": count,
            })
        except Exception:
            pass

    # --- Task 4: BCTC quy + chi so dinh gia -----------------------------
    path = find_file(structured_search, f"FinMind_Vnstock_{ticker}.json")
    if path:
        payload = read_json(path)
        if payload:
            data["chi_so_tai_chinh"] = payload
            ratios = (payload.get("fundamental_ratios") or {}).get("latest") or {}
            summary["so_chi_so_dinh_gia"] = len(ratios)
            summary["nguon_chi_so"] = (payload.get("fundamental_ratios") or {}).get("source")
            note(path, len(ratios))
    else:
        warnings.append("Thieu BCTC/chi so dinh gia (Task 4) - chua chay vnstock_data_fetcher.py?")

    # --- Task 5: gia OHLCV ----------------------------------------------
    path = find_file(structured_search, f"FinMind_Market_OHLCV_{ticker}.csv")
    if path:
        rows = read_csv(path)
        block = {
            "so_phien": len(rows),
            "tu_ngay": rows[0].get("time") if rows else None,
            "den_ngay": rows[-1].get("time") if rows else None,
            "duong_dan_file_day_du": str(path.relative_to(ROOT)),
        }
        block["du_lieu"] = rows if full else rows[-PREVIEW_ROWS:]
        if not full and len(rows) > PREVIEW_ROWS:
            block["ghi_chu"] = f"Chi nhung {PREVIEW_ROWS} phien gan nhat. Dung --full de nhung ca {len(rows)} phien."
        data["gia_thi_truong"] = block
        summary["so_phien_gia"] = len(rows)
        note(path, len(rows))
    else:
        warnings.append("Thieu du lieu gia OHLCV (Task 5) - chua chay market_data_fetcher.py?")

    # --- Task 5: snapshot khoi ngoai (file tich luy chung nhieu ma) ------
    path = find_file(structured_search, "FinMind_ForeignFlow_Snapshot.csv")
    if path:
        mine = [r for r in read_csv(path) if (r.get("symbol") or "").upper() == ticker]
        if mine:
            data["khoi_ngoai_snapshot"] = mine
            summary["so_snapshot_khoi_ngoai"] = len(mine)
            note(path, len(mine))

    # --- Task 3: tin tuc + cong bo BCTC ---------------------------------
    news = {}
    for key, filename, label in (
        ("cafef", f"CafeF_Article_{ticker}.json", "so_tin_cafef"),
        ("vneconomy", f"VnEconomy_Article_{ticker}.json", "so_tin_vneconomy"),
    ):
        path = find_file(news_search, filename)
        if path:
            rows = read_json(path) or []
            news[key] = rows if full else shrink_news(rows)
            summary[label] = len(rows)
            note(path, len(rows))
    if news:
        data["tin_tuc"] = news
    else:
        warnings.append("Thieu tin tuc (Task 3) - chua chay CafeFScraper.py / vneconomy_scraper.py?")

    path = find_file(news_search, f"Data_BCTC_{ticker}.json")
    if path:
        rows = read_json(path) or []
        data["cong_bo_bctc"] = rows
        summary["so_cong_bo_bctc"] = len(rows)
        note(path, len(rows))

    # --- Task 2: bao cao phan tich CTCK ---------------------------------
    path = BROKERAGE_DATA_DIR / "cleaned" / ticker / f"{ticker}_brokerage_reports.jsonl"
    if path.is_file():
        rows = read_jsonl(path)
        keep = ["title", "broker", "published_at", "report_type", "recommendation",
                "target_price", "upside_percent", "source_platform",
                "canonical_source_url", "valuation_methods", "analysts"]
        data["bao_cao_phan_tich"] = rows if full else [pick(r, keep) for r in rows]
        summary["so_bao_cao_phan_tich"] = len(rows)
        summary["cac_ctck_da_co_bao_cao"] = sorted({r.get("broker") for r in rows if r.get("broker")})
        note(path, len(rows))
    else:
        warnings.append("Thieu bao cao phan tich CTCK (Task 2) - chua chay brokerage_reports/main.py?")

    summary["so_nhom_du_lieu_thu_duoc"] = len(data)
    return {
        "ma_co_phieu": ticker,
        "thoi_diem_tong_hop": datetime.now().isoformat(timespec="seconds"),
        "che_do": "day_du" if full else "rut_gon",
        "tom_tat": summary,
        "canh_bao": warnings,
        "cac_file_nguon": files,
        "du_lieu": data,
    }


def print_summary(result):
    print(f"\n{'=' * 62}")
    print(f"  KET QUA THU THAP - MA {result['ma_co_phieu']}")
    print(f"{'=' * 62}")
    for key, value in result["tom_tat"].items():
        label = key.replace("_", " ")
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value) or "(khong co)"
        print(f"  {label:<32}: {value}")
    if result["canh_bao"]:
        print(f"\n  THIEU DU LIEU ({len(result['canh_bao'])} muc):")
        for item in result["canh_bao"]:
            print(f"    - {item}")
    print(f"{'=' * 62}\n")


def main():
    cli = argparse.ArgumentParser(description="Gom ket qua 1 lan chay thanh 1 file JSON duy nhat")
    cli.add_argument("--ticker", default=os.getenv("FINMIND_TICKER", "FPT"), help="Ma co phieu can tong hop")
    cli.add_argument("--full", action="store_true", help="Nhung TOAN BO du lieu (file se rat lon)")
    cli.add_argument("--output", help="Duong dan file JSON dau ra (mac dinh: FinMind_KetQua_<MA>.json o goc du an)")
    args = cli.parse_args()

    ticker = args.ticker.strip().upper()
    print(f"[*] Dang gom du lieu cua ma {ticker}...")
    result = build(ticker, args.full)

    output = Path(args.output) if args.output else ROOT / f"FinMind_KetQua_{ticker}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print_summary(result)
    size_kb = round(output.stat().st_size / 1024, 1)
    print(f"[v] Da xuat file tong hop: {output.name} ({size_kb} KB)")
    print(f"    Duong dan day du: {output}")
    if not result["du_lieu"]:
        print("[!] Khong tim thay du lieu nao - kiem tra lai da chay pipeline cho dung ma chua.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
