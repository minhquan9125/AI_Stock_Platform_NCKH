# Brokerage Report Crawler

## Chạy nhanh

Người dùng thông thường chỉ cần chạy:

```powershell
python main.py
```

Sau đó nhập mã cổ phiếu và số báo cáo mong muốn. Số này là **mục tiêu báo cáo
hợp lệ, duy nhất**, không phải số URL discovery. Các record đã có trong JSONL
được tính vào mục tiêu; crawler tự phân trang đến khi đủ mục tiêu hoặc các nguồn
hết kết quả.

Chế độ nâng cao vẫn hỗ trợ:

```powershell
python main.py --ticker FPT --target 100 --sources cafef vietstock ssi vndirect
```

Mặc định CLI và hàm `crawl_reports()` chỉ bật `cafef` và `vietstock`. SSI và
VNDirect vẫn được giữ để phát triển tiếp nhưng chỉ chạy khi chỉ định rõ bằng
`--sources`. URL tải lỗi, báo cáo bị loại và bản trùng không làm tăng target;
target chỉ dựa trên số record duy nhất thực sự nằm trong cleaned JSONL.

`--limit` được giữ làm alias tương thích cho `--target`. `--max-pages` chỉ là
giới hạn an toàn tùy chọn; mặc định hệ thống tự phân trang, dừng sau hai trang
liên tiếp không có URL mới hoặc khi đạt giới hạn an toàn 50 trang.

Discovery các nguồn và xử lý PDF chạy song song tối đa 3 worker. HTTP client chỉ
chờ một khoảng nhỏ giữa hai request tới cùng domain; backoff dài chỉ áp dụng cho
HTTP 429/5xx. Kết quả trả thêm `existing_reports`, `new_accepted`,
`total_unique_reports`, `duplicates`, `rejected`, `failed` và
`exhausted_sources`.

Frontend có thể gọi trực tiếp:

```python
from services import crawl_reports

result = crawl_reports("FPT", target_reports=100)
```

Chạy toàn bộ 30 mã VN30 (target áp dụng riêng cho từng mã):

```powershell
python main.py --group VN30 --target 20
```

## Nguồn dữ liệu giai đoạn đầu

Project có crawler riêng cho CafeF, Vietstock Finance, SSI Research và VNDirect
Research. CafeF dùng kho `https://cafef.vn/du-lieu/phan-tich-bao-cao.chn`;
Vietstock dùng `https://finance.vietstock.vn/bao-cao-phan-tich`.

CafeF cung cấp metadata trong HTML nhưng nút tải PDF là sự kiện Blazor. Crawler
chỉ khởi động Chrome headless để lấy URL PDF khi parse chi tiết CafeF; mọi bước
tìm kiếm, parse metadata, tải và kiểm tra PDF vẫn dùng HTTP thông thường. CafeF
hiện chỉ hiển thị “Tóm tắt AI”, không phải mô tả gốc, nên crawler không đưa phần
này vào dataset: `description` được để `null` và lý do được ghi trong
`validation_notes`.

`source_platform` luôn là nơi tìm thấy báo cáo (`CafeF`, `Vietstock Finance`);
`broker` là đơn vị thực sự phát hành (`SSI`, `BVS`, `VCBS`...). Nếu SHA-256 của
PDF trùng nhau, hệ thống giữ một record, ưu tiên domain chính thức của broker làm
`canonical_source_url` và đưa URL kho tổng hợp vào `mirror_urls`.

Project độc lập chuyên thu thập báo cáo phân tích do các công ty chứng khoán
phát hành, phục vụ bộ dữ liệu Hybrid Graph–Vector RAG. Project không chỉnh sửa
hoặc phụ thuộc vào crawler tin tức CafeF.

Hệ thống hiện có crawler riêng cho Vietstock Finance, SSI Research và VNDirect
Research. Vietstock dùng trang `finance.vietstock.vn/bao-cao-phan-tich` và XHR
công khai `ChannelEDocumentPage`; SSI đọc danh sách báo cáo và
đường dẫn tải chính thức; VNDirect dùng trang tìm kiếm WordPress nhẹ. Khi nguồn
trả CAPTCHA hoặc HTTP 403, crawler ghi lỗi và dừng, không né chặn.

## Cấu trúc

```text
brokerage_report_crawler/
├── main.py
├── config/                 # settings, companies, brokers
├── crawlers/               # BaseCrawler, HTTP, Vietstock, SSI, VNDirect
├── models/                 # ReportCandidate, ReportRecord
├── processing/             # PDF, ticker, metadata, recommendation, dedup
├── storage/                # JSONL, CSV, state
├── services/               # pipeline và mirror merger
├── tests/fixtures/         # HTML fixture, test PDF sinh trong tmp
├── logs/
└── data/
    ├── raw/                # metadata tìm thấy trước xử lý
    ├── pdf/                # PDF gốc, không ghi đè
    ├── extracted/          # text UTF-8
    ├── cleaned/            # dataset chính
    ├── duplicates/         # dấu vết bản trùng
    ├── failed/             # lỗi, rejected, needs review
    ├── state/              # ticker/source resume state
    └── exports/            # CSV và crawl_report.json
```

## Cài đặt trên Windows

```powershell
cd "C:\Users\Administrator\Desktop\CODE\nghiên cứu khoa học\brokerage_report_crawler"
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -U pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

Nếu PowerShell chặn `Activate.ps1`, không cần đổi Execution Policy; gọi trực
tiếp `.venv\Scripts\python.exe` như các lệnh trên.

Trong workspace hiện tại có thể dùng môi trường dùng chung:

```powershell
& "C:\Users\Administrator\.venv\Scripts\python.exe" main.py --ticker FPT
```

## Cách chạy

Một hoặc nhiều mã:

```powershell
python main.py --ticker FPT
python main.py --tickers FPT HPG VNM
```

Chọn nguồn:

```powershell
python main.py --ticker FPT --sources cafef vietstock ssi vndirect --limit 100 --max-pages 5
```

Tải và trích xuất PDF:

```powershell
python main.py --ticker FPT --sources vietstock --limit 5 --max-pages 1 --download-pdf --extract-pdf
python main.py --ticker FPT --sources cafef vietstock --limit 5 --max-pages 1 --download-pdf --extract-pdf
```

`--extract-pdf` yêu cầu `--download-pdf`. PyMuPDF được ưu tiên. PDF có quá ít
text được đánh dấu `needs_ocr`; giai đoạn này không tự OCR.

Giới hạn ngày, retry và state:

```powershell
python main.py --ticker FPT --from-date 2025-01-01 --to-date 2026-07-29
python main.py --ticker FPT --sources vietstock --retry-failed
python main.py --ticker FPT --sources vietstock --reset-state
```

Reset đổi tên state cũ thành file `.bak` có timestamp, không xóa dataset/PDF.
State được tách theo `data/state/{ticker}/{source}/`. URL retry thành công được
xóa khỏi failed ledger đang hoạt động.

## Pipeline và kiểm tra PDF

```text
Source listing/XHR → ReportCandidate → ticker validation
→ tải PDF → Content-Type + %PDF magic bytes
→ SHA-256 → PyMuPDF extraction → metadata rules
→ dedup/merge mirrors → JSONL + CSV + state/report
```

Download theo redirect, timeout, tối đa ba lần retry và exponential backoff.
HTML giả PDF bị từ chối. Tên file:

```text
{broker}_{ticker}_{published_date}_{pdf_hash_8}.pdf
```

File cùng hash không được ghi đè. Text được lưu nguyên bản UTF-8; không gọi LLM
và không viết lại nội dung nguồn.

## Xác định ticker và broker

Ticker được kiểm tra bằng tiêu đề, metadata và phần đầu nội dung PDF. Cấu hình
`positive_aliases` xác nhận pháp nhân; `excluded_entities` ngăn FPT bị nhầm với
FRT, FOX, FTS hoặc FOC. Nếu thiếu bằng chứng, record không vào cleaned dataset.

`source_platform` là nơi tìm thấy báo cáo; `broker` là đơn vị phát hành. Ví dụ
PDF BVS trên Vietstock có `source_platform="Vietstock Finance"` và
`broker="BVS"`.

Nếu PDF/hash nội dung trùng nhau, merger ưu tiên domain chính thức của broker
làm `canonical_source_url`; URL còn lại được giữ trong `mirror_urls`. Dấu vết
bản trùng được append vào `data/duplicates/`.

## Metadata và JSONL

Rule parser hỗ trợ recommendation chuẩn:

```text
BUY, OUTPERFORM, ACCUMULATE, HOLD, NEUTRAL, REDUCE, SELL, NOT_RATED
```

Đồng thời trích xuất có điều kiện giá mục tiêu, giá hiện tại, upside, analyst và
DCF/P_E/P_B/EV_EBITDA/SOTP/DDM/RNAV. Không tìm thấy thì để `null` hoặc `[]`.

Dataset:

```text
data/cleaned/FPT/FPT_brokerage_reports.jsonl
data/exports/FPT/FPT_brokerage_reports.csv
data/exports/FPT/crawl_report.json
```

Mỗi dòng JSONL là một `ReportRecord`, gồm ticker, broker/source, ngày, metadata
khuyến nghị, URL/PDF/hash, text path, page count, status và validation notes.

## Thêm ticker hoặc nguồn

Thêm ticker vào `config/companies.json` với `company_name`,
`positive_aliases`, `excluded_entities`.

Để thêm nguồn:

1. Tạo class kế thừa `BaseCrawler`.
2. Triển khai `search_reports`; tùy chọn `fetch_detail`.
3. Đăng ký class trong `crawlers.CRAWLERS`.
4. Thêm fixture và test parser offline.
5. Thêm broker/domain chính thức vào `config/brokers.json`.

## Kiểm thử

```powershell
python -m compileall .
python -m pytest -v
```

Test không phụ thuộc website online. PDF text được tạo trong thư mục pytest tạm;
file giả PDF, ticker FPT/FRT, recommendation, target price, date, hash,
near-duplicate, mirror merger và resume/retry đều được kiểm tra.

## Rate limit, bản quyền và giới hạn

- Mặc định chạy tuần tự và nghỉ ngẫu nhiên 1,5–4 giây.
- `--workers` giới hạn tối đa 3; phiên bản hiện tại cố ý xử lý tuần tự.
- Không proxy, bypass CAPTCHA, giả mạo phiên đăng nhập hoặc né HTTP 403.
- Selector/API công khai có thể thay đổi và cần cập nhật fixture.
- Người sử dụng phải tuân thủ robots.txt, điều khoản, bản quyền và phạm vi sử
  dụng hợp pháp của từng báo cáo.
- Metadata rule-based có thể để trống; dữ liệu này không phải khuyến nghị đầu tư
  của hệ thống.
