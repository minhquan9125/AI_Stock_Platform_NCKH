import pandas as pd
from vnstock import Vnstock

# ==========================================
# Hàm lấy dữ liệu với cơ chế Fallback
# ==========================================

def fetch_market_data(symbol, start_date, end_date):

    sources = [
        "VCI",
        "TCBS",
        "DNSE"
    ]

    for source in sources:

        try:

            print(f"\nĐang kết nối nguồn {source}...")

            stock = Vnstock().stock(
                symbol=symbol,
                source=source
            )

            df = stock.quote.history(
                start=start_date,
                end=end_date,
                interval="1D"
            )

            if not df.empty:

                print(f"Thành công từ nguồn {source}")

                return df

        except Exception as e:

            print(f"Lỗi nguồn {source}")

            print(e)

    return pd.DataFrame()


# ==========================================
# Hàm test
# ==========================================

def main():

    ticker = "VCB"

    start_date = "2026-01-01"

    end_date = "2026-07-01"

    df = fetch_market_data(
        ticker,
        start_date,
        end_date
    )

    if df.empty:

        print("Không lấy được dữ liệu")

        return

    print("\n==========================")

    print("5 dòng đầu")

    print(df.head())

    print("\n==========================")

    print("Tên các cột")

    print(df.columns)

    print("\n==========================")

    print("Thông tin DataFrame")

    print(df.info())

    print("\n==========================")

    print("Thống kê")

    print(df.describe())

    filename = f"{ticker}_market_data.csv"

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"\nĐã lưu file {filename}")


if __name__ == "__main__":

    main()