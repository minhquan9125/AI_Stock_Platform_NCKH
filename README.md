# AI_Stock_Platform_NCKH — Merged Data Ingestion Pipeline

Gộp code từ 4 nhánh (Quan, Nhan, HuynhVu, Huyen) thành 1 pipeline chạy đủ các nhiệm vụ thu thập dữ liệu đã chia trong tài liệu mô tả kiến trúc dữ liệu. Đây là thư mục **local độc lập, chưa gắn với git** — bạn tự kiểm tra rồi quyết định commit/push vào repo chính sau. Đã có sẵn `.gitignore` chặn credentials + dữ liệu tự sinh, an toàn để đưa lên GitHub.

## Ánh xạ Nhiệm vụ → Code

| # | Nhiệm vụ | Thư mục | Nguồn gốc | Trạng thái |
|---|----------|---------|-----------|------------|
| 1 | Báo cáo Thường niên (2000–2025) | *(không có trong pipeline này)* | — | Nhóm xác nhận đã có sẵn dữ liệu, không cần crawler |
| 2 | Báo cáo Phân tích từ CTCK (SSI, VCI, VNDirect, Vietstock...) | `data_ingestion/brokerage_reports/` | Nhan | Đầy đủ — pipeline ETL hoàn chỉnh (crawl → tách PDF → validate → dedup → lưu) |
| 3 | Tin tức & Công bố thông tin hàng ngày | `data_ingestion/news_scraper/` | HuynhVu | Đầy đủ — CafeF, VnEconomy, BCTC announcements |
| 4 | BCTC Quý & Chỉ số định giá (P/E, P/B, ROE, ROA, EPS...) | `data_ingestion/structured_data/vnstock_data_fetcher.py` | HuynhVu/Huyen, **đã sửa lỗi** | Đã sửa: lấy đủ 3 báo cáo VAS (KQKD, CĐKT, LCTT) + ratio đúng chỉ số mới nhất |
| 5 | Giá thị trường OHLCV & Dấu vết dòng tiền | `data_ingestion/structured_data/market_data_fetcher.py` | Quan, **mở rộng** | OHLCV đầy đủ. Khối ngoại: chỉ có snapshot tức thời (xem Giới hạn bên dưới). Tự doanh/block trade: **chưa có nguồn** |
| 6 | Kinh tế Vĩ mô & Giá Hàng hóa | `data_ingestion/macro_commodity/` | Huyen (v2 + v3) | Đầy đủ — World Bank API + Yahoo Finance, ~40+ chỉ số/ticker |
| 7 | QA Chuẩn chuyên gia & Chuẩn mực Kế toán VAS | `data_ingestion/qa_ground_truth/` | HuynhVu | Đầy đủ — StackExchange Quant Q&A + 26 Chuẩn mực Kế toán VN |

## Hướng dẫn cho thành viên nhóm (clone về chạy)

**1. Cài đặt (1 lần):**
```powershell
git clone <link-repo>
cd AI_Stock_Platform_NCKH-Merged   # hoặc tên thư mục sau khi clone
pip install -r requirements.txt
```
Yêu cầu: Python 3.10+. Riêng crawler CafeF (Task 2) dùng Selenium để lấy link PDF, cần máy đã cài sẵn **trình duyệt Chrome** (Selenium 4.25+ tự tải driver phù hợp, không cần cài ChromeDriver tay).

**2. Lấy file `gsheet_credentials.json`:**
File này **không nằm trong git** (bị `.gitignore` chặn cố ý, vì nó là private key thật — từng bị GitHub chặn push do lộ secret). Người giữ file (bạn) cần gửi trực tiếp cho thành viên qua kênh riêng tư **KHÔNG PHẢI git**: nhắn tin/Zalo/Drive riêng... Thành viên nhận file xong đặt đúng vào **gốc thư mục dự án** (cùng cấp với `run_full_pipeline.ps1`), không cần đổi tên.

Google Sheet đích đã share sẵn quyền Editor cho service account `finmind-sheets-bot@gentle-brace-429408-n8.iam.gserviceaccount.com` — thành viên nào có file credentials này đều ghi được vào cùng 1 Sheet của cả nhóm, không cần tạo Sheet riêng.

**3. Chạy toàn bộ pipeline (thu thập + tự động đẩy lên Google Sheet):**
```powershell
./run_full_pipeline.ps1
```
Script tự kiểm tra: nếu **có** `gsheet_credentials.json` ở gốc thư mục → chạy xong sẽ tự động gọi `upload_all_data.py` gom hết CSV vừa tạo và đẩy lên Sheet chung. Nếu **chưa có** file đó → vẫn chạy đủ Task 2-7 và lưu dữ liệu local bình thường, chỉ bỏ qua bước upload (có log cảnh báo rõ ràng, không lỗi dừng chương trình).

Log chi tiết từng bước lưu tại `logs/full_pipeline_<timestamp>.log`.

**Chạy từng phần riêng lẻ / chỉ muốn upload lại lên Sheet:**
```powershell
cd data_ingestion/<tên_thư_mục_task>
py <tên_script>.py

# Upload thủ công (gom toàn bộ CSV hiện có, không cần chạy lại crawler):
cd ../..
py upload_all_data.py
```

## Lỗi đã sửa khi merge (Task 4)

`vnstock_data_fetcher.py` bản gốc có 2 lỗi khiến `fundamental_ratios` chỉ trả về 1 dòng vô nghĩa ("Năm": 2018):

1. Gọi `stock.finance.ratio(period="quarter", lang="vi")` trên cổng KBS — KBS **không nhận** tham số `lang`, gây lỗi và tự động fallback sang VCI.
2. Trên VCI, `ratio()` trả về bảng dạng "wide" (mỗi dòng = 1 chỉ số, mỗi cột = 1 quý), nhưng dữ liệu chỉ có tới 2018 và code cũ lấy `iloc[0]` — tức lấy **dòng đầu tiên** (nhãn "Năm") thay vì cột quý mới nhất.

Bản sửa: gọi đúng cổng KBS (bỏ `lang=`) cho `ratio()`/`income_statement()`/`cash_flow()` (dữ liệu hiện tại đến 2026-Q2), tự động fallback VCI cho `balance_sheet()` (KBS không hỗ trợ), và trích đúng **cột quý mới nhất** thay vì dòng đầu bảng.

## Giới hạn đã xác minh thực tế (Task 5)

Đã gọi thử trực tiếp `stock.trading.foreign_trade()`, `.prop_trade()`, `.trading_stats()` trên cả nguồn VCI và KBS của `vnstock` 4.0.5 (bản cài trên máy) — **tất cả đều raise `NotImplementedError`**. Đây có vẻ là các hàm "đặt chỗ" trong API, chưa triển khai ở bản miễn phí (có thể mở khi đăng ký gói trả phí "Vnstock Insiders").

Dữ liệu khối ngoại duy nhất lấy được miễn phí là **snapshot tức thời** qua `price_board()` (giá khớp, khối lượng/giá trị mua-bán ròng khối ngoại *tại thời điểm gọi API*). `market_data_fetcher.py` ghi snapshot này vào `FinMind_ForeignFlow_Snapshot.csv` mỗi lần chạy — nếu đưa vào pipeline lịch hàng ngày, theo thời gian sẽ tự dựng thành chuỗi gần-lịch sử (daily snapshot), nhưng **không phải** dữ liệu giao dịch đầy đủ như mô tả gốc.

**Tự doanh (proprietary trading) và giao dịch thỏa thuận lớn (block trade) hiện chưa có nguồn nào trong pipeline này** — cần viết crawler HTML riêng (vd trang thống kê giao dịch của HOSE/CafeF/Vietstock) nếu bắt buộc phải có, hoặc chấp nhận thiếu phần này.

## Upload lên Google Sheets

`upload_all_data.py` (đặt tại gốc thư mục) là script upload **thống nhất** — quét toàn bộ `data_ingestion/**/*.csv` (bỏ qua các thư mục dữ liệu trung gian như `state/`, `raw/`, `duplicates/`, `failed/`) và đẩy lên cùng 1 Google Sheet, mỗi file CSV → 1 tab riêng đặt tên theo đường dẫn + ngày chạy. Tab cũ hơn `RETENTION_DAYS` (mặc định 7 ngày) tự động bị xoá ở lần chạy tiếp theo.

`data_ingestion/news_scraper/upload_to_gsheet.py` (bản gốc của HuynhVu, chỉ quét riêng `FinMind_Data_Lake/`) vẫn còn trong repo nhưng **không còn được gọi trong pipeline chính** — dùng `upload_all_data.py` là đủ, bao trùm cả phần này.

## Lưu ý bảo mật

- File `gsheet_credentials.json` (Google Service Account) là **private key thật**, chỉ đặt **1 bản duy nhất tại gốc thư mục dự án**, không đi kèm trong git (`.gitignore` đã chặn). Xem mục "Hướng dẫn cho thành viên nhóm" phía trên để biết cách lấy file này an toàn.
- **Trước khi push bất kỳ thay đổi nào lên GitHub**, chạy `git status` kiểm tra kỹ không có file `*credentials*.json` nào bị `git add` nhầm — dù đã có `.gitignore`, vẫn nên kiểm tra lại 1 lần cho chắc (repo dự án từng bị GitHub Push Protection chặn vì lỗi này).
- `data_ingestion/brokerage_reports/crawlers/cafef.py` cần Selenium + trình duyệt Chrome cài sẵn trên máy để tải PDF (do link PDF của CafeF ẩn sau nút Blazor).
