# =====================================================================
# PIPELINE TỔNG HỢP - CHẠY ĐỦ 6 NHIỆM VỤ THU THẬP DỮ LIỆU (TASK 2-7)
# CỦA DỰ ÁN AI_Stock_Platform_NCKH (đã merge từ 4 nhánh: Quan, Nhan,
# HuynhVu, Huyen). Xem README.md để biết chi tiết từng nhiệm vụ.
#
# Task 1 (Báo cáo Thường niên) KHÔNG nằm trong pipeline này - dữ liệu đã
# có sẵn theo xác nhận của nhóm.
# =====================================================================

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$env:PYTHONIOENCODING = "utf-8"

$logDir = "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logFile = Join-Path $logDir "full_pipeline_$timestamp.log"

function Run-Step {
    param($Name, $WorkDir, $ScriptArgs)
    Add-Content -Path $logFile -Value "`n===== $Name - $(Get-Date) ====="
    Push-Location $WorkDir
    & py @ScriptArgs *>> "$PSScriptRoot\$logFile"
    Pop-Location
}

Add-Content -Path $logFile -Value "===== AI_Stock_Platform_NCKH - Full Pipeline bat dau - $(Get-Date) ====="

# --- Task 4 + Task 5: Chi so tai chinh & Du lieu gia / dong tien ---
Run-Step -Name "Task4-5: vnstock_data_fetcher" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("vnstock_data_fetcher.py")
Run-Step -Name "Task4-5: market_data_fetcher"  -WorkDir "data_ingestion\structured_data" -ScriptArgs @("market_data_fetcher.py")
Run-Step -Name "Task4: flatten_vnstock_json (JSON -> CSV cho Google Sheet)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("flatten_vnstock_json.py")

# --- Task 3: Tin tuc & Cong bo thong tin hang ngay ---
Run-Step -Name "Task3: CafeFScraper"          -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("CafeFScraper.py")
Run-Step -Name "Task3: vneconomy_scraper"     -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("vneconomy_scraper.py")
Run-Step -Name "Task3: cafef_bctc_scraper"    -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("cafef_bctc_scraper.py")
Run-Step -Name "Task3: finmind_file_organizer --once" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("finmind_file_organizer.py", "--once")

# --- Task 6: Kinh te vi mo & Gia hang hoa ---
Run-Step -Name "Task6: macro_commodity_base (World Bank + Yahoo Finance)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_base.py")
Run-Step -Name "Task6: macro_commodity_append_sectors (11 nganh bo sung)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_append_sectors.py")

# --- Task 7: Bo du lieu Hoi-Dap chuan chuyen gia + Chuan muc ke toan VAS ---
Run-Step -Name "Task7: stackexchange_qa_scraper"        -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("stackexchange_qa_scraper.py")
Run-Step -Name "Task7: vas_accounting_standards_scraper" -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("vas_accounting_standards_scraper.py")

# --- Task 2: Bao cao Phan tich tu Cong ty Chung khoan (SSI, VCI, VNDirect, HSC...) ---
# Luu y: crawler nay dung Selenium (cho CafeF) va co the chay lau (nhieu
# phut/ticker) do phai tai + doc PDF. Mac dinh chi chay cho FPT; sua danh
# sach --tickers de mo rong.
Run-Step -Name "Task2: brokerage_report_crawler (FPT)" -WorkDir "data_ingestion\brokerage_reports" -ScriptArgs @("main.py", "--tickers", "FPT", "--sources", "cafef", "ssi", "vietstock", "vndirect", "--download-pdf", "--extract-pdf")

# --- Buoc cuoi: gom toan bo CSV vua sinh ra va day len Google Sheet ---
# Can co file gsheet_credentials.json dat tai goc du an (xem README.md
# muc "Huong dan cho thanh vien nhom"). Neu chua co file nay, buoc nay
# se bao loi FileNotFoundError va dung - cac buoc thu thap du lieu phia
# tren van da chay va co du lieu local binh thuong.
if (Test-Path "$PSScriptRoot\gsheet_credentials.json") {
    Run-Step -Name "Upload toan bo du lieu len Google Sheet" -WorkDir "." -ScriptArgs @("upload_all_data.py")
} else {
    Add-Content -Path $logFile -Value "`n[!] Bo qua buoc upload Google Sheet: khong tim thay gsheet_credentials.json tai $PSScriptRoot"
    Write-Host "[!] Khong tim thay gsheet_credentials.json - bo qua buoc upload len Google Sheet. Xem README.md de biet cach lay file nay."
}

Add-Content -Path $logFile -Value "`n===== Hoan tat toan bo pipeline - $(Get-Date) ====="
Write-Host "Hoan tat. Xem log chi tiet tai: $logFile"
