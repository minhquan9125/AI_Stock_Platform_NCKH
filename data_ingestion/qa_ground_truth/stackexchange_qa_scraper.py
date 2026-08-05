import csv
import json
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# NHÓM IV.7 - BỘ DỮ LIỆU HỎI-ĐÁP CHUẨN (Ground-Truth QA)
#
# Nguồn: StackExchange API chính thức (https://api.stackexchange.com),
# site "quant" = Quantitative Finance. Đây là dữ liệu THẬT do cộng đồng
# chuyên gia định lượng/tài chính đặt câu hỏi và trả lời, có cơ chế bình
# chọn (score) và "câu trả lời được chấp nhận" (accepted answer) - tức
# CHÍNH NGƯỜI HỎI đã xác nhận câu trả lời đó đúng. Vì vậy trường
# "human_verified" chỉ = True khi có accepted answer thật sự, không phải
# suy đoán hay tự sinh.
#
# Giấy phép: Nội dung StackExchange dùng chung CC BY-SA 4.0, YÊU CẦU ghi
# nguồn khi tái sử dụng -> mỗi bản ghi giữ nguyên "question_url" và
# "attribution" để tuân thủ.
# =====================================================================

API_BASE = "https://api.stackexchange.com/2.3"
SITE = "quant"  # Quantitative Finance StackExchange


def _clean_html(html_text):
    """Chuyển HTML trả về từ StackExchange API sang văn bản sạch."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _get(url, params, max_retries=3):
    """Gọi API kèm xử lý ngoại lệ và tôn trọng cờ 'backoff' của
    StackExchange (yêu cầu chờ thêm giây trước khi gọi lại)."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
        except Exception as e:
            print(f"   [!] Lỗi gọi API (lần {attempt + 1}): {e}")
            time.sleep(2)
            continue

        if "error_message" in data:
            print(f"   [!] StackExchange API lỗi: {data['error_message']}")
            return None

        backoff = data.get("backoff")
        if backoff:
            print(f"   [*] API yêu cầu nghỉ {backoff}s trước request tiếp theo...")
            time.sleep(backoff)

        return data
    return None


class StackExchangeQAScraper:
    """Cào bộ câu hỏi-đáp chất lượng cao (đã có bình chọn cộng đồng) từ
    Quantitative Finance StackExchange, dùng làm Ground-Truth QA dataset
    cho việc đo lường Answer Correctness / Hallucination Rate."""

    def __init__(self, question_pages=2, pagesize=100, answer_batch_size=100):
        self.question_pages = question_pages
        self.pagesize = pagesize
        self.answer_batch_size = answer_batch_size
        self.qa_pairs = []

    def _fetch_answered_questions(self):
        """Lấy các câu hỏi được bình chọn cao nhất và ĐÃ có câu trả lời."""
        questions = []
        for page in range(1, self.question_pages + 1):
            print(f"[*] Đang tải trang câu hỏi {page}/{self.question_pages}...")
            data = _get(
                f"{API_BASE}/questions",
                params={
                    "site": SITE,
                    "page": page,
                    "pagesize": self.pagesize,
                    "order": "desc",
                    "sort": "votes",
                    "filter": "withbody",
                },
            )
            if not data:
                break

            for q in data.get("items", []):
                if q.get("is_answered") and q.get("answer_count", 0) > 0:
                    questions.append(q)

            if not data.get("has_more"):
                break
            time.sleep(1)

        print(f"[+] Tìm được {len(questions)} câu hỏi đã có trả lời.\n")
        return questions

    def _fetch_best_answers(self, question_ids):
        """Lấy câu trả lời điểm cao nhất cho từng câu hỏi (ưu tiên
        accepted answer), gọi theo lô để tiết kiệm quota API."""
        answers_by_question = {}

        for i in range(0, len(question_ids), self.answer_batch_size):
            batch = question_ids[i : i + self.answer_batch_size]
            print(
                f"[*] Đang tải câu trả lời cho lô {i // self.answer_batch_size + 1} "
                f"({len(batch)} câu hỏi)..."
            )
            ids_str = ";".join(str(qid) for qid in batch)

            # 1 lô câu hỏi có thể có nhiều hơn 100 câu trả lời cộng lại
            # (mỗi câu hỏi có thể có nhiều answer) -> phải phân trang hết,
            # không được dừng lại ở trang đầu tiên (mặc định API chỉ trả
            # 30 kết quả/trang nếu không truyền pagesize).
            page = 1
            while True:
                data = _get(
                    f"{API_BASE}/questions/{ids_str}/answers",
                    params={
                        "site": SITE,
                        "page": page,
                        "pagesize": 100,
                        "order": "desc",
                        "sort": "votes",
                        "filter": "withbody",
                    },
                )
                if not data:
                    break

                for ans in data.get("items", []):
                    qid = ans["question_id"]
                    current_best = answers_by_question.get(qid)
                    # Ưu tiên accepted answer; nếu chưa có thì lấy điểm cao nhất
                    if current_best is None:
                        answers_by_question[qid] = ans
                    elif ans.get("is_accepted") and not current_best.get(
                        "is_accepted"
                    ):
                        answers_by_question[qid] = ans
                    elif ans.get("score", 0) > current_best.get(
                        "score", 0
                    ) and not current_best.get("is_accepted"):
                        answers_by_question[qid] = ans

                if not data.get("has_more"):
                    break
                page += 1
                time.sleep(1)

            time.sleep(1)

        return answers_by_question

    def run(self):
        questions = self._fetch_answered_questions()
        if not questions:
            print("[!] Không lấy được câu hỏi nào từ StackExchange.")
            return

        question_ids = [q["question_id"] for q in questions]
        answers_by_question = self._fetch_best_answers(question_ids)

        for q in questions:
            qid = q["question_id"]
            best_answer = answers_by_question.get(qid)
            if not best_answer:
                continue

            self.qa_pairs.append(
                {
                    "source": "StackExchange - Quantitative Finance",
                    "question_id": qid,
                    "title": q.get("title", ""),
                    "tags": ", ".join(q.get("tags", [])),
                    "question_body": _clean_html(q.get("body", "")),
                    "question_score": q.get("score", 0),
                    "question_url": q.get("link", ""),
                    "answer_body": _clean_html(best_answer.get("body", "")),
                    "answer_score": best_answer.get("score", 0),
                    "is_accepted_answer": bool(best_answer.get("is_accepted")),
                    "human_verified": bool(best_answer.get("is_accepted")),
                    "content_license": "CC BY-SA 4.0",
                    "attribution": "Stack Exchange Inc. - https://quant.stackexchange.com",
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        verified_count = sum(1 for x in self.qa_pairs if x["human_verified"])
        print(
            f"\n[+] Hoàn tất! Thu thập {len(self.qa_pairs)} cặp Q&A "
            f"({verified_count} cặp có accepted answer = human_verified)."
        )

    def export_to_files(self, filename_prefix="FinMind_QA_StackExchange"):
        if not self.qa_pairs:
            print("[!] Không có dữ liệu để xuất file.")
            return

        json_file = f"{filename_prefix}.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.qa_pairs, f, ensure_ascii=False, indent=4)
        print(f"[v] Đã xuất file chuẩn JSON: {json_file}")

        csv_file = f"{filename_prefix}.csv"
        keys = self.qa_pairs[0].keys()
        with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.qa_pairs)
        print(f"[v] Đã xuất file bảng biểu CSV: {csv_file}")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH
# =====================================================================
if __name__ == "__main__":
    # 2 trang x 100 câu hỏi = tối đa 200 câu hỏi được bình chọn cao nhất
    # (chỉ tốn ~4 request API, quota miễn phí 300 request/ngày/IP)
    scraper = StackExchangeQAScraper(question_pages=2, pagesize=100)
    scraper.run()
    scraper.export_to_files(filename_prefix="FinMind_QA_StackExchange")
