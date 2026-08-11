import json
import sys
import warnings

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from vnstock import Vnstock

warnings.filterwarnings("ignore")

# =====================================================================
# TASK 4 - BÁO CÁO TÀI CHÍNH QUÝ & CHỈ SỐ ĐỊNH GIÁ
#
# Lấy đủ 3 báo cáo tài chính chuẩn VAS (Cân đối kế toán, Kết quả kinh
# doanh, Lưu chuyển tiền tệ) theo quý + bộ chỉ số định giá (P/E, P/B,
# ROE, ROA, EPS...).
#
# Ghi chú quan trọng (rút ra từ việc điều tra API thực tế của vnstock 4.0.5):
#   - stock.finance.ratio(): cổng KBS trả về đúng nhất (P/E, P/B, ROE...
#     theo quý gần nhất), NHƯNG không được truyền kwarg lang= (KBS sẽ
#     raise TypeError). Cổng VCI thì nhận lang= nhưng dữ liệu ratio lại
#     bị "đứng" ở 2018 (không rõ do giới hạn dữ liệu miễn phí hay bug
#     của nguồn) -> ưu tiên KBS cho riêng hàm ratio().
#   - stock.finance.balance_sheet(): cổng KBS không hỗ trợ (trả về bảng
#     rỗng), phải luôn lấy từ VCI.
#   - stock.finance.income_statement() và cash_flow(): cả KBS và VCI đều
#     trả dữ liệu quý hiện tại bình thường.
#   - Bảng trả về từ vnstock có dạng "wide": mỗi DÒNG là 1 chỉ số
#     (item/item_id), mỗi CỘT là 1 quý (vd "2026-Q2"). Lấy "chỉ số mới
#     nhất" nghĩa là lấy giá trị ở CỘT quý mới nhất cho từng dòng — TUYỆT
#     ĐỐI không dùng ratios_df.iloc[0] (đó là lấy DÒNG đầu tiên, tức 1
#     chỉ số bất kỳ ở mọi quý, không phải điều ta cần).
# =====================================================================


def _latest_quarter_column(df):
    """Tìm cột quý mới nhất trong bảng "wide" (item x quý) của vnstock.

    Cột hợp lệ có dạng "YYYY-Qn" (vd "2026-Q2"); vnstock đôi khi trả về
    thêm cột trùng tên với hậu tố "_1" (vd "2025-Q4_1") do dữ liệu nguồn
    trùng lặp - cột này bị loại khi so sánh "mới nhất".
    """
    quarter_cols = []
    for col in df.columns:
        base = col.split("_")[0]
        if len(base) == 7 and base[4] == "-" and base[5] == "Q":
            try:
                year, q = int(base[:4]), int(base[6])
                quarter_cols.append((year, q, col))
            except ValueError:
                continue
    if not quarter_cols:
        return None
    quarter_cols.sort(key=lambda x: (x[0], x[1]))
    return quarter_cols[-1][2]


def _statement_to_latest_dict(df, extra_quarters=4):
    """Chuyển bảng "wide" (item x quý) thành dict {item: giá trị quý mới
    nhất}, kèm lịch sử `extra_quarters` quý gần nhất dạng list để tiện so
    sánh tăng trưởng liền kề.
    """
    if df is None or df.empty:
        return {}, []

    latest_col = _latest_quarter_column(df)
    if latest_col is None:
        return {}, []

    quarter_cols = []
    for col in df.columns:
        base = col.split("_")[0]
        if len(base) == 7 and base[4] == "-" and base[5] == "Q":
            year, q = int(base[:4]), int(base[6])
            quarter_cols.append((year, q, col))
    quarter_cols.sort(key=lambda x: (x[0], x[1]), reverse=True)
    recent_cols = [c for _, _, c in quarter_cols[:extra_quarters]]

    item_col = "item" if "item" in df.columns else df.columns[0]
    id_col = "item_id" if "item_id" in df.columns else None

    latest = {}
    history = []
    for _, row in df.iterrows():
        key = row.get(id_col) if id_col else row[item_col]
        if not isinstance(key, str) or not key:
            key = row[item_col]
        latest[key] = row.get(latest_col)

    for col in recent_cols:
        quarter_snapshot = {"quarter": col}
        for _, row in df.iterrows():
            key = row.get(id_col) if id_col else row[item_col]
            if not isinstance(key, str) or not key:
                key = row[item_col]
            quarter_snapshot[key] = row.get(col)
        history.append(quarter_snapshot)

    return latest, history


def _fetch_with_fallback(symbol, fetch_kbs, fetch_vci, label):
    """Thử KBS trước (nhanh, chi tiết), fallback sang VCI nếu KBS lỗi
    hoặc trả bảng rỗng."""
    try:
        df = fetch_kbs()
        if df is not None and not df.empty:
            return df, "KBS"
    except Exception as e:
        print(f"   [-] {label}: cổng KBS lỗi ({e}), thử VCI...")

    try:
        df = fetch_vci()
        if df is not None and not df.empty:
            return df, "VCI"
    except Exception as e:
        print(f"   [!] {label}: cổng VCI cũng lỗi ({e})")

    return None, None


def fetch_stock_data_clean(symbol="FPT"):
    print(f"[*] Đang tải dữ liệu tài chính chuyên sâu cho {symbol} bằng vnstock 4.0.5...")

    stock_kbs = Vnstock().stock(symbol=symbol, source="KBS")
    stock_vci = Vnstock().stock(symbol=symbol, source="VCI")

    # 1. Chỉ số định giá (P/E, P/B, ROE, ROA, EPS...) - ưu tiên KBS,
    #    KHÔNG truyền lang= cho KBS (gây TypeError).
    print("   -> Đang lấy chỉ số định giá (ratio)...")
    ratio_df, ratio_source = _fetch_with_fallback(
        symbol,
        lambda: stock_kbs.finance.ratio(period="quarter"),
        lambda: stock_vci.finance.ratio(period="quarter", lang="vi"),
        "ratio",
    )
    latest_ratios, ratio_history = _statement_to_latest_dict(ratio_df)
    print(f"      + Nguồn: {ratio_source or 'KHÔNG LẤY ĐƯỢC'} | {len(latest_ratios)} chỉ số")

    # 2. Kết quả kinh doanh (Income Statement) - 8 quý gần nhất
    print("   -> Đang lấy Kết quả kinh doanh (income statement)...")
    income_df, income_source = _fetch_with_fallback(
        symbol,
        lambda: stock_kbs.finance.income_statement(period="quarter"),
        lambda: stock_vci.finance.income_statement(period="quarter", lang="vi"),
        "income_statement",
    )
    latest_income, income_history = _statement_to_latest_dict(income_df, extra_quarters=8)
    print(f"      + Nguồn: {income_source or 'KHÔNG LẤY ĐƯỢC'} | {len(income_history)} quý lịch sử")

    # 3. Cân đối kế toán (Balance Sheet) - KBS không hỗ trợ, luôn lấy VCI
    print("   -> Đang lấy Cân đối kế toán (balance sheet, chỉ có ở VCI)...")
    balance_df, balance_source = _fetch_with_fallback(
        symbol,
        lambda: (_ for _ in ()).throw(RuntimeError("KBS khong ho tro balance_sheet")),
        lambda: stock_vci.finance.balance_sheet(period="quarter", lang="vi"),
        "balance_sheet",
    )
    latest_balance, balance_history = _statement_to_latest_dict(balance_df, extra_quarters=8)
    print(f"      + Nguồn: {balance_source or 'KHÔNG LẤY ĐƯỢC'} | {len(balance_history)} quý lịch sử")

    # 4. Lưu chuyển tiền tệ (Cash Flow) - 8 quý gần nhất
    print("   -> Đang lấy Lưu chuyển tiền tệ (cash flow)...")
    cashflow_df, cashflow_source = _fetch_with_fallback(
        symbol,
        lambda: stock_kbs.finance.cash_flow(period="quarter"),
        lambda: stock_vci.finance.cash_flow(period="quarter", lang="vi"),
        "cash_flow",
    )
    latest_cashflow, cashflow_history = _statement_to_latest_dict(cashflow_df, extra_quarters=8)
    print(f"      + Nguồn: {cashflow_source or 'KHÔNG LẤY ĐƯỢC'} | {len(cashflow_history)} quý lịch sử")

    output_data = {
        "symbol": symbol,
        "fundamental_ratios": {
            "source": ratio_source,
            "latest": latest_ratios,
            "quarterly_history": ratio_history,
        },
        "income_statement": {
            "source": income_source,
            "latest": latest_income,
            "quarterly_history": income_history,
        },
        "balance_sheet": {
            "source": balance_source,
            "latest": latest_balance,
            "quarterly_history": balance_history,
        },
        "cash_flow": {
            "source": cashflow_source,
            "latest": latest_cashflow,
            "quarterly_history": cashflow_history,
        },
        # Giữ tương thích ngược với pipeline cũ (finmind_file_organizer,
        # upload_to_gsheet) từng đọc "quarterly_performance" của income
        # statement trực tiếp.
        "quarterly_performance": income_history,
    }

    file_name = f"FinMind_Vnstock_{symbol}.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4, default=str)
    print(f"[v] Đã xuất file JSON thành công: {file_name}\n")


if __name__ == "__main__":
    fetch_stock_data_clean("FPT")
