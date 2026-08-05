import csv
from datetime import datetime
import json
import os
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


class CafeFScraper:

    def __init__(self, keyword, max_articles=20):
        """Khởi tạo Scraper với từ khóa và số lượng bài báo tối đa cần lấy."""
        self.keyword = keyword
        self.max_articles = max_articles
        self.base_url = "https://cafef.vn"
        self.search_url_template = (
            "https://cafef.vn/tim-kiem/trang-{page}.chn?keywords={keyword}"
        )
        self.session = requests.Session()
        self.articles_data = []

        # Danh sách User-Agent để xoay vòng, tránh bị nhận diện là Bot
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]

    def _get_headers(self):
        """Tạo Header ngẫu nhiên giả lập trình duyệt thật."""
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Referer": "https://cafef.vn/",
        }

    def _fetch_html(self, url):
        """Gửi request tải HTML an toàn với cơ chế xử lý ngoại lệ."""
        try:
            response = self.session.get(
                url, headers=self._get_headers(), timeout=10
            )
            if response.status_code == 200:
                return response.text
            else:
                print(
                    f"[!] Lỗi HTTP {response.status_code} khi truy cập: {url}"
                )
                return None
        except Exception as e:
            print(f"[!] Ngoại lệ khi gọi URL {url}: {str(e)}")
            return None

    def _clean_text(self, text):
        """Làm sạch văn bản, loại bỏ ký tự rác (tối ưu cho RAG Chunking)."""
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)  # Xóa khoảng trắng thừa
        return text.strip()

    def _parse_date(self, date_str):
        """Chuẩn hóa chuỗi thời gian về định dạng chuẩn ISO để sắp xếp."""
        try:
            # Tìm chuỗi ngày tháng dạng DD/MM/YYYY - HH:MM hoặc DD-MM-YYYY
            match = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})", date_str)
            if match:
                date_part = match.group(1).replace("-", "/")
                return datetime.strptime(date_part, "%d/%m/%Y")
        except Exception:
            pass
        return datetime.min  # Nếu không parse được, gán giá trị nhỏ nhất

    def search_article_links(self):
        """Quét các trang tìm kiếm để lấy danh sách URL bài báo liên quan."""
        print(
            f"[*] Đang tìm kiếm từ khóa: '{self.keyword}' trên CafeF..."
        )
        encoded_kw = quote(self.keyword)
        page = 1
        found_links = set()

        while len(found_links) < self.max_articles and page <= 10:  # Quét tối đa 10 trang
            url = self.search_url_template.format(page=page, keyword=encoded_kw)
            print(
                f"   -> Đang quét trang tìm kiếm {page}: {url}..."
            )
            html = self._fetch_html(url)

            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")

            # Fallback Selector: Thử nhiều class khác nhau phòng trường hợp CafeF đổi DOM
            items = (
                soup.select("div.item")
                or soup.select("div.tlitem")
                or soup.select(".list-search .item")
                or soup.select(".timeline .item")
            )

            if not items:
                print(f"   [-] Không tìm thấy thêm bài báo nào ở trang {page}.")
                break

            new_items_count = 0
            for item in items:
                if len(found_links) >= self.max_articles:
                    break

                title_tag = item.find("h3") or item.find("h4") or item.find("a")
                if not title_tag:
                    continue

                link_tag = (
                    title_tag.find("a")
                    if title_tag.name != "a"
                    else title_tag
                )
                if not link_tag or "href" not in link_tag.attrs:
                    continue

                full_url = urljoin(self.base_url, link_tag["href"])
                # Chỉ lấy bài thuộc domain cafef.vn và không lấy trang tag/video
                if "cafef.vn" in full_url and ".chn" in full_url:
                    if full_url not in found_links:
                        found_links.add(full_url)
                        new_items_count += 1

            if new_items_count == 0:
                break

            page += 1
            time.sleep(
                random.uniform(1.0, 2.5)
            )  # Rate limiting: Ngủ ngẫu nhiên giữa các trang

        print(
            f"[+] Đã thu thập được {len(found_links)} link bài báo. Bắt đầu tải nội dung chi tiết...\n"
        )
        return list(found_links)

    def scrape_article_detail(self, url):
        """Vào từng bài báo để cào toàn bộ nội dung text sạch (Deep Scraping)."""
        html = self._fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 1. Trích xuất Tiêu đề
        title_tag = (
            soup.find("h1", class_="title")
            or soup.find("h1", class_="article-title")
            or soup.find("title")
        )
        title = (
            self._clean_text(title_tag.get_text())
            if title_tag
            else "No Title"
        )

        # 2. Trích xuất Ngày đăng
        date_tag = (
            soup.find("span", class_="pdate")
            or soup.find("span", class_="date-and-time")
            or soup.find("div", class_="author")
            or soup.find("span", class_="time")
        )
        date_str = (
            self._clean_text(date_tag.get_text()) if date_tag else ""
        )
        parsed_date = self._parse_date(date_str)

        # 3. Trích xuất Sapo (Đoạn tóm tắt đầu bài)
        sapo_tag = soup.find("h2", class_="sapo") or soup.find(
            "div", class_="sapo"
        )
        sapo = (
            self._clean_text(sapo_tag.get_text()) if sapo_tag else ""
        )

        # 4. Trích xuất Nội dung chính (Body Text)
        content_div = (
            soup.find("div", class_="detail-content")
            or soup.find("div", class_="contentdetail")
            or soup.find("div", id="mainContent")
        )
        content_text = ""

        if content_div:
            # Loại bỏ các thành phần rác trong bài: Quảng cáo, bài liên quan, script, style
            for junk in content_div.find_all(
                ["script", "style", "div"],
                class_=["link-content-footer", "relate-link", "tindng", "ads"],
            ):
                junk.decompose()

            # Lấy tất cả các thẻ văn bản p
            paragraphs = content_div.find_all("p")
            content_text = " ".join(
                [
                    self._clean_text(p.get_text())
                    for p in paragraphs
                    if p.get_text()
                ]
            )
        else:
            # Fallback nếu không tìm thấy thẻ container chuẩn
            paragraphs = soup.find_all("p")
            content_text = " ".join(
                [
                    self._clean_text(p.get_text())
                    for p in paragraphs
                    if len(p.get_text()) > 30
                ]
            )

        # Nếu không lấy được nội dung, bỏ qua bài này
        if not content_text or len(content_text) < 50:
            return None

        return {
            "title": title,
            "url": url,
            "publish_date": date_str,
            "_sort_date": parsed_date,  # Trường tạm để sắp xếp
            "sapo": sapo,
            "content": content_text,
            "char_count": len(content_text),
            "source": "CafeF",
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def run(self):
        """Thực thi toàn bộ luồng Data Ingestion."""
        links = self.search_article_links()

        for idx, link in enumerate(links, 1):
            print(f"[{idx}/{len(links)}] Đang cào nội dung: {link}")
            article_data = self.scrape_article_detail(link)

            if article_data:
                self.articles_data.append(article_data)
                print(f"   + Thành công: {article_data['title'][:60]}...")
            else:
                print("   - Bỏ qua: Không trích xuất được text hợp lệ.")

            # Nghỉ ngẫu nhiên từ 1.5 đến 3 giây để tránh bị Cloudflare/WAF chặn
            time.sleep(random.uniform(1.5, 3.0))

        # ƯU TIÊN SẮP XẾP BÀI MỚI NHẤT LÊN ĐẦU (Theo yêu cầu)
        print("\n[*] Đang sắp xếp lại dữ liệu ưu tiên bài viết mới nhất...")
        self.articles_data.sort(
            key=lambda x: x["_sort_date"], reverse=True
        )

        # Xóa trường tạm phục vụ sort trước khi xuất file
        for item in self.articles_data:
            del item["_sort_date"]

        print(
            f"[+] Hoàn tất! Thu thập thành công {len(self.articles_data)} bài báo chất lượng."
        )

    def export_to_files(self, filename_prefix="cafef_data"):
        """Xuất dữ liệu ra file JSON (cho RAG) và CSV (cho Dashboard/Bảng biểu)."""
        if not self.articles_data:
            print("[!] Không có dữ liệu để xuất file.")
            return

        # 1. Xuất JSON (Dành cho Vector DB Embeddings & Knowledge Graph)
        json_file = f"{filename_prefix}_{self.keyword}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.articles_data, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

        # 2. Xuất CSV (Dành cho kiểm tra thủ công & Excel)
        csv_file = f"{filename_prefix}_{self.keyword}.csv"
        keys = self.articles_data[0].keys()
        with open(
            csv_file, "w", encoding="utf-8-sig", newline=""
        ) as f:  # utf-8-sig không bị lỗi font Tiếng Việt trong Excel
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(self.articles_data)
        print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


# =====================================================================
# KHU VỰC THỰC THI (MAIN ROUTINE)
# =====================================================================
if __name__ == "__main__":
    # Từ khóa cần tìm (Thay đổi theo mã cổ phiếu hoặc chủ đề bạn muốn, VD: "VCI", "Báo cáo tài chính", "Ngành thép")
    KEYWORD = "FPT"

    # Số lượng bài tối đa muốn thu thập (trong MVP bạn nên để 15-30 bài để test luồng trước)
    MAX_ARTICLES = 15

    # Khởi tạo và chạy bot
    scraper = CafeFScraper(keyword=KEYWORD, max_articles=MAX_ARTICLES)
    scraper.run()

    # Xuất dữ liệu ra file để đưa vào bước Text Chunking của mô hình RAG
    # Prefix chứa "CafeF"/"Article" để finmind_file_organizer.py._extract_category()
    # nhận diện đúng và xếp vào 3_Tin_Tuc_Va_Su_Kien (thay vì rơi vào mục "Khác").
    # Tránh dùng từ 3-4 ký tự (vd "News") kẻo bị hiểu nhầm là mã chứng khoán.
    scraper.export_to_files(filename_prefix="CafeF_Article")