# =====================================================================
# CHẠY TOÀN BỘ PIPELINE FINMIND THEO LỊCH (dùng với Windows Task
# Scheduler). Log lại kết quả từng bước ra file trong thư mục logs/ vì
# script chạy nền, không có ai ngồi xem Terminal.
# =====================================================================

$ErrorActionPreference = "Continue"
Set-Location "C:\mascot\mascot"

# Đồng bộ encoding UTF-8 giữa PowerShell và Python (các script Python đã
# ép stdout UTF-8) -> tránh log bị lỗi ký tự (mojibake) khi ghi ra file.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$logDir = "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logFile = Join-Path $logDir "pipeline_$timestamp.log"

function Run-Step {
    param($Name, $ScriptArgs)
    Add-Content -Path $logFile -Value "`n===== $Name - $(Get-Date) ====="
    & py @ScriptArgs *>> $logFile
}

Add-Content -Path $logFile -Value "===== FinMind Daily Pipeline bat dau - $(Get-Date) ====="

Run-Step -Name "vnstock_data_fetcher"              -ScriptArgs @("vnstock_data_fetcher.py")
Run-Step -Name "CafeFScraper"                       -ScriptArgs @("CafeFScraper.py")
Run-Step -Name "VnEconomyScraper"                   -ScriptArgs @("vneconomy_scraper.py")
Run-Step -Name "cafef_bctc_scraper"                 -ScriptArgs @("cafef_bctc_scraper.py")
Run-Step -Name "macro_commodity_scraper"            -ScriptArgs @("macro_commodity_scraper.py")
Run-Step -Name "stackexchange_qa_scraper"           -ScriptArgs @("stackexchange_qa_scraper.py")
Run-Step -Name "vas_accounting_standards_scraper"   -ScriptArgs @("vas_accounting_standards_scraper.py")
Run-Step -Name "finmind_file_organizer --once"      -ScriptArgs @("finmind_file_organizer.py", "--once")
Run-Step -Name "upload_to_gsheet"                   -ScriptArgs @("upload_to_gsheet.py")

Add-Content -Path $logFile -Value "`n===== Hoan tat - $(Get-Date) ====="
