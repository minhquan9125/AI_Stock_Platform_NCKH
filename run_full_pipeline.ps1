# =====================================================================
# PIPELINE TỔNG HỢP - CHẠY ĐỦ 6 NHIỆM VỤ THU THẬP DỮ LIỆU (TASK 2-7)
# CỦA DỰ ÁN AI_Stock_Platform_NCKH (đã merge từ 4 nhánh: Quan, Nhan,
# HuynhVu, Huyen). Xem README.md để biết chi tiết từng nhiệm vụ.
#
# Task 1 (Báo cáo Thường niên) KHÔNG nằm trong pipeline này - dữ liệu đã
# có sẵn theo xác nhận của nhóm.
#
# CACH DUNG:
#   .\run_full_pipeline.ps1 -Ticker VCB              # cao du 6 task cho VCB
#   .\run_full_pipeline.ps1 -Ticker VCB -Tasks 3,4   # chi cao tin tuc + BCTC quy
#   .\run_full_pipeline.ps1 -Tasks 6,7               # chi cao vi mo + QA (khong can ma)
#   .\run_full_pipeline.ps1 -Ticker VCB -Tasks 2 -Sources ssi,vndirect
#
# Y nghia tung task (xem bang chi tiet trong README.md):
#   2 = Bao cao phan tich CTCK   (CHAM NHAT - Selenium + tai/doc PDF)
#   3 = Tin tuc + cong bo BCTC
#   4 = BCTC quy + chi so dinh gia
#   5 = Gia thi truong OHLCV + khoi ngoai
#   6 = Kinh te vi mo + gia hang hoa   (khong phu thuoc ma co phieu)
#   7 = QA chuyen gia + chuan muc VAS  (khong phu thuoc ma co phieu)
#
# Ma duoc truyen xuong tat ca script con qua bien moi truong
# FINMIND_TICKER + tham so --ticker.
# =====================================================================

param(
    [ValidatePattern('^[A-Za-z][A-Za-z0-9]{1,9}$')]
    [string]$Ticker = "FPT",

    # Cac task can chay. Mac dinh "all" = chay het.
    [string[]]$Tasks = @("all"),

    # Rieng Task 2: chon nguon nao trong 4 nguon bao cao phan tich.
    [string[]]$Sources = @("cafef", "ssi", "vietstock", "vndirect")
)

# KHONG dung [ValidateSet] cho 2 tham so tren: khi goi qua
# "powershell -File script.ps1 -Tasks 4,5" thi PowerShell truyen nguyen
# chuoi "4,5" (mot phan tu) chu khong tach thanh mang, nen ValidateSet se
# bao loi. Tu tach dau phay + tu kiem tra de chay duoc CA hai kieu goi:
#   .\run_full_pipeline.ps1 -Tasks 4,5                    (trong PowerShell)
#   powershell -File .\run_full_pipeline.ps1 -Tasks 4,5   (tu cmd/bat)
function Normalize-List {
    param([string[]]$Value, [string[]]$Allowed, [string]$ParamName)
    $items = @($Value | ForEach-Object { $_ -split "[,;\s]+" } | Where-Object { $_ } | ForEach-Object { $_.Trim().ToLower() } | Select-Object -Unique)
    $bad = @($items | Where-Object { $Allowed -notcontains $_ })
    if ($bad.Count -gt 0) {
        Write-Host "[X] Gia tri khong hop le cho -${ParamName}: $($bad -join ', ')"
        Write-Host "    Chi chap nhan: $($Allowed -join ', ')"
        exit 1
    }
    return $items
}

$Tasks = Normalize-List -Value $Tasks -Allowed @("all", "2", "3", "4", "5", "6", "7") -ParamName "Tasks"
$Sources = Normalize-List -Value $Sources -Allowed @("cafef", "ssi", "vietstock", "vndirect") -ParamName "Sources"

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
    Write-Host "  -> $Name"
    Push-Location $WorkDir
    & py @ScriptArgs *>> "$PSScriptRoot\$logFile"
    Pop-Location
}

# Task co duoc chon chay khong? "all" (mac dinh) = chay het.
$runAll = $Tasks -contains "all"
function Want { param([string]$Task) return ($runAll -or ($Tasks -contains $Task)) }

Add-Content -Path $logFile -Value "===== AI_Stock_Platform_NCKH - Full Pipeline bat dau - $(Get-Date) ====="
$taskLabel = if ($runAll) { "tat ca (2,3,4,5,6,7)" } else { ($Tasks | Sort-Object) -join "," }
Add-Content -Path $logFile -Value "Ma co phieu: $Ticker | Task duoc chon: $taskLabel"
Write-Host "[*] Ma co phieu : $Ticker"
Write-Host "[*] Task se chay: $taskLabel"

# Canh bao som neu ma chua khai bao trong companies.json - Task 2 van chay
# duoc nhung buoc validate_ticker se thieu alias/cong ty con de loai tru,
# de bi bo sot hoac nhan nham bao cao cua cong ty con.
$companiesFile = "$PSScriptRoot\data_ingestion\brokerage_reports\config\companies.json"
if ((Want "2") -and (Test-Path $companiesFile)) {
    $companies = Get-Content $companiesFile -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not ($companies.PSObject.Properties.Name -contains $Ticker)) {
        $msg = "[!] Ma $Ticker chua co trong companies.json - Task 2 se loc bao cao kem chinh xac. Nen bo sung truoc."
        Add-Content -Path $logFile -Value $msg
        Write-Host $msg
    }
}

# --- Task 4: BCTC quy + chi so dinh gia ---
if (Want "4") {
    Run-Step -Name "Task4: vnstock_data_fetcher ($Ticker)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("vnstock_data_fetcher.py", "--ticker", $Ticker)
    Run-Step -Name "Task4: flatten_vnstock_json (JSON -> CSV cho Google Sheet)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("flatten_vnstock_json.py")
}

# --- Task 5: Gia thi truong OHLCV + snapshot khoi ngoai ---
if (Want "5") {
    Run-Step -Name "Task5: market_data_fetcher ($Ticker)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("market_data_fetcher.py", "--ticker", $Ticker)
}

# --- Task 3: Tin tuc & Cong bo thong tin hang ngay ---
if (Want "3") {
    Run-Step -Name "Task3: CafeFScraper ($Ticker)"       -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("CafeFScraper.py", "--ticker", $Ticker)
    Run-Step -Name "Task3: vneconomy_scraper ($Ticker)"  -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("vneconomy_scraper.py", "--ticker", $Ticker)
    Run-Step -Name "Task3: cafef_bctc_scraper ($Ticker)" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("cafef_bctc_scraper.py", "--ticker", $Ticker)
    Run-Step -Name "Task3: finmind_file_organizer --once" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("finmind_file_organizer.py", "--once")
}

# --- Task 6: Kinh te vi mo & Gia hang hoa (khong phu thuoc ma co phieu) ---
if (Want "6") {
    Run-Step -Name "Task6: macro_commodity_base (World Bank + Yahoo Finance)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_base.py")
    Run-Step -Name "Task6: macro_commodity_append_sectors (11 nganh bo sung)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_append_sectors.py")
}

# --- Task 7: QA chuan chuyen gia + Chuan muc ke toan VAS (khong phu thuoc ma) ---
if (Want "7") {
    Run-Step -Name "Task7: stackexchange_qa_scraper"        -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("stackexchange_qa_scraper.py")
    Run-Step -Name "Task7: vas_accounting_standards_scraper" -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("vas_accounting_standards_scraper.py")
}

# --- Task 2: Bao cao Phan tich tu Cong ty Chung khoan ---
# Luu y: crawler nay dung Selenium (cho CafeF) va co the chay lau (nhieu
# phut/ticker) do phai tai + doc PDF. Chi chay dung 1 ma da truyen vao.
if (Want "2") {
    $task2Args = @("main.py", "--ticker", $Ticker, "--sources") + $Sources + @("--download-pdf", "--extract-pdf")
    Run-Step -Name "Task2: brokerage_report_crawler ($Ticker, nguon: $($Sources -join ','))" -WorkDir "data_ingestion\brokerage_reports" -ScriptArgs $task2Args
}

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
