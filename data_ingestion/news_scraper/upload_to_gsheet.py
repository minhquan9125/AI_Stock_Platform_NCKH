import csv
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# =====================================================================
# ĐẨY DỮ LIỆU FinMind_Data_Lake LÊN GOOGLE SHEETS
#
# Yêu cầu chuẩn bị trước (chỉ làm 1 lần):
#   1. File credentials Service Account (JSON) đặt tại CREDENTIALS_FILE
#   2. Google Sheet đích đã được Share quyền Editor cho email
#      "client_email" bên trong file JSON đó
#   3. Điền SPREADSHEET_ID (lấy từ URL của Google Sheet, đoạn giữa
#      /d/ và /edit)
# =====================================================================

CREDENTIALS_FILE = "gsheet_credentials.json"
SPREADSHEET_ID = "1fLkYaPjLqfwrfWzDfrtyX_GqZJofCTsXxuw3O-EbrcY"
DATA_LAKE_DIR = Path("./FinMind_Data_Lake")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Giới hạn số ký tự/ô để tránh vượt trần 50.000 ký tự/ô của Google Sheets
# (các cột full_content/content dạng văn bản dài có thể vượt trần này).
MAX_CELL_CHARS = 49000

# Mỗi ngày cào dữ liệu -> 1 tab riêng (tên tab gắn hậu tố ngày). Tab của
# những ngày quá RETENTION_DAYS ngày trước sẽ tự động bị xóa khi chạy
# script (không xóa các tab khác không theo quy ước đặt tên này).
RETENTION_DAYS = 7
DATE_SUFFIX_RE = re.compile(r"_(\d{4}-\d{2}-\d{2})$")

# Tên cột (không phân biệt hoa/thường) bị loại khi so trùng dòng, vì các
# cột này đổi giá trị mỗi lần cào dù nội dung thực chất không đổi -> nếu
# tính cả vào sẽ khiến dòng cũ/mới luôn bị coi là khác nhau.
TIMESTAMP_COL_HINTS = ("scraped_at", "generated_at", "fetched_at", "created_at")


def _row_signature(header, row):
    """Chữ ký để so trùng 1 dòng dữ liệu, bỏ qua các cột timestamp."""
    return tuple(
        val
        for col, val in zip(header, row)
        if not any(hint in col.lower() for hint in TIMESTAMP_COL_HINTS)
    )


def _connect():
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Không tìm thấy '{CREDENTIALS_FILE}'. Hãy làm theo hướng dẫn "
            "tạo Service Account trước khi chạy script này."
        )
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _safe_sheet_title(csv_path, date_str):
    """Google Sheets giới hạn tên tab tối đa 100 ký tự và không được
    trùng nhau -> dùng đường dẫn tương đối rút gọn + hậu tố ngày làm tên
    tab (mỗi ngày cào dữ liệu ra 1 tab riêng)."""
    rel = csv_path.relative_to(DATA_LAKE_DIR)
    base = "_".join(rel.with_suffix("").parts)
    suffix = f"_{date_str}"
    base = base[: 100 - len(suffix)]
    return f"{base}{suffix}"


def _read_csv_rows(csv_path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    # Cắt bớt các ô quá dài để không lỗi khi ghi lên Sheets
    return [
        [cell[:MAX_CELL_CHARS] if len(cell) > MAX_CELL_CHARS else cell for cell in row]
        for row in rows
    ]


def _cleanup_old_tabs(spreadsheet):
    """Xóa các tab có hậu tố ngày (đúng định dạng do script này tạo ra)
    đã cũ hơn RETENTION_DAYS ngày. KHÔNG đụng tới tab nào không theo quy
    ước đặt tên _YYYY-MM-DD (vd tab người dùng tự thêm tay)."""
    cutoff = datetime.now().date() - timedelta(days=RETENTION_DAYS - 1)
    deleted = 0

    for ws in spreadsheet.worksheets():
        match = DATE_SUFFIX_RE.search(ws.title)
        if not match:
            continue
        try:
            tab_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue

        if tab_date < cutoff:
            spreadsheet.del_worksheet(ws)
            print(f"[x] Đã xóa tab quá hạn ({RETENTION_DAYS} ngày): '{ws.title}'")
            deleted += 1
            time.sleep(1.0)

    if deleted == 0:
        print("[*] Không có tab nào quá hạn cần xóa.")
    return deleted


def upload_all_csv():
    if not SPREADSHEET_ID:
        print(
            "[!] Chưa điền SPREADSHEET_ID trong script. Mở file "
            "upload_to_gsheet.py, dán ID Google Sheet vào biến "
            "SPREADSHEET_ID rồi chạy lại."
        )
        return

    print("[*] Đang xác thực với Google Sheets API...")
    gc = _connect()
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)
    print(f"[+] Đã kết nối tới Google Sheet: {spreadsheet.title}\n")

    csv_files = sorted(DATA_LAKE_DIR.rglob("*.csv"))
    if not csv_files:
        print(f"[!] Không tìm thấy file .csv nào trong {DATA_LAKE_DIR}/")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")

    for csv_path in csv_files:
        title = _safe_sheet_title(csv_path, today_str)
        rows = _read_csv_rows(csv_path)
        if not rows:
            print(f"[-] Bỏ qua (rỗng): {csv_path}")
            continue

        header, data_rows = rows[0], rows[1:]
        n_cols = max(len(r) for r in rows)

        try:
            ws = spreadsheet.worksheet(title)
            existing_values = ws.get_all_values()

            if not existing_values:
                # Tab đã tồn tại nhưng đang trống -> ghi từ đầu như bình thường
                ws.update(values=rows, range_name="A1")
                print(f"[v] Tab '{title}' đang trống -> ghi {len(data_rows)} dòng.")
            else:
                existing_header = existing_values[0]
                existing_sigs = {
                    _row_signature(existing_header, r) for r in existing_values[1:]
                }
                new_rows = [
                    r for r in data_rows
                    if _row_signature(header, r) not in existing_sigs
                ]
                if new_rows:
                    ws.append_rows(new_rows, value_input_option="RAW")
                    print(
                        f"[v] Tab '{title}' đã có sẵn -> bổ sung {len(new_rows)} "
                        f"dòng mới (bỏ qua {len(data_rows) - len(new_rows)} dòng trùng)."
                    )
                else:
                    print(f"[=] Tab '{title}' đã có đủ, không có dòng mới nào.")

        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(
                title=title, rows=len(rows) + 10, cols=n_cols + 2
            )
            ws.update(values=rows, range_name="A1")
            print(f"[v] Tạo tab mới '{title}': {len(data_rows)} dòng x {n_cols} cột "
                  f"(nguồn: {csv_path})")

        time.sleep(1.2)  # Tránh chạm rate limit ghi của Google Sheets API

    print()
    _cleanup_old_tabs(spreadsheet)

    print(f"\n[+] Hoàn tất! Đã đồng bộ {len(csv_files)} file CSV lên Google Sheets "
          f"(tab ngày {today_str}, giữ lại {RETENTION_DAYS} ngày gần nhất).")
    print(f"    Link: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")


if __name__ == "__main__":
    upload_all_csv()
