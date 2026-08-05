import csv
from datetime import datetime
import json
import random
import re
import sys
import time
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
import requests

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# NGUỒN BỔ SUNG: VnEconomy (Thời báo Kinh tế Việt Nam - Hội Khoa học
# Kinh tế Việt Nam), đăng bài hàng ngày, cùng vai trò với CafeFScraper.py
# nhưng khác nguồn để đa dạng hóa tin tức cho RAG/Knowledge Graph.
# =====================================================================


class VnEconomyScraper:

    def __init__(self, keyword, max_articles=20):
        """Khởi tạo Scraper với từ khóa và số lượng bài báo tối đa cần lấy."""
        self.keyword = keyword
        self.max_articles = max_articles
        self.base_url = "https://vneconomy.vn"
        self.search_url_template = (
            "https://vneconomy.vn/tim-kiem.html?Text={keyword}&SortBy=newest&page={page}"
        )
        self.session = requests.Session()
        self.articles_data = []

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

    def _get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Referer": "https://vneconomy.vn/",
        }

    def _fetch_html(self, url):
        try:
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            if response.status_code == 200:
                return response.text
            print(f"[!] Lỗi HTTP {response.status_code} khi truy cập: {url}")
        except Exception as e:
            print(f"[!] Ngoại lệ khi gọi URL {url}: {str(e)}")
        return None

    def _clean_text(self, text):
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _parse_date(self, date_str):
        """VnEconomy hiển thị giờ dạng 'HH:MM, DD/MM/YYYY'."""
        try:
            match = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})", date_str)
            if match:
                date_part = match.group(1).replace("-", "/")
                return datetime.strptime(date_part, "%d/%m/%Y")
        except Exception:
            pass
        return datetime.min

    def search_article_links(self):
        """Quét các trang tìm kiếm (?Text=...&page=N) để lấy URL bài báo."""
        print(f"[*] Đang tìm kiếm từ khóa: '{self.keyword}' trên VnEconomy...")
        encoded_kw = quote(self.keyword)
        page = 1
        found_links = set()

        while len(found_links) < self.max_articles and page <= 10:
            url = self.search_url_template.format(page=page, keyword=encoded_kw)
            print(f"   -> Đang quét trang tìm kiếm {page}: {url}...")
            html = self._fetch_html(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            items = soup.select("article")

            if not items:
                print(f"   [-] Không tìm thấy thêm bài báo nào ở trang {page}.")
                break

            new_items_count = 0
            for item in items:
                if len(found_links) >= self.max_articles:
                    break
                link_tag = item.find("a", href=True)
                if not link_tag:
                    continue
                full_url = urljoin(self.base_url, link_tag["href"])
                if "vneconomy.vn" in full_url and full_url.endswith(".htm"):
                    if full_url not in found_links:
                        found_links.add(full_url)
                        new_items_count += 1

            if new_items_count == 0:
                break

            page += 1
            time.sleep(random.uniform(1.0, 2.5))

        print(
            f"[+] Đã thu thập được {len(found_links)} link bài báo. Bắt đầu tải nội dung chi tiết...\n"
        )
        return list(found_links)

    def scrape_article_detail(self, url):
        html = self._fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.select_one("h1[data-field='title']") or soup.find("title")
        title = self._clean_text(title_tag.get_text()) if title_tag else "No Title"

        date_tag = soup.select_one("time[data-field='distributionDate']")
        date_str = self._clean_text(date_tag.get_text()) if date_tag else ""
        parsed_date = self._parse_date(date_str)

        sapo_tag = soup.select_one("h4[data-field='sapo']")
        sapo = self._clean_text(sapo_tag.get_text()) if sapo_tag else ""

        content_div = soup.select_one("main[data-field='body']") or soup.select_one(
            "[data-field='body']"
        )
        content_text = ""

        if content_div:
            for junk in content_div.find_all(["script", "style"]):
                junk.decompose()
            paragraphs = content_div.find_all("p")
            content_text = " ".join(
                self._clean_text(p.get_text()) for p in paragraphs if p.get_text()
            )
            if not content_text:
                content_text = self._clean_text(content_div.get_text())

        if not content_text or len(content_text) < 50:
            return None

        return {
            "title": title,
            "url": url,
            "publish_date": date_str,
            "_sort_date": parsed_date,
            "sapo": sapo,
            "content": content_text,
            "char_count": len(content_text),
            "source": "VnEconomy",
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def run(self):
        links = self.search_article_links()

        for idx, link in enumerate(links, 1):
            print(f"[{idx}/{len(links)}] Đang cào nội dung: {link}")
            article_data = self.scrape_article_detail(link)

            if article_data:
                self.articles_data.append(article_data)
                print(f"   + Thành công: {article_data['title'][:60]}...")
            else:
                print("   - Bỏ qua: Không trích xuất được text hợp lệ.")

            time.sleep(random.uniform(1.5, 3.0))

        print("\n[*] Đang sắp xếp lại dữ liệu ưu tiên bài viết mới nhất...")
        self.articles_data.sort(key=lambda x: x["_sort_date"], reverse=True)
        for item in self.articles_data:
            del item["_sort_date"]

        print(f"[+] Hoàn tất! Thu thập thành công {len(self.articles_data)} bài báo chất lượng.")

    def export_to_files(self, filename_prefix="VnEconomy_Article"):
        if not self.articles_data:
            print("[!] Không có dữ liệu để xuất file.")
            return

        json_file = f"{filename_prefix}_{self.keyword}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.articles_data, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

        csv_file = f"{filename_prefix}_{self.keyword}.csv"
        keys = self.articles_data[0].keys()
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(self.articles_data)
        print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    KEYWORD = "FPT"
    MAX_ARTICLES = 15

    scraper = VnEconomyScraper(keyword=KEYWORD, max_articles=MAX_ARTICLES)
    scraper.run()
    scraper.export_to_files(filename_prefix="VnEconomy_Article")
