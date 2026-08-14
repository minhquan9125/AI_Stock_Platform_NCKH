import argparse
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


class CafeFBCTCScraper:

    def __init__(self, keyword, max_reports=15):
        """Khởi tạo Scraper chuyên dụng cho Báo Cáo Tài Chính (BCTC).

        :param keyword: Mã cổ phiếu hoặc từ khóa (VD: "FPT", "VCI", "HPG",
            "Vietcombank")
        :param max_reports: Số lượng báo cáo tối đa muốn lấy
        """
        self.keyword = keyword.upper() if len(keyword) <= 4 else keyword
        self.max_reports = max_reports
        self.base_url = "https://cafef.vn"

        # Tối ưu từ khóa tìm kiếm: Ghép thêm chữ "Báo cáo tài chính" để lọc chuẩn xác nhất
        self.search_query = f"Báo cáo tài chính {self.keyword}"
        self.search_url_template = (
            "https://cafef.vn/tim-kiem/trang-{page}.chn?keywords={keyword}"
        )

        self.session = requests.Session()
        self.reports_data = []

        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        ]

    def _get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Referer": "https://cafef.vn/",
        }

    def _fetch_html(self, url):
        try:
            response = self.session.get(
                url, headers=self._get_headers(), timeout=10
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            print(f"[!] Lỗi kết nối đến {url}: {e}")
        return None

    def _clean_text(self, text):
        return re.sub(r"\s+", " ", text).strip() if text else ""

    def _parse_date(self, date_str):
        try:
            match = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})", date_str)
            if match:
                return datetime.strptime(
                    match.group(1).replace("-", "/"), "%d/%m/%Y"
                )
        except Exception:
            pass
        return datetime.min

    def _detect_report_period(self, text):
        """Tự động nhận diện kỳ báo cáo từ Tiêu đề hoặc Nội dung (Phục vụ phân
        loại cho Vector DB).
        """
        text_lower = text.lower()
        year_match = re.search(r"(202\d|201\d)", text)
        year = year_match.group(1) if year_match else ""

        if "quý 1" in text_lower or "q1" in text_lower:
            return f"Quý 1/{year}" if year else "Quý 1"
        elif "quý 2" in text_lower or "q2" in text_lower or "bán niên" in text_lower:
            return f"Quý 2 (Bán niên)/{year}" if year else "Quý 2"
        elif "quý 3" in text_lower or "q3" in text_lower:
            return f"Quý 3/{year}" if year else "Quý 3"
        elif "quý 4" in text_lower or "q4" in text_lower:
            return f"Quý 4/{year}" if year else "Quý 4"
        elif "thường niên" in text_lower or "cả năm" in text_lower or "kiểm toán" in text_lower:
            return f"Năm/{year}" if year else "Báo cáo Năm"
        return "Báo cáo định kỳ"

    def search_bctc_links(self):
        """Quét tìm kiếm các bài công bố Báo cáo tài chính."""
        print(
            f"[*] Đang tìm kiếm BCTC cho từ khóa: '{self.keyword}' (Query: '{self.search_query}')..."
        )
        encoded_kw = quote(self.search_query)
        page = 1
        found_links = set()

        # Từ khóa bắt buộc phải có trong tiêu đề hoặc link để lọc bỏ tin tức rác không liên quan
        valid_keywords = [
            "bctc",
            "báo cáo tài chính",
            "kết quả kinh doanh",
            "lợi nhuận",
            "doanh thu",
            "quý",
            "kiểm toán",
            "thường niên",
        ]

        while len(found_links) < self.max_reports and page <= 10:
            url = self.search_url_template.format(page=page, keyword=encoded_kw)
            print(f"   -> Đang quét trang {page}...")
            html = self._fetch_html(url)
            if not html:
                break

            soup = BeautifulSoup(html, "html.parser")
            items = (
                soup.select("div.item")
                or soup.select("div.tlitem")
                or soup.select(".list-search .item")
            )

            if not items:
                break

            new_count = 0
            for item in items:
                if len(found_links) >= self.max_reports:
                    break

                title_tag = item.find("h3") or item.find("h4") or item.find("a")
                if not title_tag:
                    continue

                title_text = self._clean_text(title_tag.get_text()).lower()

                # Kiểm tra xem bài có thực sự nói về BCTC hay không
                if not any(kw in title_text for kw in valid_keywords):
                    continue

                link_tag = (
                    title_tag.find("a")
                    if title_tag.name != "a"
                    else title_tag
                )
                if not link_tag or "href" not in link_tag.attrs:
                    continue

                full_url = urljoin(self.base_url, link_tag["href"])
                if "cafef.vn" in full_url and full_url not in found_links:
                    found_links.add(full_url)
                    new_count += 1

            if new_count == 0:
                break
            page += 1
            time.sleep(random.uniform(1.0, 2.0))

        print(
            f"[+] Đã lọc được {len(found_links)} bài viết/công bố về BCTC của '{self.keyword}'.\n"
        )
        return list(found_links)

    def scrape_report_detail(self, url):
        """Vào chi tiết bài công bố để trích xuất nội dung và QUAN TRỌNG NHẤT:
        Quét link tải PDF/Excel.
        """
        html = self._fetch_html(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("h1", class_="title") or soup.find(
            "h1", class_="article-title"
        )
        title = (
            self._clean_text(title_tag.get_text())
            if title_tag
            else "No Title"
        )

        date_tag = (
            soup.find("span", class_="pdate")
            or soup.find("span", class_="date-and-time")
            or soup.find("span", class_="time")
        )
        date_str = (
            self._clean_text(date_tag.get_text()) if date_tag else ""
        )
        parsed_date = self._parse_date(date_str)

        # 1. Trích xuất text nội dung (để tóm tắt chỉ số bằng LLM)
        content_div = (
            soup.find("div", class_="detail-content")
            or soup.find("div", class_="contentdetail")
            or soup.find("div", id="mainContent")
        )
        content_text = ""
        pdf_links = []

        if content_div:
            # QUAN TRỌNG: Tìm tất cả các đường link đính kèm file (PDF, DOC, EXCEL, RAR, ZIP)
            for a_tag in content_div.find_all("a", href=True):
                href = a_tag["href"]
                # Nhận diện file đính kèm BCTC
                if any(
                    ext in href.lower()
                    for ext in [
                        ".pdf",
                        ".doc",
                        ".docx",
                        ".xls",
                        ".xlsx",
                        ".rar",
                        ".zip",
                        "download",
                    ]
                ):
                    full_file_url = urljoin(url, href)
                    if full_file_url not in pdf_links:
                        pdf_links.append(full_file_url)

            # Làm sạch text sau khi đã lấy link file
            for junk in content_div.find_all(
                ["script", "style", "div"],
                class_=["link-content-footer", "relate-link", "ads"],
            ):
                junk.decompose()
            content_text = " ".join(
                [
                    self._clean_text(p.get_text())
                    for p in content_div.find_all("p")
                    if p.get_text()
                ]
            )

        # Nhận diện kỳ báo cáo (Quý 1, 2, 3, 4...)
        report_period = self._detect_report_period(f"{title} {content_text[:200]}")

        return {
            "ticker": self.keyword,
            "report_period": report_period,
            "title": title,
            "publish_date": date_str,
            "_sort_date": parsed_date,
            "url": url,
            "attached_files": pdf_links,  # Danh sách link tải PDF/Excel BCTC
            "has_pdf": len(pdf_links) > 0,
            "content_summary": content_text[
                :1000
            ],  # Lấy 1000 ký tự đầu để review nhanh
            "full_content": content_text,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def run(self):
        links = self.search_bctc_links()

        for idx, link in enumerate(links, 1):
            print(f"[{idx}/{len(links)}] Đang cào BCTC từ: {link}")
            data = self.scrape_report_detail(link)

            if data and (
                data["has_pdf"] or len(data["full_content"]) > 100
            ):
                self.reports_data.append(data)
                status_file = (
                    f"| Tìm thấy {len(data['attached_files'])} file đính kèm"
                    if data["has_pdf"]
                    else "| Chỉ có text"
                )
                print(
                    f"   + [Thành công] {data['report_period']} {status_file}"
                )
            else:
                print("   - [Bỏ qua] Không có thông tin hoặc file BCTC hợp lệ.")

            time.sleep(random.uniform(1.5, 2.5))

        # Sắp xếp ưu tiên Báo cáo mới nhất lên đầu
        print("\n[*] Đang sắp xếp ưu tiên Báo Cáo Tài Chính mới nhất...")
        self.reports_data.sort(
            key=lambda x: x["_sort_date"], reverse=True
        )

        for item in self.reports_data:
            del item["_sort_date"]

        print(
            f"[+] Hoàn tất! Thu thập thành công {len(self.reports_data)} bản báo cáo tài chính của {self.keyword}."
        )

    def export_data(self, prefix="BCTC"):
        if not self.reports_data:
            print("[!] Không có dữ liệu để xuất.")
            return

        # 1. Xuất JSON
        json_file = f"{prefix}_{self.keyword}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.reports_data, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã lưu dữ liệu BCTC vào file JSON: {json_file}")

        # 2. Xuất CSV
        csv_file = f"{prefix}_{self.keyword}.csv"
        keys = self.reports_data[0].keys()
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.reports_data)
        print(f"[v] Đã lưu bảng tổng hợp vào file CSV: {csv_file}")

    def download_pdf_files(self, save_dir=None):
        """Hàm bổ trợ cực kỳ hữu ích cho dự án NCKH: Tự động tải các file PDF/Excel BCTC tìm được về ổ cứng máy tính."""
        if not save_dir:
            save_dir = f"./BCTC_Files_{self.keyword}"

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        print(f"\n[*] Bắt đầu tải các file BCTC gốc về thư mục: {save_dir}")
        downloaded_count = 0

        for item in self.reports_data:
            for file_url in item["attached_files"]:
                try:
                    # Tạo tên file dễ đọc từ kỳ báo cáo và tên gốc
                    file_name = file_url.split("/")[-1].split("?")[0]
                    clean_period = (
                        re.sub(r"[^\w\-]", "_", item["report_period"])
                        + "_"
                    )
                    full_save_path = os.path.join(save_dir, clean_period + file_name)

                    if not os.path.exists(
                        full_save_path
                    ):  # Không tải lại nếu file đã có
                        print(f"   -> Đang tải: {file_name}...")
                        r = self.session.get(
                            file_url, headers=self._get_headers(), stream=True
                        )
                        if r.status_code == 200:
                            with open(full_save_path, "wb") as f:
                                for chunk in r.iter_content(1024):
                                    f.write(chunk)
                            downloaded_count += 1
                            time.sleep(1)
                except Exception as e:
                    print(f"   [!] Lỗi khi tải file {file_url}: {e}")

        print(f"[+] Đã tải xong {downloaded_count} file BCTC gốc về máy!\n")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    # Mã cổ phiếu cần cào BCTC (VD: "FPT", "VCB", "HPG", "MWG").
    # Thứ tự ưu tiên: --ticker > biến môi trường FINMIND_TICKER > mặc định "FPT".
    cli = argparse.ArgumentParser(description="Cào công bố BCTC trên CafeF cho MỘT mã cổ phiếu")
    cli.add_argument("--ticker", default=os.getenv("FINMIND_TICKER", "FPT"), help="Mã cổ phiếu hoặc từ khóa cần cào")
    cli.add_argument("--max-reports", type=int, default=10, help="Số báo cáo tối đa cần thu thập")
    args = cli.parse_args()

    TICKER = args.ticker.strip()
    if TICKER.isalnum() and len(TICKER) <= 10:  # là mã CK -> viết hoa cho đồng nhất tên file
        TICKER = TICKER.upper()

    # Khởi tạo tool cào BCTC riêng biệt
    bctc_scraper = CafeFBCTCScraper(keyword=TICKER, max_reports=args.max_reports)

    # 1. Chạy cào thông tin báo cáo & link tải file
    bctc_scraper.run()

    # 2. Xuất dữ liệu ra file JSON & CSV
    bctc_scraper.export_data(prefix="Data_BCTC")

    # 3. (OPTIONAL) Tự động tải luôn các file PDF/Excel BCTC tìm được về máy cho pdfplumber xử lý
    # Mở comment dòng dưới đây nếu muốn tool tự động tải file gốc về ổ cứng:
    # bctc_scraper.download_pdf_files()