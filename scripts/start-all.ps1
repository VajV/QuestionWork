# QuestionWork -- Start All Services
# Launches backend (FastAPI) and frontend (Next.js) in separate windows

$ErrorActionPreference = "Stop"
$LegacyWithdrawalGuardMessage = "process_withdrawals.py must not run while WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED=true. Disable the legacy cron/task before using the new withdrawal job path."

$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $ROOT "backend"
$FRONTEND_DIR = Join-Path $ROOT "frontend"
$ExpectedApiPaths = @(
    "/api/v1/analytics/events",
    "/api/v1/analytics/funnel-kpis",
    "/api/v1/notifications/preferences"
)

function Get-MissingApiPaths {
    param([string]$OpenApiUrl)

    try {
        $doc = Invoke-RestMethod -Uri $OpenApiUrl -TimeoutSec 5 -ErrorAction Stop
    } catch {
        return $ExpectedApiPaths
    }

    $missing = @()
    foreach ($path in $ExpectedApiPaths) {
        if (-not ($doc.paths.PSObject.Properties.Name -contains $path)) {
            $missing += $path
        }
    }

    return $missing
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QuestionWork -- Starting All Services  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Check directories ────────────────────────────────────────────────────────

if (-not (Test-Path $BACKEND_DIR)) {
    Write-Host "[ERROR] Backend directory not found: $BACKEND_DIR" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $FRONTEND_DIR)) {
    Write-Host "[ERROR] Frontend directory not found: $FRONTEND_DIR" -ForegroundColor Red
    exit 1
}


# ── Start Database ───────────────────────────────────────────────────────────

$START_DB = Join-Path $PSScriptRoot "start-db.ps1"
if (Test-Path $START_DB) {
    & $START_DB
} else {
    Write-Host "[WARN] start-db.ps1 not found." -ForegroundColor Yellow
}

# ── Run Migrations ───────────────────────────────────────────────────────────

$MIGRATE = Join-Path $PSScriptRoot "migrate.ps1"
if (Test-Path $MIGRATE) {
    & $MIGRATE
} else {
    Write-Host "[WARN] migrate.ps1 not found." -ForegroundColor Yellow
}

# ── Check venv ───────────────────────────────────────────────────────────────

$VENV_ACTIVATE = Join-Path $BACKEND_DIR ".venv\Scripts\activate.ps1"
if (-not (Test-Path $VENV_ACTIVATE)) {
    Write-Host "[WARN] Python venv not found at $VENV_ACTIVATE" -ForegroundColor Yellow
    Write-Host "       Run: cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host ""
}

# ── Check node_modules ───────────────────────────────────────────────────────

$NODE_MODULES = Join-Path $FRONTEND_DIR "node_modules"
if (-not (Test-Path $NODE_MODULES)) {
    Write-Host "[INFO] node_modules not found — running npm install..." -ForegroundColor Yellow
    Push-Location $FRONTEND_DIR
    npm install
    Pop-Location
    Write-Host ""
}

# ── Check ports ──────────────────────────────────────────────────────────────

function Test-Port {
    param([int]$Port)
    $conn = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $conn.TcpTestSucceeded
}

Write-Host "[CHECK] Checking port availability..." -ForegroundColor Gray

if (Test-Port 8001) {
    Write-Host "[WARN] Port 8001 is already in use. Backend may already be running." -ForegroundColor Yellow
    Write-Host "       To stop: taskkill /F /IM uvicorn.exe" -ForegroundColor Gray
} else {
    Write-Host "  [OK] Port 8001 is free" -ForegroundColor Green
}

if (Test-Port 3000) {
    Write-Host "[WARN] Port 3000 is already in use. Frontend may already be running." -ForegroundColor Yellow
    Write-Host "       To stop: taskkill /F /IM node.exe" -ForegroundColor Gray
} else {
    Write-Host "  [OK] Port 3000 is free" -ForegroundColor Green
}

Write-Host ""

# ── Start Backend ────────────────────────────────────────────────────────────

Write-Host "[START] Launching Backend (FastAPI on :8001)..." -ForegroundColor Cyan

$backendRunScript = Join-Path $BACKEND_DIR "scripts\run.ps1"

Start-Process powershell -ArgumentList "-NoExit", "-File", $backendRunScript `
    -WindowStyle Normal

Write-Host "  [OK] Backend window opened" -ForegroundColor Green

# ── Wait for backend to boot ─────────────────────────────────────────────────

Write-Host "[WAIT] Waiting for backend to start" -ForegroundColor Gray
$maxWait = 15
$waited  = 0
$started = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    Write-Host -NoNewline "."

    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8001/health" `
                    -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $started = $true
            break
        }
    } catch {
        # still booting
    }
}

Write-Host ""

if ($started) {
    $missingPaths = Get-MissingApiPaths -OpenApiUrl "http://127.0.0.1:8001/openapi.json"
    if ($missingPaths.Count -eq 0) {
        Write-Host "  [OK] Backend is up! http://localhost:8001/health" -ForegroundColor Green
        Write-Host "  [OK] Runtime route map matches expected analytics/notification endpoints" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Backend responded, but runtime route map is stale:" -ForegroundColor Yellow
        foreach ($path in $missingPaths) {
            Write-Host "         - $path" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [WARN] Backend did not respond in ${maxWait}s — it may still be starting." -ForegroundColor Yellow
}

# ── Start Frontend ───────────────────────────────────────────────────────────

Write-Host ""
Write-Host "[START] Launching Frontend (Next.js on :3000)..." -ForegroundColor Cyan

$frontendCmd = "cd '$FRONTEND_DIR'; " +
    "Write-Host '--- QuestionWork Frontend ---' -ForegroundColor Magenta; " +
    "Write-Host '[INFO] Starting Next.js dev server on http://localhost:3000 ...' -ForegroundColor Gray; " +
    "Write-Host ''; " +
    "npm run dev; " +
    "Write-Host ''; " +
    "Write-Host '[INFO] Frontend stopped. Press any key to close...' -ForegroundColor Yellow; " +
    "[Console]::ReadKey() | Out-Null"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd `
    -WindowStyle Normal

Write-Host "  [OK] Frontend window opened" -ForegroundColor Green

$startJobRuntimes = ($env:QUESTIONWORK_START_JOB_RUNTIMES -eq "1") -and $started

if ($env:WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED -in @("1", "true", "True", "TRUE", "yes", "YES", "on", "ON")) {
    Write-Host "[OPS] $LegacyWithdrawalGuardMessage" -ForegroundColor Yellow
}

if ($startJobRuntimes) {
    Write-Host ""
    Write-Host "[START] Launching trust-layer worker..." -ForegroundColor Cyan
    $workerRunScript = Join-Path $BACKEND_DIR "scripts\run_worker.ps1"
    if (Test-Path $workerRunScript) {
        Start-Process powershell -ArgumentList "-NoExit", "-File", $workerRunScript -WindowStyle Normal
        Write-Host "  [OK] Worker window opened" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Worker run script not found: $workerRunScript" -ForegroundColor Yellow
    }

    Write-Host "[START] Launching trust-layer scheduler..." -ForegroundColor Cyan
    $schedulerRunScript = Join-Path $BACKEND_DIR "scripts\run_scheduler.ps1"
    if (Test-Path $schedulerRunScript) {
        Start-Process powershell -ArgumentList "-NoExit", "-File", $schedulerRunScript -WindowStyle Normal
        Write-Host "  [OK] Scheduler window opened" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Scheduler run script not found: $schedulerRunScript" -ForegroundColor Yellow
    }
}

if (($env:QUESTIONWORK_START_JOB_RUNTIMES -eq "1") -and (-not $started)) {
    Write-Host "[WARN] Skipping trust-layer worker/scheduler because backend health check did not succeed." -ForegroundColor Yellow
}

# ── Wait for frontend to boot ────────────────────────────────────────────────

Write-Host "[WAIT] Waiting for frontend to start" -ForegroundColor Gray
$maxWait = 30
$waited  = 0
$fStarted = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    Write-Host -NoNewline "."

    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:3000" `
                    -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $fStarted = $true
            break
        }
    } catch {
        # still booting
    }
}

Write-Host ""

if ($fStarted) {
    Write-Host "  [OK] Frontend is up! http://localhost:3000" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Frontend did not respond in ${maxWait}s — it may still be compiling." -ForegroundColor Yellow
}

# ── Summary ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QuestionWork is running!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Frontend  : http://localhost:3000" -ForegroundColor White
Write-Host "  Backend   : http://localhost:8001" -ForegroundColor White
Write-Host "  Swagger   : http://localhost:8001/docs" -ForegroundColor White
Write-Host "  Health    : http://localhost:8001/health" -ForegroundColor White
if ($startJobRuntimes) {
    Write-Host "  Worker    : separate PowerShell window" -ForegroundColor White
    Write-Host "  Scheduler : separate PowerShell window" -ForegroundColor White
}
if ($env:WITHDRAWAL_AUTO_APPROVE_JOBS_ENABLED -in @("1", "true", "True", "TRUE", "yes", "YES", "on", "ON")) {
    Write-Host "  Guard     : $LegacyWithdrawalGuardMessage" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Test login:" -ForegroundColor Gray
Write-Host "    Username : novice_dev"    -ForegroundColor Gray
Write-Host "    Password : ***REDACTED***"   -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Enter to open the app in browser (or Ctrl+C to exit)..." -ForegroundColor Yellow
$null = Read-Host

Start-Process "http://localhost:3000"
