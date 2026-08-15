# =====================================================================
# PIPELINE TỔNG HỢP - CHẠY ĐỦ 6 NHIỆM VỤ THU THẬP DỮ LIỆU (TASK 2-7)
# CỦA DỰ ÁN AI_Stock_Platform_NCKH (đã merge từ 4 nhánh: Quan, Nhan,
# HuynhVu, Huyen). Xem README.md để biết chi tiết từng nhiệm vụ.
#
# Task 1 (Báo cáo Thường niên) KHÔNG nằm trong pipeline này - dữ liệu đã
# có sẵn theo xác nhận của nhóm.
#
# CACH DUNG:
#   .\run_full_pipeline.ps1 -Ticker FPT                  # cao du 6 task cho FPT
#   .\run_full_pipeline.ps1 -Ticker FPT,VCB,HPG          # cao nhieu ma 1 lan
#   .\run_full_pipeline.ps1 -Ticker FPT,VCB -Tasks 4,5   # nhieu ma + chon task
#   .\run_full_pipeline.ps1 -Tasks 6,7                   # chi vi mo + QA (khong can ma)
#   .\run_full_pipeline.ps1 -Ticker VCB -Tasks 2 -Sources ssi,vndirect
#
# Khi truyen nhieu ma: Task 2,3,4,5 chay lap cho TUNG ma; Task 6,7 chi
# chay MOT LAN (du lieu vi mo/QA dung chung cho moi ma, khong can lap).
# Moi ma sinh ra 1 file FinMind_KetQua_<MA>.json rieng.
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
    # Mot hoac nhieu ma, ngan cach bang dau phay: -Ticker FPT,VCB,HPG
    [string[]]$Ticker = @("FPT"),

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

# Danh sach ma: tach dau phay giong tren, viet hoa, kiem tra dinh dang.
$Tickers = @($Ticker | ForEach-Object { $_ -split "[,;\s]+" } | Where-Object { $_ } | ForEach-Object { $_.Trim().ToUpper() } | Select-Object -Unique)
$badTicker = @($Tickers | Where-Object { $_ -notmatch '^[A-Z][A-Z0-9]{1,9}$' })
if ($badTicker.Count -gt 0) {
    Write-Host "[X] Ma co phieu khong hop le: $($badTicker -join ', ')"
    Write-Host "    Ma phai bat dau bang chu cai, dai 2-10 ky tu. VD: FPT hoac FPT,VCB,HPG"
    exit 1
}

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
Add-Content -Path $logFile -Value "Ma co phieu: $($Tickers -join ',') | Task duoc chon: $taskLabel"
Write-Host "[*] Ma co phieu : $($Tickers -join ', ')  ($($Tickers.Count) ma)"
Write-Host "[*] Task se chay: $taskLabel"

# Canh bao som neu ma chua khai bao trong companies.json - Task 2 van chay
# duoc nhung buoc validate_ticker se thieu alias/cong ty con de loai tru,
# de bi bo sot hoac nhan nham bao cao cua cong ty con.
$companiesFile = "$PSScriptRoot\data_ingestion\brokerage_reports\config\companies.json"
if ((Want "2") -and (Test-Path $companiesFile)) {
    $companies = Get-Content $companiesFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $missing = @($Tickers | Where-Object { $companies.PSObject.Properties.Name -notcontains $_ })
    if ($missing.Count -gt 0) {
        $msg = "[!] Chua co trong companies.json: $($missing -join ', ') - Task 2 se loc bao cao kem chinh xac."
        Add-Content -Path $logFile -Value $msg
        Write-Host $msg
    }
}

# =====================================================================
# PHAN 1: cac task KHONG phu thuoc ma co phieu - chay DUNG MOT LAN
# du co bao nhieu ma di nua (du lieu vi mo/QA dung chung cho moi ma).
# =====================================================================
if (Want "6") {
    Write-Host "`n[Task 6] Kinh te vi mo & gia hang hoa (chay 1 lan cho moi ma)"
    Run-Step -Name "Task6: macro_commodity_base (World Bank + Yahoo Finance)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_base.py")
    Run-Step -Name "Task6: macro_commodity_append_sectors (11 nganh bo sung)" -WorkDir "data_ingestion\macro_commodity" -ScriptArgs @("macro_commodity_append_sectors.py")
}

if (Want "7") {
    Write-Host "`n[Task 7] QA chuyen gia & chuan muc VAS (chay 1 lan cho moi ma)"
    Run-Step -Name "Task7: stackexchange_qa_scraper"        -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("stackexchange_qa_scraper.py")
    Run-Step -Name "Task7: vas_accounting_standards_scraper" -WorkDir "data_ingestion\qa_ground_truth" -ScriptArgs @("vas_accounting_standards_scraper.py")
}

# =====================================================================
# PHAN 2: cac task phu thuoc ma - lap lai cho TUNG ma
# =====================================================================
$ketQua = @()
$viTri = 0
foreach ($ma in $Tickers) {
    $viTri++
    Write-Host "`n=========== [$viTri/$($Tickers.Count)] MA $ma ==========="
    # Cac script con doc bien nay khi khong duoc truyen --ticker truc tiep.
    $env:FINMIND_TICKER = $ma

    # --- Task 4: BCTC quy + chi so dinh gia ---
    if (Want "4") {
        Run-Step -Name "Task4: vnstock_data_fetcher ($ma)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("vnstock_data_fetcher.py", "--ticker", $ma)
        Run-Step -Name "Task4: flatten_vnstock_json ($ma)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("flatten_vnstock_json.py")
    }

    # --- Task 5: Gia thi truong OHLCV + snapshot khoi ngoai ---
    if (Want "5") {
        Run-Step -Name "Task5: market_data_fetcher ($ma)" -WorkDir "data_ingestion\structured_data" -ScriptArgs @("market_data_fetcher.py", "--ticker", $ma)
    }

    # --- Task 3: Tin tuc & Cong bo thong tin hang ngay ---
    if (Want "3") {
        Run-Step -Name "Task3: CafeFScraper ($ma)"       -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("CafeFScraper.py", "--ticker", $ma)
        Run-Step -Name "Task3: vneconomy_scraper ($ma)"  -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("vneconomy_scraper.py", "--ticker", $ma)
        Run-Step -Name "Task3: cafef_bctc_scraper ($ma)" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("cafef_bctc_scraper.py", "--ticker", $ma)
        Run-Step -Name "Task3: finmind_file_organizer --once" -WorkDir "data_ingestion\news_scraper" -ScriptArgs @("finmind_file_organizer.py", "--once")
    }

    # --- Task 2: Bao cao Phan tich tu Cong ty Chung khoan ---
    # Luu y: crawler nay dung Selenium (cho CafeF) va co the chay lau
    # (nhieu phut/ma) do phai tai + doc PDF.
    if (Want "2") {
        $task2Args = @("main.py", "--ticker", $ma, "--sources") + $Sources + @("--download-pdf", "--extract-pdf")
        Run-Step -Name "Task2: brokerage_report_crawler ($ma, nguon: $($Sources -join ','))" -WorkDir "data_ingestion\brokerage_reports" -ScriptArgs $task2Args
    }

    # --- Gom ket qua ma nay thanh 1 file JSON rieng ---
    # Buoc nay luon chay va khong can credentials gi ca.
    Run-Step -Name "Tong hop ket qua ra JSON ($ma)" -WorkDir "." -ScriptArgs @("export_ticker_summary.py", "--ticker", $ma)

    $summaryFile = "$PSScriptRoot\FinMind_KetQua_$ma.json"
    if (Test-Path $summaryFile) {
        # Doc thang file JSON vua tao de in tom tat ra man hinh (Run-Step
        # da ghi toan bo output vao log nen man hinh khong thay gi).
        $summary = Get-Content $summaryFile -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host "  --- Ket qua ma ${ma} ---"
        foreach ($p in $summary.tom_tat.PSObject.Properties) {
            $v = if ($p.Value -is [array]) { $p.Value -join ", " } else { $p.Value }
            Write-Host ("    {0,-30}: {1}" -f $p.Name.Replace("_", " "), $v)
        }
        if ($summary.canh_bao.Count -gt 0) {
            $summary.canh_bao | ForEach-Object { Write-Host "    [!] $_" }
        }
        $ketQua += [PSCustomObject]@{ Ma = $ma; File = "FinMind_KetQua_$ma.json"; Nhom = $summary.tom_tat.so_nhom_du_lieu_thu_duoc }
    } else {
        Write-Host "  [!] Khong tao duoc file tong hop JSON cho $ma - xem $logFile"
        $ketQua += [PSCustomObject]@{ Ma = $ma; File = "(that bai)"; Nhom = 0 }
    }
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
Write-Host "`n=============== HOAN TAT $($Tickers.Count) MA ==============="
foreach ($r in $ketQua) {
    Write-Host ("  {0,-6} -> {1}  ({2} nhom du lieu)" -f $r.Ma, $r.File, $r.Nhom)
}
Write-Host "  Log chi tiet: $logFile"
Write-Host "======================================================="
