# =====================================================================
# PIPELINE TỔNG HỢP - CHẠY ĐỦ 6 NHIỆM VỤ THU THẬP DỮ LIỆU (TASK 2-7)
# CỦA DỰ ÁN AI_Stock_Platform_NCKH (đã merge từ 4 nhánh: Quan, Nhan,
# HuynhVu, Huyen). Xem README.md để biết chi tiết từng nhiệm vụ.
#
# Task 1 (Báo cáo Thường niên) KHÔNG nằm trong pipeline này - dữ liệu đã
# có sẵn theo xác nhận của nhóm.
#
# CACH DUNG:
#   .\run_full_pipeline.ps1 -Ticker VCB     # chi cao dung ma VCB
#   .\run_full_pipeline.ps1                 # khong truyen -> mac dinh FPT
#
# Ma duoc truyen xuong tat ca script con qua bien moi truong
# FINMIND_TICKER + tham so --ticker. Task 6 (vi mo/hang hoa) va Task 7
# (QA/VAS) khong phu thuoc ma co phieu nen chay nguyen nhu cu.
# =====================================================================

param(
    [ValidatePattern('^[A-Za-z][A-Za-z0-9]{1,9}$')]
    [string]$Ticker = "FPT"
)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$Ticker = $Ticker.ToUpper()
# Cac script con doc bien nay khi khong duoc truyen --ticker truc tiep.
$env:FINMIND_TICKER = $Ticker

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
Add-Content -Path $logFile -Value "Ma co phieu duoc cao trong lan chay nay: $Ticker"
Write-Host "[*] Bat dau cao du lieu cho ma: $Ticker"

# Canh bao som neu ma chua khai bao trong companies.json - Task 2 van chay
# duoc nhung buoc validate_ticker se thieu alias/cong ty con de loai tru,
# de bi bo sot hoac nhan nham bao cao cua cong ty con.
$companiesFile = "$PSScriptRoot\data_ingestion\brokerage_reports\config\companies.json"
if (Test-Path $companiesFile) {
    $companies = Get-Content $companiesFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not ($companies.PSObject.Properties.Name -contains $Ticker)) {
        $msg = "[!] Ma $Ticker chua co trong companies.json - Task 2 se loc bao cao kem chinh xac. Nen bo sung truoc."
        Add-Content -Path $logFile -Value $msg
        Write-Host $msg
    }
}

# --- Task 4 + Task 5: Chi so tai chinh & Du lieu gia / dong tien ---
Run-Step -Name "Task4-5: vnstock_data_fetcher ($Ticker)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("vnstock_data_fetcher.py", "--ticker", $Ticker)
Run-Step -Name "Task4-5: market_data_fetcher ($Ticker)"  -WorkDir "data_ingestion\structured_data" -ScriptArgs @("market_data_fetcher.py", "--ticker", $Ticker)
Run-Step -Name "Task4: flatten_vnstock_json (JSON -> CSV cho Google Sheet)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("flatten_vnstock_json.py")

# --- Task 3: Tin tuc & Cong bo thong tin hang ngay ---
Run-Step -Name "Task3: CafeFScraper ($Ticker)"       -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("CafeFScraper.py", "--ticker", $Ticker)
Run-Step -Name "Task3: vneconomy_scraper ($Ticker)"  -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("vneconomy_scraper.py", "--ticker", $Ticker)
Run-Step -Name "Task3: cafef_bctc_scraper ($Ticker)" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("cafef_bctc_scraper.py", "--ticker", $Ticker)
Run-Step -Name "Task3: finmind_file_organizer --once" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("finmind_file_organizer.py", "--once")

# --- Task 6: Kinh te vi mo & Gia hang hoa ---
Run-Step -Name "Task6: macro_commodity_base (World Bank + Yahoo Finance)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_base.py")
Run-Step -Name "Task6: macro_commodity_append_sectors (11 nganh bo sung)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_append_sectors.py")

# --- Task 7: Bo du lieu Hoi-Dap chuan chuyen gia + Chuan muc ke toan VAS ---
Run-Step -Name "Task7: stackexchange_qa_scraper"        -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("stackexchange_qa_scraper.py")
Run-Step -Name "Task7: vas_accounting_standards_scraper" -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("vas_accounting_standards_scraper.py")

# --- Task 2: Bao cao Phan tich tu Cong ty Chung khoan (SSI, VCI, VNDirect, HSC...) ---
# Luu y: crawler nay dung Selenium (cho CafeF) va co the chay lau (nhieu
# phut/ticker) do phai tai + doc PDF. Chi chay dung 1 ma da truyen vao.
Run-Step -Name "Task2: brokerage_report_crawler ($Ticker)" -WorkDir "data_ingestion\brokerage_reports" -ScriptArgs @("main.py", "--ticker", $Ticker, "--sources", "cafef", "ssi", "vietstock", "vndirect", "--download-pdf", "--extract-pdf")

# --- Gom ket qua thanh 1 file JSON de xem ngay, khong can Google Sheet ---
# Buoc nay luon chay va khong can credentials gi ca.
Run-Step -Name "Tong hop ket qua ra JSON ($Ticker)" -WorkDir "." -ScriptArgs @("export_ticker_summary.py", "--ticker", $Ticker)

$summaryFile = "$PSScriptRoot\FinMind_KetQua_$Ticker.json"
if (Test-Path $summaryFile) {
    # Doc thang file JSON vua tao de in tom tat ra man hinh (Run-Step da
    # ghi toan bo output vao log nen man hinh khong thay gi).
    $summary = Get-Content $summaryFile -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "`n============ KET QUA THU THAP - MA $Ticker ============"
    foreach ($p in $summary.tom_tat.PSObject.Properties) {
        $v = if ($p.Value -is [array]) { $p.Value -join ", " } else { $p.Value }
        Write-Host ("  {0,-30}: {1}" -f $p.Name.Replace("_", " "), $v)
    }
    if ($summary.canh_bao.Count -gt 0) {
        Write-Host "`n  THIEU DU LIEU:"
        $summary.canh_bao | ForEach-Object { Write-Host "    - $_" }
    }
    Write-Host "======================================================="
} else {
    Write-Host "[!] Khong tao duoc file tong hop JSON - xem chi tiet trong $logFile"
}

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
Write-Host "`nHoan tat ma $Ticker."
Write-Host "  - Du lieu tong hop : FinMind_KetQua_$Ticker.json"
Write-Host "  - Log chi tiet     : $logFile"
