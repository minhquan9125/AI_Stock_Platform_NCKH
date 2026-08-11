import csv
import os
import sys
from datetime import datetime

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from vnstock import Vnstock

# =====================================================================
# TASK 5 - DỮ LIỆU GIÁ THỊ TRƯỜNG & DẤU VẾT DÒNG TIỀN
#
# Phần 1 (đầy đủ, ổn định): Lịch sử giá OHLCV — kế thừa nguyên logic
# fallback đa nguồn của Quan (data_ingestion/structured_data/test_market_data.py).
#
# Phần 2 (giới hạn — đọc kỹ trước khi dùng): "Dấu vết dòng tiền" theo
# đúng mô tả nhiệm vụ (khối ngoại mua/bán ròng, tự doanh, thỏa thuận
# lớn/block trade) ĐÃ ĐƯỢC KIỂM TRA TRỰC TIẾP với vnstock 4.0.5 hiện có:
#
#   - stock.trading.foreign_trade() / .prop_trade() / .trading_stats():
#     tồn tại trên API nhưng khi gọi thực tế đều raise NotImplementedError
#     (cả nguồn VCI lẫn KBS) — có vẻ các hàm này chỉ là API "đặt chỗ" cho
#     tương lai, hoặc chỉ mở khi đăng ký gói "Vnstock Insiders".
#   - Dữ liệu khối ngoại DUY NHẤT hiện lấy được qua vnstock miễn phí là
#     snapshot TỨC THỜI trong stock.trading.price_board() — 4 cột
#     foreign_buy_volume/foreign_sell_volume/foreign_buy_value/
#     foreign_sell_value tại thời điểm gọi API, KHÔNG PHẢI chuỗi thời
#     gian lịch sử.
#   - Giao dịch thỏa thuận lớn (block trade) và chi tiết tự doanh công
#     ty chứng khoán KHÔNG có endpoint nào tương ứng trong vnstock 4.0.5
#     (miễn phí) tại thời điểm viết file này.
#
# => Giải pháp thực tế: hàm fetch_foreign_flow_snapshot() dưới đây LẤY
#    SNAPSHOT khối ngoại mỗi lần chạy và APPEND vào 1 file CSV tích lũy.
#    Nếu chạy hàng ngày qua pipeline lịch (giống news_scraper), theo
#    thời gian sẽ tự dựng thành 1 chuỗi lịch sử gần đúng (daily
#    snapshot, không phải full lịch sử giao dịch). Block trade / tự
#    doanh vẫn còn thiếu — cần nguồn dữ liệu khác (vd cafef/vietstock có
#    trang riêng, phải viết crawler HTML mới) nếu bắt buộc phải có.
# =====================================================================


def fetch_market_data(symbol, start_date, end_date):
    """Lấy lịch sử giá OHLCV với cơ chế fallback qua nhiều nguồn."""
    sources = ["VCI", "TCBS", "DNSE"]

    for source in sources:
        try:
            print(f"\nĐang kết nối nguồn {source}...")
            stock = Vnstock().stock(symbol=symbol, source=source)
            df = stock.quote.history(start=start_date, end=end_date, interval="1D")
            if not df.empty:
                print(f"Thành công từ nguồn {source}")
                return df
        except Exception as e:
            print(f"Lỗi nguồn {source}")
            print(e)

    return pd.DataFrame()


def fetch_foreign_flow_snapshot(symbol):
    """Lấy snapshot khối ngoại mua/bán ròng TỨC THỜI (không phải lịch
    sử) từ price_board. Trả về dict 1 dòng để append vào file tích lũy.
    """
    try:
        stock = Vnstock().stock(symbol=symbol, source="VCI")
        board = stock.trading.price_board([symbol])
    except Exception as e:
        print(f"[!] Không lấy được price_board cho {symbol}: {e}")
        return None

    if board.empty:
        return None

    row = board.iloc[0]

    def _get(col):
        try:
            return row[("match", col)]
        except Exception:
            return None

    return {
        "symbol": symbol,
        "snapshot_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "match_price": _get("match_price"),
        "foreign_buy_volume": _get("foreign_buy_volume"),
        "foreign_sell_volume": _get("foreign_sell_volume"),
        "foreign_buy_value": _get("foreign_buy_value"),
        "foreign_sell_value": _get("foreign_sell_value"),
        "foreign_net_volume": (
            (_get("foreign_buy_volume") or 0) - (_get("foreign_sell_volume") or 0)
        ),
    }


def append_foreign_flow_snapshot(symbol, filename="FinMind_ForeignFlow_Snapshot.csv"):
    """Append 1 dòng snapshot khối ngoại vào file CSV tích lũy (chạy
    hàng ngày sẽ tự dựng thành chuỗi gần-lịch sử theo ngày)."""
    row = fetch_foreign_flow_snapshot(symbol)
    if row is None:
        print(f"[!] Bỏ qua {symbol}: không lấy được snapshot khối ngoại.")
        return

    file_exists = os.path.exists(filename)
    with open(filename, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"[v] Đã ghi snapshot khối ngoại {symbol} vào {filename}")


def main():
    tickers = ["FPT", "VCB", "HPG"]
    start_date = "2020-01-01"
    end_date = datetime.now().strftime("%Y-%m-%d")

    for ticker in tickers:
        df = fetch_market_data(ticker, start_date, end_date)

        if df.empty:
            print(f"Không lấy được dữ liệu OHLCV cho {ticker}")
        else:
            filename = f"FinMind_Market_OHLCV_{ticker}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"Đã lưu {len(df)} dòng OHLCV vào {filename}")

        append_foreign_flow_snapshot(ticker)

    print(
        "\n[LƯU Ý] File FinMind_ForeignFlow_Snapshot.csv chỉ chứa snapshot "
        "tức thời mỗi lần chạy (không phải lịch sử đầy đủ). Dữ liệu block "
        "trade / tự doanh hiện KHÔNG có sẵn qua vnstock miễn phí — xem "
        "docstring đầu file để biết chi tiết."
    )


if __name__ == "__main__":
    main()
