import csv
import json
import random
import sys
import time

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from CafeFScraper import CafeFScraper
from vneconomy_scraper import VnEconomyScraper

# =====================================================================
# GOM ~200 BÀI BÁO TỪ NHIỀU CHỦ ĐỀ (không giới hạn ở mã FPT mặc định),
# tái sử dụng engine tìm-kiếm/cào-chi-tiết đã có sẵn của CafeFScraper và
# VnEconomyScraper, quét lần lượt qua danh sách chủ đề đa dạng.
# =====================================================================

TARGET_TOTAL = 200
PER_KEYWORD = 18

KEYWORDS = [
    "chứng khoán",
    "bất động sản",
    "ngân hàng",
    "công nghệ",
    "trí tuệ nhân tạo",
    "giáo dục",
    "y tế",
    "du lịch",
    "thể thao",
    "giải trí",
    "môi trường",
    "giao thông",
    "năng lượng",
    "nông nghiệp",
    "việc làm",
    "đời sống xã hội",
]

SOURCES = [
    ("CafeF", CafeFScraper),
    ("VnEconomy", VnEconomyScraper),
]


def main():
    all_articles = []
    seen_urls = set()

    for keyword in KEYWORDS:
        if len(all_articles) >= TARGET_TOTAL:
            break
        for source_name, scraper_cls in SOURCES:
            if len(all_articles) >= TARGET_TOTAL:
                break
            print(f"\n[*] === Nguồn: {source_name} | Chủ đề: '{keyword}' ===")
            try:
                scraper = scraper_cls(keyword=keyword, max_articles=PER_KEYWORD)
                scraper.run()
            except Exception as e:
                print(f"[!] Lỗi khi cào {source_name}/{keyword}: {e}")
                continue

            added = 0
            for art in scraper.articles_data:
                if art["url"] in seen_urls:
                    continue
                seen_urls.add(art["url"])
                art["search_keyword"] = keyword
                all_articles.append(art)
                added += 1
                if len(all_articles) >= TARGET_TOTAL:
                    break
            print(
                f"   -> Thêm {added} bài mới (đã loại trùng URL). "
                f"Tổng hiện tại: {len(all_articles)}/{TARGET_TOTAL}"
            )
            time.sleep(random.uniform(1.0, 2.0))

    print(
        f"\n[+] Hoàn tất thu thập: {len(all_articles)} bài báo "
        f"(mục tiêu {TARGET_TOTAL})."
    )

    if not all_articles:
        print("[!] Không có dữ liệu để xuất file.")
        return

    # Prefix chứa "News" để finmind_file_organizer.py._extract_category()
    # nhận diện và xếp vào 3_Tin_Tuc_Va_Su_Kien.
    prefix = "FinMind_News_Mix"

    json_file = f"{prefix}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=4)
    print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

    csv_file = f"{prefix}.csv"
    keys = all_articles[0].keys()
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(all_articles)
    print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


if __name__ == "__main__":
    main()
