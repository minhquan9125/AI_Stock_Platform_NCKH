"""
FINMIND MACRO & COMMODITY DATA SCRAPER
========================================
Task 6: Dữ liệu Kinh tế Vĩ mô & Giá Hàng hóa (Macroeconomic & Commodity Data)

Nguồn dữ liệu uy tín:
    1. World Bank Open Data API (api.worldbank.org) — GDP, CPI, Lãi suất, Tỷ giá VN
    2. Yahoo Finance (yfinance) — Giá dầu Brent, Vàng, Thép HRC, Quặng sắt, Cao su, Cước vận tải biển

Đầu ra:
    - FinMind_Macro_Vietnam_GENERAL_MARKET.json / .csv  (Vĩ mô Việt Nam)
    - FinMind_Commodity_Global_GENERAL_MARKET.json / .csv (Giá hàng hóa thế giới)

Lưu ý:
    - File được đặt tên chứa "GENERAL_MARKET" để Watchdog (finmind_file_organizer.py)
      tự động phân loại vào thư mục FinMind_Data_Lake/GENERAL_MARKET/4_Du_Lieu_Khac/
    - Prefix "FinMind_Macro" / "FinMind_Commodity" giúp Watchdog nhận diện đúng luồng.
"""

import csv
import json
import os
import sys
import time
import random
from datetime import datetime

import requests

# Ép stdout dùng UTF-8: tránh UnicodeEncodeError khi in tiếng Việt có dấu
# trên terminal Windows mặc định dùng codepage cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# =====================================================================
# PHẦN 1: THU THẬP DỮ LIỆU KINH TẾ VĨ MÔ VIỆT NAM (WORLD BANK API)
# =====================================================================

# Bảng ánh xạ: Mã chỉ số World Bank -> Tên tiếng Việt & mô tả
WORLD_BANK_INDICATORS = {
    # Tăng trưởng GDP (% hàng năm)
    "NY.GDP.MKTP.KD.ZG": {
        "name_vi": "Tăng trưởng GDP",
        "name_en": "GDP Growth (annual %)",
        "unit": "%",
    },
    # GDP giá trị tuyệt đối (USD hiện hành)
    "NY.GDP.MKTP.CD": {
        "name_vi": "GDP (USD)",
        "name_en": "GDP (current US$)",
        "unit": "USD",
    },
    # Lạm phát CPI (% hàng năm)
    "FP.CPI.TOTL.ZG": {
        "name_vi": "Chỉ số CPI (Lạm phát)",
        "name_en": "Inflation, consumer prices (annual %)",
        "unit": "%",
    },
    # Lãi suất cho vay thực tế
    "FR.INR.LEND": {
        "name_vi": "Lãi suất cho vay",
        "name_en": "Lending interest rate (%)",
        "unit": "%",
    },
    # Lãi suất tiền gửi
    "FR.INR.DPST": {
        "name_vi": "Lãi suất tiền gửi",
        "name_en": "Deposit interest rate (%)",
        "unit": "%",
    },
    # Tỷ giá hối đoái chính thức (LCU/USD, tức VND/USD)
    "PA.NUS.FCRF": {
        "name_vi": "Tỷ giá USD/VND (bình quân năm)",
        "name_en": "Official exchange rate (LCU per US$, period average)",
        "unit": "VND/USD",
    },
    # Tín dụng nội địa cho khu vực tư nhân (% GDP)
    "FD.AST.PRVT.GD.ZS": {
        "name_vi": "Tín dụng khu vực tư nhân (% GDP)",
        "name_en": "Domestic credit to private sector (% of GDP)",
        "unit": "% GDP",
    },
    # Tín dụng nội địa cung cấp bởi hệ thống ngân hàng (% GDP)
    "FS.AST.DOMS.GD.ZS": {
        "name_vi": "Tín dụng nội địa ngân hàng (% GDP)",
        "name_en": "Domestic credit provided by financial sector (% of GDP)",
        "unit": "% GDP",
    },
    # Dự trữ ngoại hối (bao gồm vàng, USD hiện hành)
    "FI.RES.TOTL.CD": {
        "name_vi": "Dự trữ ngoại hối (bao gồm vàng)",
        "name_en": "Total reserves (includes gold, current US$)",
        "unit": "USD",
    },
    # Cán cân thương mại hàng hóa và dịch vụ (% GDP)
    "NE.RSB.GNFS.ZS": {
        "name_vi": "Cán cân thương mại (% GDP)",
        "name_en": "External balance on goods and services (% of GDP)",
        "unit": "% GDP",
    },
    # FDI ròng chảy vào (% GDP)
    "BX.KLT.DINV.WD.GD.ZS": {
        "name_vi": "Vốn FDI ròng chảy vào (% GDP)",
        "name_en": "Foreign direct investment, net inflows (% of GDP)",
        "unit": "% GDP",
    },
}

# Phạm vi năm cào dữ liệu vĩ mô
MACRO_START_YEAR = 2000
MACRO_END_YEAR = 2025
COUNTRY_CODE = "VN"  # Mã ISO quốc gia Việt Nam


def fetch_world_bank_indicator(indicator_code, country="VN", start_year=2000, end_year=2025):
    """
    Gọi World Bank Open Data API để lấy chuỗi thời gian của 1 chỉ số kinh tế.
    
    API Endpoint: https://api.worldbank.org/v2/country/{country}/indicator/{indicator}
    Tham số: date={start}:{end}, format=json, per_page=500
    
    Returns: list[dict] với mỗi phần tử gồm { year, value }
    """
    url = (
        f"https://api.worldbank.org/v2/country/{country}"
        f"/indicator/{indicator_code}"
        f"?date={start_year}:{end_year}&format=json&per_page=500"
    )

    try:
        response = requests.get(url, timeout=15)
        if response.status_code != 200:
            print(f"   [!] Lỗi HTTP {response.status_code} khi gọi World Bank API cho {indicator_code}")
            return []

        data = response.json()

        # World Bank API trả về: [metadata_page, [data_records]]
        if not data or len(data) < 2 or not data[1]:
            print(f"   [-] Không có dữ liệu World Bank cho chỉ số {indicator_code}")
            return []

        records = []
        for entry in data[1]:
            year = entry.get("date")
            value = entry.get("value")
            if value is not None:
                records.append({
                    "year": int(year),
                    "value": round(value, 4) if isinstance(value, float) else value,
                })

        # Sắp xếp theo năm tăng dần (World Bank trả về giảm dần)
        records.sort(key=lambda x: x["year"])
        return records

    except Exception as e:
        print(f"   [!] Ngoại lệ khi gọi World Bank API ({indicator_code}): {e}")
        return []


def collect_vietnam_macro_data():
    """
    Thu thập toàn bộ chỉ số kinh tế vĩ mô Việt Nam từ World Bank API.
    
    Trả về cấu trúc dữ liệu gồm:
        - metadata: Thông tin nguồn, thời gian cào
        - indicators: Dict các chỉ số, mỗi chỉ số có info + time_series
    """
    print("=" * 65)
    print("  📊 PHẦN 1: THU THẬP DỮ LIỆU KINH TẾ VĨ MÔ VIỆT NAM")
    print(f"  Nguồn: World Bank Open Data API (api.worldbank.org)")
    print(f"  Phạm vi: {MACRO_START_YEAR} - {MACRO_END_YEAR}")
    print("=" * 65)

    all_indicators = {}
    total = len(WORLD_BANK_INDICATORS)

    for idx, (code, info) in enumerate(WORLD_BANK_INDICATORS.items(), 1):
        print(f"\n[{idx}/{total}] Đang tải: {info['name_vi']} ({info['name_en']})...")

        time_series = fetch_world_bank_indicator(
            indicator_code=code,
            country=COUNTRY_CODE,
            start_year=MACRO_START_YEAR,
            end_year=MACRO_END_YEAR,
        )

        if time_series:
            print(f"   + Thành công: {len(time_series)} năm dữ liệu ({time_series[0]['year']}-{time_series[-1]['year']})")
        else:
            print(f"   - Không có dữ liệu.")

        all_indicators[code] = {
            "indicator_code": code,
            "name_vi": info["name_vi"],
            "name_en": info["name_en"],
            "unit": info["unit"],
            "country": "Vietnam",
            "country_code": COUNTRY_CODE,
            "data_points": len(time_series),
            "time_series": time_series,
        }

        # Rate limiting lịch sự với World Bank
        time.sleep(random.uniform(0.5, 1.0))

    output = {
        "metadata": {
            "dataset_name": "Dữ liệu Kinh tế Vĩ mô Việt Nam",
            "dataset_name_en": "Vietnam Macroeconomic Data",
            "source": "World Bank Open Data API",
            "source_url": "https://data.worldbank.org/country/vietnam",
            "country": "Vietnam",
            "country_code": COUNTRY_CODE,
            "date_range": f"{MACRO_START_YEAR}-{MACRO_END_YEAR}",
            "total_indicators": len(all_indicators),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "purpose": "Task 6 - Xây dựng mạng lưới chuỗi tác động vĩ mô cho Knowledge Graph",
        },
        "indicators": all_indicators,
    }

    return output


def flatten_macro_for_csv(macro_data):
    """
    Chuyển đổi cấu trúc JSON phân cấp thành bảng phẳng (flat table) cho CSV.
    
    Mỗi dòng: indicator_code | name_vi | name_en | unit | year | value
    """
    rows = []
    for code, indicator in macro_data["indicators"].items():
        for point in indicator["time_series"]:
            rows.append({
                "indicator_code": code,
                "name_vi": indicator["name_vi"],
                "name_en": indicator["name_en"],
                "unit": indicator["unit"],
                "country": "Vietnam",
                "year": point["year"],
                "value": point["value"],
            })
    # Sắp xếp: theo chỉ số, rồi theo năm
    rows.sort(key=lambda x: (x["indicator_code"], x["year"]))
    return rows


# =====================================================================
# PHẦN 2: THU THẬP GIÁ HÀNG HÓA THẾ GIỚI (YAHOO FINANCE)
# =====================================================================

# Bảng ánh xạ: Mã ticker Yahoo Finance -> Thông tin hàng hóa
COMMODITY_TICKERS = {
    "BZ=F": {
        "name_vi": "Dầu thô Brent",
        "name_en": "Brent Crude Oil Futures",
        "unit": "USD/thùng",
        "impact": "Tác động ngành: Dầu khí (PVD, PVS, PLX), Vận tải, Phân bón",
    },
    "CL=F": {
        "name_vi": "Dầu thô WTI",
        "name_en": "WTI Crude Oil Futures",
        "unit": "USD/thùng",
        "impact": "Tác động: Giá xăng dầu, chi phí vận tải, lạm phát",
    },
    "GC=F": {
        "name_vi": "Vàng",
        "name_en": "Gold Futures",
        "unit": "USD/ounce",
        "impact": "Tác động: Tâm lý trú ẩn an toàn, lạm phát, tỷ giá",
    },
    "SI=F": {
        "name_vi": "Bạc",
        "name_en": "Silver Futures",
        "unit": "USD/ounce",
        "impact": "Tác động: Ngành công nghệ, điện tử, kim loại quý",
    },
    "HG=F": {
        "name_vi": "Đồng",
        "name_en": "Copper Futures",
        "unit": "USD/pound",
        "impact": "Tác động: Chỉ báo sức khỏe kinh tế toàn cầu, ngành xây dựng",
    },
    "NG=F": {
        "name_vi": "Khí tự nhiên",
        "name_en": "Natural Gas Futures",
        "unit": "USD/MMBtu",
        "impact": "Tác động: Chi phí năng lượng, ngành điện (POW, PPC)",
    },
    "ZC=F": {
        "name_vi": "Ngô (Corn)",
        "name_en": "Corn Futures",
        "unit": "Cent/bushel",
        "impact": "Tác động: Ngành chăn nuôi, thức ăn gia súc (DBC)",
    },
    "ZS=F": {
        "name_vi": "Đậu tương",
        "name_en": "Soybean Futures",
        "unit": "Cent/bushel",
        "impact": "Tác động: Ngành thực phẩm, dầu ăn, chăn nuôi",
    },
    "CT=F": {
        "name_vi": "Bông vải (Cotton)",
        "name_en": "Cotton Futures",
        "unit": "Cent/pound",
        "impact": "Tác động: Ngành dệt may (TCM, STK, TNG)",
    },
    "KC=F": {
        "name_vi": "Cà phê",
        "name_en": "Coffee Futures",
        "unit": "Cent/pound",
        "impact": "Tác động: Ngành cà phê xuất khẩu Việt Nam (VN là top 2 thế giới)",
    },
    "SB=F": {
        "name_vi": "Đường",
        "name_en": "Sugar Futures",
        "unit": "Cent/pound",
        "impact": "Tác động: Ngành mía đường (SBT, QNS, LSS)",
    },
    "RB=F": {
        "name_vi": "Cao su tự nhiên",
        "name_en": "Rubber Futures (TOCOM)",
        "unit": "Cent/pound",
        "impact": "Tác động: Ngành cao su (GVR, DPR, PHR, TRC)",
    },
}

# Khoảng thời gian lấy dữ liệu commodity (5 năm gần nhất)
COMMODITY_PERIOD = "5y"
COMMODITY_INTERVAL = "1mo"  # Tần suất: hàng tháng (Monthly)


def fetch_commodity_data_yfinance():
    """
    Thu thập giá hàng hóa thế giới từ Yahoo Finance sử dụng thư viện yfinance.

    Lấy dữ liệu lịch sử 5 năm gần nhất, tần suất hàng tháng.
    """
    print("\n" + "=" * 65)
    print("  🌍 PHẦN 2: THU THẬP GIÁ HÀNG HÓA THẾ GIỚI")
    print(f"  Nguồn: Yahoo Finance (finance.yahoo.com)")
    print(f"  Phạm vi: {COMMODITY_PERIOD} gần nhất, tần suất {COMMODITY_INTERVAL}")
    print("=" * 65)

    try:
        import yfinance as yf
    except ImportError:
        print("\n[!] Chưa cài thư viện yfinance. Đang thử cài đặt tự động...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "yfinance"])
        import yfinance as yf

    all_commodities = {}
    total = len(COMMODITY_TICKERS)

    for idx, (ticker, info) in enumerate(COMMODITY_TICKERS.items(), 1):
        print(f"\n[{idx}/{total}] Đang tải: {info['name_vi']} ({ticker})...")

        try:
            commodity = yf.Ticker(ticker)
            hist = commodity.history(period=COMMODITY_PERIOD, interval=COMMODITY_INTERVAL)

            if hist.empty:
                print(f"   [-] Không có dữ liệu cho {ticker}.")
                time_series = []
            else:
                time_series = []
                for date, row in hist.iterrows():
                    time_series.append({
                        "date": date.strftime("%Y-%m-%d"),
                        "open": round(float(row["Open"]), 4) if row["Open"] == row["Open"] else None,
                        "high": round(float(row["High"]), 4) if row["High"] == row["High"] else None,
                        "low": round(float(row["Low"]), 4) if row["Low"] == row["Low"] else None,
                        "close": round(float(row["Close"]), 4) if row["Close"] == row["Close"] else None,
                        "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                    })

                print(f"   + Thành công: {len(time_series)} tháng dữ liệu ({time_series[0]['date']} → {time_series[-1]['date']})")

            all_commodities[ticker] = {
                "ticker": ticker,
                "name_vi": info["name_vi"],
                "name_en": info["name_en"],
                "unit": info["unit"],
                "impact_vietnam": info["impact"],
                "data_points": len(time_series),
                "time_series": time_series,
            }

        except Exception as e:
            print(f"   [!] Lỗi khi tải {ticker}: {e}")
            all_commodities[ticker] = {
                "ticker": ticker,
                "name_vi": info["name_vi"],
                "name_en": info["name_en"],
                "unit": info["unit"],
                "impact_vietnam": info["impact"],
                "data_points": 0,
                "time_series": [],
                "error": str(e),
            }

        # Rate limiting lịch sự
        time.sleep(random.uniform(0.3, 0.8))

    output = {
        "metadata": {
            "dataset_name": "Giá Hàng hóa Thế giới",
            "dataset_name_en": "Global Commodity Prices",
            "source": "Yahoo Finance",
            "source_url": "https://finance.yahoo.com/markets/commodities/",
            "period": COMMODITY_PERIOD,
            "interval": COMMODITY_INTERVAL,
            "total_commodities": len(all_commodities),
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "purpose": "Task 6 - Xây dựng mạng lưới tác động giá hàng hóa lên ngành chứng khoán VN cho Knowledge Graph",
        },
        "commodities": all_commodities,
    }

    return output


def flatten_commodity_for_csv(commodity_data):
    """
    Chuyển đổi cấu trúc JSON phân cấp commodity thành bảng phẳng cho CSV.
    
    Mỗi dòng: ticker | name_vi | name_en | unit | date | open | high | low | close | volume
    """
    rows = []
    for ticker, commodity in commodity_data["commodities"].items():
        for point in commodity["time_series"]:
            rows.append({
                "ticker": ticker,
                "name_vi": commodity["name_vi"],
                "name_en": commodity["name_en"],
                "unit": commodity["unit"],
                "impact_vietnam": commodity["impact_vietnam"],
                "date": point["date"],
                "open": point["open"],
                "high": point["high"],
                "low": point["low"],
                "close": point["close"],
                "volume": point["volume"],
            })
    # Sắp xếp theo ticker rồi theo ngày
    rows.sort(key=lambda x: (x["ticker"], x["date"]))
    return rows


# =====================================================================
# XUẤT DỮ LIỆU RA FILE JSON & CSV
# =====================================================================

def export_json(data, filename):
    """Xuất dữ liệu ra file JSON (cho AI Copilot & Knowledge Graph)."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"[v] Đã xuất file JSON: {filename}")


def export_csv(rows, filename, fieldnames=None):
    """Xuất dữ liệu ra file CSV chuẩn utf-8-sig (không lỗi font Tiếng Việt trên Excel)."""
    if not rows:
        print(f"[!] Không có dữ liệu để xuất CSV: {filename}")
        return

    if fieldnames is None:
        fieldnames = rows[0].keys()

    with open(filename, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[v] Đã xuất file CSV: {filename}")


# =====================================================================
# KHU VỰC THỰC THI CHÍNH (MAIN ROUTINE)
# =====================================================================

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  📈 FINMIND MACRO & COMMODITY SCRAPER                           ║")
    print("║  Task 6: Dữ liệu Kinh tế Vĩ mô & Giá Hàng hóa                ║")
    print("║  Nguồn: World Bank API + Yahoo Finance                          ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")

    start_time = time.time()

    # ─────────────────────────────────────────────────────────
    # PHẦN 1: Dữ liệu Kinh tế Vĩ mô Việt Nam (World Bank)
    # ─────────────────────────────────────────────────────────
    macro_data = collect_vietnam_macro_data()

    macro_json_file = "FinMind_Macro_Vietnam_GENERAL_MARKET.json"
    macro_csv_file = "FinMind_Macro_Vietnam_GENERAL_MARKET.csv"

    export_json(macro_data, macro_json_file)
    macro_rows = flatten_macro_for_csv(macro_data)
    export_csv(macro_rows, macro_csv_file)

    # ─────────────────────────────────────────────────────────
    # PHẦN 2: Giá Hàng hóa Thế giới (Yahoo Finance)
    # ─────────────────────────────────────────────────────────
    commodity_data = fetch_commodity_data_yfinance()

    commodity_json_file = "FinMind_Commodity_Global_GENERAL_MARKET.json"
    commodity_csv_file = "FinMind_Commodity_Global_GENERAL_MARKET.csv"

    export_json(commodity_data, commodity_json_file)
    commodity_rows = flatten_commodity_for_csv(commodity_data)
    export_csv(commodity_rows, commodity_csv_file)

    # ─────────────────────────────────────────────────────────
    # TỔNG KẾT
    # ─────────────────────────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)
    macro_count = sum(
        ind["data_points"] for ind in macro_data["indicators"].values()
    )
    commodity_count = sum(
        c["data_points"] for c in commodity_data["commodities"].values()
    )

    print("\n" + "=" * 65)
    print("  ✅ HOÀN TẤT THU THẬP DỮ LIỆU TASK 6!")
    print("=" * 65)
    print(f"  📊 Vĩ mô Việt Nam : {len(macro_data['indicators'])} chỉ số, {macro_count} điểm dữ liệu")
    print(f"  🌍 Hàng hóa TG    : {len(commodity_data['commodities'])} loại, {commodity_count} điểm dữ liệu")
    print(f"  ⏱️  Thời gian      : {elapsed} giây")
    print(f"\n  📁 File đã xuất:")
    print(f"     1. {macro_json_file}")
    print(f"     2. {macro_csv_file}")
    print(f"     3. {commodity_json_file}")
    print(f"     4. {commodity_csv_file}")
    print(f"\n  💡 Chạy Watchdog (finmind_file_organizer.py) để tự động phân loại")
    print(f"     vào FinMind_Data_Lake/GENERAL_MARKET/")
    print("=" * 65)
