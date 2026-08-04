FINMIND DATA INGESTION & AUTOMATED DATA LAKE PIPELINE
Dự án Nghiên cứu Khoa học: Nền tảng AI hỗ trợ tổng hợp và phân tích thông tin chứng khoán đa nguồn bằng Hybrid Graph–Vector RAG

Phân hệ: Thu thập dữ liệu thời gian thực (Real-time Ingestion) & Giám sát Hồ chứa dữ liệu tự động (Watchdog Data Lake)

1. TỔNG QUAN KIẾN TRÚC HỆ THỐNG (HOW IT WORKS)
Hệ thống được thiết kế theo mô hình Đoạn ống dữ liệu tự động (Automated Data Pipeline) phục vụ cho mô hình Ngôn ngữ Lớn (LLM) và Cơ sở dữ liệu Đồ thị (Knowledge Graph). Toàn bộ thư mục MASCOT hoạt động dưới sự phối hợp của 4 script độc lập và 1 thư mục lưu trữ trung tâm:

Plaintext
MASCOT/
 │
 ├─ [Terminal 1: Giám sát 24/7] ──> finmind_file_organizer.py (Watchdog Bot)
 │                                          │
 ├─ [Terminal 2: Cào Dữ liệu]               ▼
 │   ├── CafeFScraper.py          ──> [Thư mục gốc] ──> Tự động phân loại ──> FinMind_Data_Lake/
 │   ├── cafef_bctc_scraper.py    ──> [Thư mục gốc] ──> Tự động phân loại ──> FinMind_Data_Lake/
 │   └── vnstock_data_fetcher.py  ──> [Thư mục gốc] ──> Tự động phân loại ──> FinMind_Data_Lake/
Cơ chế hoạt động: 3 script thu thập (CafeFScraper, cafef_bctc_scraper, vnstock_data_fetcher) đóng vai trò là "Nhân viên đi săn", có nhiệm vụ kết nối API/HTML, làm sạch văn bản và xuất các file .json, .csv ra thư mục gốc. Script finmind_file_organizer.py đóng vai trò là "Quản gia Watchdog", chạy ngầm 24/7 để bắt các file mới xuất ra, đọc tên mã cổ phiếu và tự động chuyển thẳng vào đúng ngăn trong FinMind_Data_Lake.

2. YÊU CẦU HỆ THỐNG & CÀI ĐẶT (PREREQUISITES)
Để chạy mượt mà toàn bộ hệ thống, mở Terminal/PowerShell trong thư mục project và cài đặt các gói thư viện chuẩn theo danh sách sau:

PowerShell
# 1. Cài đặt các thư viện cào dữ liệu và phân tích HTML
pip install requests beautifulsoup4 pandas openpyxl

# 2. Cài đặt thư viện chứng khoán quốc dân (Bắt buộc phải tải bản v4 mới nhất)
pip install -U vnstock
Yêu cầu phiên bản Python: Python 3.10+ (Hệ thống đã kiểm thử ổn định trên Python 3.14).

Lưu ý: Thư viện vnstock phải là phiên bản v4.0.5 trở lên để tránh lỗi 404 Not Found từ các cổng dữ liệu cũ.

3. CHI TIẾT CHỨC NĂNG & HÀM CỦA TỪNG FILE
3.1. vnstock_data_fetcher.py — Thu thập Chỉ số tài chính & BCTC Chuẩn hóa
Script chuyên dụng thu thập dữ liệu cấu trúc (Structured Data) từ API mở của các công ty chứng khoán lớn thông qua thư viện vnstock. Dữ liệu này dùng để cấp số liệu cho Knowledge Graph (Neo4j) và vẽ Biểu đồ Dashboard MVP.

Cơ chế Nguồn đôi (Dual-Source Fallback): Ưu tiên gọi cổng KBS (KB Securities); nếu mạng nghẽn hoặc máy chủ KBS bảo trì, code tự động chuyển ngầm sang cổng VCI (Vietcap) để đảm bảo luồng Airflow không bao giờ bị đứt gãy.

Hàm cốt lõi:

fetch_stock_data_clean(symbol="FPT"): Hàm chính thực hiện 3 nhiệm vụ:

Gọi stock.finance.ratio(): Lấy các chỉ số định giá tài chính mới nhất (P/E, P/B, ROE, ROA, EPS, Biên lợi nhuận gộp/ròng).

Gọi stock.finance.income_statement(): Cào lịch sử Báo cáo kết quả kinh doanh của 8 quý gần nhất (Doanh thu, Lợi nhuận sau thuế).

Đóng gói toàn bộ số liệu thành file chuẩn FinMind_Vnstock_[MÃ_CK].json và lưu ra ổ cứng.

3.2. CafeFScraper.py — Thu thập Tin tức & Bài báo Tài chính
Script thu thập dữ liệu phi cấu trúc (Unstructured Text) từ trang CafeF theo từ khóa hoặc mã cổ phiếu. Dữ liệu này được tối ưu sẵn để đưa vào quy trình cắt nhỏ văn bản (Text Chunking) và tạo Vector Embeddings cho ChromaDB/Milvus.

Các kỹ thuật tích hợp: Xoay vòng User-Agent giả lập trình duyệt, giới hạn tần suất truy vấn (Rate Limiting ngẫu nhiên 1.5s - 3s), và tự động dự phòng bộ chọn DOM (Fallback Selectors).

Các hàm/phương thức cốt lõi (Class CafeFScraper):

_get_headers(): Sinh Header ngẫu nhiên kèm Referer chuẩn từ CafeF để chống bị tường lửa (WAF/Cloudflare) chặn.

_clean_text(text): Hàm tối ưu cho RAG. Tự động loại bỏ hoàn toàn các thẻ quảng cáo, link bài liên quan, script rác và khoảng trắng dư thừa, trả về văn bản sạch 100%.

search_article_links(): Quét các trang kết quả tìm kiếm của CafeF để lấy danh sách URL bài viết mới nhất (quét tối đa 10 trang).

scrape_article_detail(url): Vào sâu từng bài báo, trích xuất cấu trúc gồm: Tiêu đề, Ngày đăng, Sapo (Tóm tắt) và Nội dung chính (Body Text).

run(): Thu thập dữ liệu và tự động sắp xếp lại theo thứ tự thời gian giảm dần, ưu tiên đẩy các bài tin tức, báo cáo mới nhất lên dòng đầu tiên.

export_to_files(filename_prefix): Xuất song song ra 2 định dạng: .json (cho AI Copilot) và .csv chuẩn utf-8-sig (để không bị lỗi font Tiếng Việt khi mở trên Excel).

3.3. cafef_bctc_scraper.py — Thu thập & Tải file Báo Cáo Tài Chính Gốc
Script chuyên sâu để lọc và thu thập riêng các bài công bố Báo cáo tài chính định kỳ, đồng thời quét và tải các file chứng từ gốc (.PDF, .EXCEL, .DOC) về máy phục vụ công tác nhận dạng chữ (OCR bằng pdfplumber).

Bộ lọc từ khóa thông minh: Tự động loại bỏ tin tức rác, chỉ giữ lại các bài viết có chứa từ khóa nghiệp vụ kế toán (bctc, kết quả kinh doanh, lợi nhuận, kiểm toán, thường niên).

Các hàm/phương thức cốt lõi (Class CafeFBCTCScraper):

_detect_report_period(text): Tự động phân tích ngữ nghĩa tiêu đề để gán nhãn siêu dữ liệu (Metadata): Quý 1, Quý 2 (Bán niên), Quý 3, Quý 4 hoặc Thường niên. Giúp AI Copilot lọc đúng tài liệu quý khi người dùng truy vấn.

scrape_report_detail(url): Ngoài việc cào text tóm tắt, hàm này sẽ quét toàn bộ thẻ <a> trong bài để trích xuất danh sách link tải file đính kèm (attached_files).

download_pdf_files(save_dir): Tự động tải toàn bộ các file PDF/Excel báo cáo tài chính gốc tìm được về lưu thẳng vào thư mục máy tính, chuẩn bị sẵn sàng cho luồng xử lý OCR của Airflow.

3.4. finmind_file_organizer.py — Robot Giám sát & Quản lý Data Lake 24/7
Hệ thống Kỹ sư dữ liệu ngầm (Automated Data Lake Watchdog), hoạt động với mức tiêu thụ CPU 0% và RAM ~20MB, có nhiệm vụ dọn dẹp và giữ cho hệ thống lưu trữ luôn ngăn nắp chuẩn khoa học.

Cơ chế vòng lặp cạn (Drain Loop): Khi phát hiện file mới, robot di chuyển xong sẽ kiểm tra lại ngay lập tức, nếu còn file thì xử lý cho đến khi thư mục gốc sạch bong rồi mới quay về trạng thái ngủ (time.sleep).

Các hàm/phương thức cốt lõi (Class FinMindDataOrganizer):

_extract_ticker(filename): Sử dụng Biểu thức chính quy (Regex) để tự động nhận diện Mã Chứng Khoán (FPT, VCI, HPG...) nằm trong tên file. Nếu là dữ liệu chung, tự động gán nhãn GENERAL_MARKET.

_extract_category(filename): Phân loại luồng dữ liệu thành 4 ngăn chuẩn dựa vào tên file:

1_Chi_So_Tai_Chinh_Vnstock

2_Bao_Cao_Tai_Chinh

3_Tin_Tuc_Va_Su_Kien

4_Du_Lieu_Khac

_update_manifest(ticker_dir, ticker, category, filename): Tính năng Audit Logging. Mỗi khi di chuyển 1 file vào folder mã chứng khoán, hàm này tự động viết nhật ký vào file THONG_KE_DU_LIEU.txt, ghi rõ thời gian lưu, phân loại và tên file để Giảng viên/Giám khảo dễ dàng kiểm tra.

scan_and_organize(): Quét toàn bộ thư mục, lọc đuôi file hợp lệ (.json, .csv, .pdf, .xlsx), tạo cây thư mục và di chuyển file (shutil.move).

run_forever(check_interval=5): Kích hoạt chế độ giám sát liên tục 24/7 theo chu kỳ nghỉ 5 giây.

4. HƯỚNG DẪN THỰC THI (STEP-BY-STEP GUIDE)
Để trải nghiệm toàn bộ quy trình tự động hóa của hệ thống FinMind, hãy thực hiện theo đúng thứ tự 3 bước sau:

Bước 1: Kích hoạt Robot Giám sát (Terminal 1)
Mở cửa sổ Terminal/PowerShell đầu tiên tại thư mục MASCOT và chạy lệnh sau để bật Robot Watchdog:

PowerShell
python finmind_file_organizer.py
Giao diện sẽ hiển thị khung thông báo FINMIND WATCHDOG và đứng chờ dữ liệu.

Bước 2: Chạy các Script Cào Dữ liệu (Terminal 2)
Mở thêm một dấu nhắc lệnh Terminal thứ hai (bấm nút + trong VS Code), và chạy lần lượt hoặc đồng thời các script cào dữ liệu theo nhu cầu:

PowerShell
# 1. Tải chỉ số định giá & BCTC 8 quý của FPT (từ cổng KBS/VCI)
python vnstock_data_fetcher.py

# 2. Tải tin tức & bài báo tài chính mới nhất từ CafeF
python CafeFScraper.py

# 3. Tải các bản công bố Báo cáo tài chính & quét link PDF gốc
python cafef_bctc_scraper.py
Bước 3: Kiểm tra kết quả tại Data Lake
Ngay khi Terminal 2 báo [v] Đã xuất file thành công, hãy quan sát Terminal 1: Robot Watchdog sẽ lập tức chớp nháy, phát hiện file mới và tự động gắp vào thư mục FinMind_Data_Lake.

Cấu trúc hồ sơ dữ liệu đầu ra sẽ tự động được tổ chức tuyệt đối ngăn nắp như sau:

Plaintext
FinMind_Data_Lake/
 └── FPT/
      ├── THONG_KE_DU_LIEU.txt                 <-- Sổ nhật ký thống kê tự động
      ├── 1_Chi_So_Tai_Chinh_Vnstock/
      │    └── FinMind_Vnstock_FPT.json        <-- Số liệu JSON cho AI Copilot & Biểu đồ
      ├── 2_Bao_Cao_Tai_Chinh/
      │    ├── Data_BCTC_FPT.csv
      │    └── Data_BCTC_FPT.json
      └── 3_Tin_Tuc_Va_Su_Kien/
           ├── FinMind_Data_báo cáo tài chính chứng khoán.csv
           └── FinMind_Data_báo cáo tài chính chứng khoán.json
(Mở file THONG_KE_DU_LIEU.txt bên trong folder FPT/ để xem lịch sử thời gian từng file được thu thập vào hệ thống).