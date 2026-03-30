# QuestionWork trust-layer worker runner

$ErrorActionPreference = "Stop"
$LegacyWithdrawalGuardMessage = "process_withdrawals.py must not run while WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true. Disable the legacy cron/task before using the new withdrawal job path."

$BACKEND_ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $BACKEND_ROOT

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Python venv not found. Run backend/scripts/setup.ps1 first." -ForegroundColor Red
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"

if ($env:WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED -in @("1", "true", "True", "TRUE", "yes", "YES", "on", "ON")) {
    Write-Host "[OPS] $LegacyWithdrawalGuardMessage" -ForegroundColor Yellow
}

Write-Host "Starting trust-layer worker..." -ForegroundColor Cyan
Write-Host "Queue runtime: app.jobs.worker.WorkerSettings" -ForegroundColor Gray

.\.venv\Scripts\python.exe -m arq app.jobs.worker.WorkerSettings