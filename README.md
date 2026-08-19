# Stock Article Crawler cho Hybrid Graph–Vector RAG

Hệ thống thu thập bài phân tích chứng khoán theo một hoặc nhiều mã, hiện hoàn thiện nguồn CafeF. Pipeline tách biệt tìm kiếm, raw HTML, parser, làm sạch, relevance, chống trùng, state và lưu trữ để dễ bổ sung nguồn.

## Cài đặt trên Windows

Yêu cầu Python 3.10+:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
```

Chạy:

```powershell
python main.py --ticker FPT --limit 100
python main.py --tickers FPT HPG VNM --max-pages 20
python main.py --ticker FPT --from-date 2025-01-01 --to-date 2026-07-29
python main.py --ticker FPT --retry-failed
python main.py --ticker FPT --reset-state
python main.py --ticker FPT --save-raw-html --verbose
pytest -v
```

`--ticker` và `--tickers` loại trừ nhau. Ticker được uppercase và validate; workers giới hạn 1–3, nhưng CafeF hiện cố ý chạy tuần tự để tôn trọng rate limit. Reset state tạo file backup có timestamp, không xóa dataset.

## Kiến trúc và luồng

```text
Search queries → URL canonicalization → Raw HTML → RawArticle
→ cleaned content → date/relevance/classification → URL/hash/fuzzy dedup
→ accepted/rejected/failed JSONL → CSV + crawl_report.json
```

- `crawlers/`: interface nguồn, HTTP retry/backoff, CafeF.
- `processing/`: main-content cleaner, ngày giờ +07:00, relevance, rule classifier, dedup.
- `storage/`: JSONL append-only, CSV và resume state.
- `services/`: resolve doanh nghiệp và điều phối.
- `models/`: Pydantic models có type validation.
- `config/companies.json`: tên và aliases. Mã chưa có dùng ticker mặc định và ghi warning.

Dataset chính: `data/cleaned/FPT/FPT_articles.jsonl`; bài không đạt/duplicate: `data/rejected/FPT/FPT_rejected.jsonl`; lỗi: `data/failed/FPT/`; state: `data/state/FPT/`; CSV/report: `data/exports/FPT/`. Mỗi dòng JSONL là một `ArticleRecord`, gồm URL gốc/canonical, timestamp đầy đủ, nội dung/hash, loại tài liệu/sự kiện và bằng chứng relevance.

Relevance mặc định nhận bài từ 5 điểm và tối thiểu 150 từ. Ticker dùng regex boundary; tiêu đề/sapo có trọng số cao, số liệu và thuật ngữ tài chính cộng điểm, bài ngắn/nhắc yếu/liệt kê nhiều mã bị trừ. Điều chỉnh bằng `--min-relevance-score` và `--min-word-count`.

Để thêm mã, thêm object vào `config/companies.json` với `company_name`,
`short_name`, `aliases`, `positive_aliases` và `excluded_entities`.
`positive_aliases` là bằng chứng xác định đúng pháp nhân (ví dụ `HoSE: FPT`);
`excluded_entities` ánh xạ công ty có tên dễ nhầm sang ticker riêng (ví dụ
`FPT Retail → FRT`). Để thêm nguồn, kế thừa `BaseArticleCrawler`, triển khai
`search_articles` và `parse_article`, rồi đăng ký crawler trong CLI/service.

## Tương thích mã cũ

Các file cũ được giữ nguyên: `CafeFScraper.py` được thay thế cho use case bài viết bởi `main.py` + `crawlers/cafef.py`; `cafef_bctc_scraper.py` vẫn dùng cho tệp BCTC; `vnstock_data_fetcher.py` và `finmind_file_organizer.py` vẫn độc lập. Dữ liệu `FinMind_Data_Lake/` không bị sửa hoặc ghi đè.

## Giới hạn và pháp lý

Selector CafeF có thể đổi và cần fixture mới. Crawler không vượt CAPTCHA, không xoay proxy, không né chặn; hãy tuân thủ robots.txt, điều khoản, bản quyền và chỉ lưu/khai thác dữ liệu trong phạm vi được phép. Vietstock, HOSE/HNX/SSC và các nguồn khác chưa triển khai. Nội dung nguồn không được AI viết lại và kết quả không phải khuyến nghị đầu tư.
