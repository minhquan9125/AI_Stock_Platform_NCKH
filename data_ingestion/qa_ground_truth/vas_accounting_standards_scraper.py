import csv
import json
import re
import sys
import time
import random
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# NHÓM IV.7 - TỪ ĐIỂN CHUẨN MỰC KẾ TOÁN VIỆT NAM (VAS)
#
# Nguồn: https://ktkt.uel.edu.vn (Khoa Kế toán - Kiểm toán, Trường ĐH
# Kinh tế - Luật, ĐHQG TP.HCM), trang liệt kê đầy đủ 26 Chuẩn mực Kế
# toán Việt Nam kèm toàn văn nội dung chính thức.
#
# Ghi chú bản quyền: Văn bản quy phạm pháp luật (chuẩn mực kế toán do Bộ
# Tài chính ban hành) KHÔNG thuộc đối tượng bảo hộ quyền tác giả theo
# Điều 15 Luật Sở hữu trí tuệ Việt Nam, nên có thể tái sử dụng tự do cho
# mục đích nghiên cứu khoa học. Vẫn giữ lại source_url để truy vết.
#
# Cơ chế phân trang: Trang danh sách dùng ASP.NET WebForms postback
# (__doPostBack), KHÔNG phải link GET thông thường -> phải mô phỏng POST
# với đầy đủ __VIEWSTATE/__EVENTVALIDATION lấy từ trang trước đó.
# =====================================================================

BASE_URL = "https://ktkt.uel.edu.vn/chuan-muc-ke-toan-viet-nam-vas2"
NEXT_PAGE_TARGET = "ctl15$ctl01$lbtNext"
MAX_PAGES = 10  # Chặn an toàn, tránh vòng lặp vô hạn nếu web đổi cấu trúc


class VASAccountingScraper:
    """Cào toàn văn 26 Chuẩn mực Kế toán Việt Nam (VAS) từ ktkt.uel.edu.vn."""

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": BASE_URL,
        }
        self.standards = []

    def _extract_form_payload(self, soup):
        """Lấy toàn bộ input ẩn (__VIEWSTATE, __EVENTVALIDATION...) cần
        thiết để giả lập postback ASP.NET."""
        form = soup.find("form")
        payload = {}
        if not form:
            return payload
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name:
                payload[name] = inp.get("value", "")
        for sel in form.find_all("select"):
            name = sel.get("name")
            if name:
                opt = sel.find("option", selected=True) or sel.find("option")
                payload[name] = opt.get("value", "") if opt else ""
        return payload

    def _collect_standard_links(self):
        """Duyệt hết các trang danh sách (postback) để lấy đầy đủ URL chi
        tiết của 26 chuẩn mực."""
        print("[*] Đang tải trang danh sách Chuẩn mực Kế toán Việt Nam...")
        r = self.session.get(BASE_URL, headers=self.headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        all_links = set()
        all_links.update(
            a["href"] for a in soup.select("a[href*='chuan-muc-so-']")
        )

        for page_num in range(2, MAX_PAGES + 1):
            payload = self._extract_form_payload(soup)
            if not payload:
                break
            payload["__EVENTTARGET"] = NEXT_PAGE_TARGET
            payload["__EVENTARGUMENT"] = ""

            r = self.session.post(
                BASE_URL, headers=self.headers, data=payload, timeout=15
            )
            soup = BeautifulSoup(r.text, "html.parser")
            new_links = set(
                a["href"] for a in soup.select("a[href*='chuan-muc-so-']")
            )

            before = len(all_links)
            all_links.update(new_links)
            added = len(all_links) - before

            print(f"   -> Trang {page_num}: +{added} chuẩn mực mới.")
            if added == 0:
                break  # Hết trang (postback lặp lại trang cuối)

        full_urls = sorted(
            f"https://ktkt.uel.edu.vn{link}" if link.startswith("/") else link
            for link in all_links
        )
        print(f"[+] Tổng cộng tìm được {len(full_urls)} Chuẩn mực Kế toán.\n")
        return full_urls

    def _parse_standard_number(self, url, title):
        match = re.search(r"chuan-muc-so-(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"[Ss]ố\s*(\d+)", title)
        return match.group(1) if match else ""

    def _clean_full_text(self, div):
        """Lấy toàn văn và cắt bỏ phần điều hướng 'Các tin khác :' ở
        cuối trang (không thuộc nội dung chuẩn mực)."""
        text = div.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        cut_idx = text.find("Các tin khác :")
        if cut_idx != -1:
            text = text[:cut_idx].strip()
        return text

    def scrape_standard(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=15)
            if r.status_code != 200:
                print(f"   [!] Lỗi HTTP {r.status_code}: {url}")
                return None
        except Exception as e:
            print(f"   [!] Ngoại lệ khi tải {url}: {e}")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""

        content_div = soup.find("div", class_="content_detail") or soup.find(
            "div", class_="article_content"
        )
        if not content_div:
            print(f"   [-] Không tìm thấy nội dung: {url}")
            return None

        full_text = self._clean_full_text(content_div)
        if len(full_text) < 200:
            print(f"   [-] Nội dung quá ngắn, bỏ qua: {url}")
            return None

        vas_number = self._parse_standard_number(url, title)

        return {
            "vas_number": vas_number,
            "title": title,
            "full_text": full_text,
            "char_count": len(full_text),
            "source_url": url,
            "source": "UEL - Khoa Kế toán Kiểm toán (ktkt.uel.edu.vn)",
            "license_note": (
                "Văn bản quy phạm pháp luật - không thuộc đối tượng bảo hộ "
                "quyền tác giả theo Điều 15 Luật SHTT Việt Nam"
            ),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def run(self):
        urls = self._collect_standard_links()
        for idx, url in enumerate(urls, 1):
            print(f"[{idx}/{len(urls)}] Đang cào: {url}")
            standard = self.scrape_standard(url)
            if standard:
                self.standards.append(standard)
                print(
                    f"   + Thành công: VAS {standard['vas_number']} - "
                    f"{standard['title']} ({standard['char_count']} ký tự)"
                )
            time.sleep(random.uniform(1.0, 2.0))

        self.standards.sort(key=lambda x: int(x["vas_number"] or 0))
        print(f"\n[+] Hoàn tất! Thu thập được {len(self.standards)}/26 Chuẩn mực.")

    def export_to_files(self, filename_prefix="FinMind_VAS_AccountingStandards"):
        if not self.standards:
            print("[!] Không có dữ liệu để xuất file.")
            return

        json_file = f"{filename_prefix}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.standards, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

        csv_file = f"{filename_prefix}.csv"
        keys = self.standards[0].keys()
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.standards)
        print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    scraper = VASAccountingScraper()
    scraper.run()
    scraper.export_to_files(filename_prefix="FinMind_VAS_AccountingStandards")
