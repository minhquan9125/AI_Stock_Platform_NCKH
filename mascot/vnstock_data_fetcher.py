import json
import sys
import warnings

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Sử dụng vnstock v4.0.5 mới nhất
from vnstock import Vnstock

# Tắt các cảnh báo nhắc nhở (Deprecation Warning) để terminal sạch đẹp khi demo NCKH
warnings.filterwarnings("ignore")


def fetch_stock_data_clean(symbol="FPT"):
    print(
        f"[*] Đang tải dữ liệu tài chính chuyên sâu cho {symbol} bằng vnstock v4.0.5..."
    )

    try:
        # Trong vnstock v4.0.5, các cổng hỗ trợ chính thức là: KBS, VCI, MSN, FMP
        # Ưu tiên số 1: KBS (Chứng khoán KB Việt Nam - tốc độ cao, cực kỳ chi tiết)
        print("   -> Đang kết nối vào cổng dữ liệu KBS (KB Securities)...")
        stock = Vnstock().stock(symbol=symbol, source="KBS")

        # 1. Lấy chỉ số tài chính cơ bản (P/E, P/B, ROE, ROA, EPS...)
        ratios_df = stock.finance.ratio(period="quarter", lang="vi")
        latest_ratios = (
            ratios_df.iloc[0].to_dict() if not ratios_df.empty else {}
        )

        # 2. Lấy Báo cáo kết quả kinh doanh 8 quý gần nhất
        income_df = stock.finance.income_statement(period="quarter", lang="vi")
        quarterly_reports = (
            income_df.head(8).to_dict(orient="records")
            if not income_df.empty
            else []
        )

        print(
            f"   + [Thành công] Đã lấy được chỉ số định giá và {len(quarterly_reports)} quý kinh doanh từ cổng KBS!"
        )

    except Exception as e_kbs:
        print(f"   [-] Cổng KBS gặp sự cố: {e_kbs}")
        print(
            "   -> [Fallback] Đang tự động chuyển sang cổng dự phòng Vietcap (VCI)..."
        )

        # Fallback sang cổng VCI (đã được fix hoàn toàn lỗi 404 trong bản v4.0.5)
        stock_vci = Vnstock().stock(symbol=symbol, source="VCI")
        ratios_df = stock_vci.finance.ratio(period="quarter", lang="vi")
        latest_ratios = (
            ratios_df.iloc[0].to_dict() if not ratios_df.empty else {}
        )

        income_df = stock_vci.finance.income_statement(
            period="quarter", lang="vi"
        )
        quarterly_reports = (
            income_df.head(8).to_dict(orient="records")
            if not income_df.empty
            else []
        )
        print(
            f"   + [Thành công] Đã tải xong dữ liệu {symbol} từ cổng VCI!"
        )

    # 3. Xuất ra file JSON chuẩn RAG
    output_data = {
        "symbol": symbol,
        "fundamental_ratios": latest_ratios,
        "quarterly_performance": quarterly_reports,
    }

    file_name = f"FinMind_Vnstock_{symbol}.json"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"[v] Đã xuất file JSON thành công: {file_name}\n")


if __name__ == "__main__":
    fetch_stock_data_clean("FPT")