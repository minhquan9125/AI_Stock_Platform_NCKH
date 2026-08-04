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

# =====================================================================
# NHÓM III.6 - DỮ LIỆU KINH TẾ VĨ MÔ & GIÁ HÀNG HÓA
# Dùng cho Knowledge Graph: xây chuỗi tác động nhân quả (VD: [Lãi suất
# giảm] --> hưởng lợi --> [Ngành BĐS/Chứng khoán])
# =====================================================================

MACRO_KEYWORDS = [
    "Lãi suất điều hành",
    "Tỷ giá",
    "CPI",
    "Tăng trưởng GDP",
    "Tăng trưởng tín dụng",
]

COMMODITY_KEYWORDS = [
    "Giá dầu Brent",
    "Giá thép",
    "Giá quặng sắt",
    "Giá cao su",
    "Phốt pho vàng",
    "Cước vận tải biển",
]


class MacroCommodityScraper:
    """Cào tin tức Vĩ mô & Hàng hóa từ CafeF bằng cách quét lần lượt một
    danh sách từ khóa, tái sử dụng engine tìm-kiếm/cào-chi-tiết đã kiểm
    chứng của CafeFScraper. Mỗi bài viết được gắn nhãn indicator_category
    và indicator_keyword để phục vụ xây dựng quan hệ nhân quả trong
    Knowledge Graph.
    """

    def __init__(self, max_articles_per_keyword=8):
        self.max_articles_per_keyword = max_articles_per_keyword
        self.all_articles = []
        self.seen_urls = set()

    def _run_keyword(self, keyword, category):
        print(f"\n[*] === Nhóm: {category} | Từ khóa: '{keyword}' ===")
        scraper = CafeFScraper(
            keyword=keyword, max_articles=self.max_articles_per_keyword
        )
        scraper.run()

        added = 0
        for article in scraper.articles_data:
            if article["url"] in self.seen_urls:
                continue
            self.seen_urls.add(article["url"])
            article["indicator_category"] = category
            article["indicator_keyword"] = keyword
            self.all_articles.append(article)
            added += 1
        print(f"   -> Thêm {added} bài mới (đã loại trùng với các từ khóa trước).")

    def run(self):
        """Quét toàn bộ từ khóa Vĩ mô Việt Nam rồi đến Hàng hóa thế giới."""
        for kw in MACRO_KEYWORDS:
            self._run_keyword(kw, "Vi_Mo_Viet_Nam")
            time.sleep(random.uniform(1.0, 2.0))

        for kw in COMMODITY_KEYWORDS:
            self._run_keyword(kw, "Hang_Hoa_The_Gioi")
            time.sleep(random.uniform(1.0, 2.0))

        print(
            f"\n[+] Hoàn tất! Tổng cộng {len(self.all_articles)} bài viết "
            f"Vĩ mô & Hàng hóa duy nhất (đã loại trùng)."
        )

    def export_to_files(self, filename_prefix="FinMind_MacroCommodity"):
        """Xuất dữ liệu ra JSON (Vector DB/Knowledge Graph) và CSV (kiểm
        tra thủ công)."""
        if not self.all_articles:
            print("[!] Không có dữ liệu để xuất file.")
            return

        json_file = f"{filename_prefix}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.all_articles, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

        csv_file = f"{filename_prefix}.csv"
        keys = self.all_articles[0].keys()
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.all_articles)
        print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    # Số bài tối đa lấy MỖI từ khóa (11 từ khóa x 8 bài ~ tối đa 88 bài,
    # thực tế ít hơn do trùng lặp giữa các từ khóa liên quan).
    MAX_PER_KEYWORD = 8

    scraper = MacroCommodityScraper(max_articles_per_keyword=MAX_PER_KEYWORD)
    scraper.run()
    scraper.export_to_files(filename_prefix="FinMind_MacroCommodity")
