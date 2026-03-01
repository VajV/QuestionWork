# QuestionWork -- Start All Services
# Launches backend (FastAPI) and frontend (Next.js) in separate windows

$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $ROOT "backend"
$FRONTEND_DIR = Join-Path $ROOT "frontend"

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

if (Test-Port 8000) {
    Write-Host "[WARN] Port 8000 is already in use. Backend may already be running." -ForegroundColor Yellow
    Write-Host "       To stop: taskkill /F /IM uvicorn.exe" -ForegroundColor Gray
} else {
    Write-Host "  [OK] Port 8000 is free" -ForegroundColor Green
}

if (Test-Port 3000) {
    Write-Host "[WARN] Port 3000 is already in use. Frontend may already be running." -ForegroundColor Yellow
    Write-Host "       To stop: taskkill /F /IM node.exe" -ForegroundColor Gray
} else {
    Write-Host "  [OK] Port 3000 is free" -ForegroundColor Green
}

Write-Host ""

# ── Start Backend ────────────────────────────────────────────────────────────

Write-Host "[START] Launching Backend (FastAPI on :8000)..." -ForegroundColor Cyan

$backendCmd = "cd '$BACKEND_DIR'; " +
    "Write-Host '--- QuestionWork Backend ---' -ForegroundColor Cyan; " +
    "if (Test-Path '.venv\Scripts\activate.ps1') { & '.venv\Scripts\activate.ps1'; Write-Host '[OK] venv activated' -ForegroundColor Green } " +
    "else { Write-Host '[WARN] venv not found, using system Python' -ForegroundColor Yellow }; " +
    "Write-Host '[INFO] Starting uvicorn on http://127.0.0.1:8000 ...' -ForegroundColor Gray; " +
    "Write-Host '[INFO] Swagger: http://localhost:8000/docs' -ForegroundColor Gray; " +
    "Write-Host ''; " +
    "uvicorn app.main:app --reload --host 127.0.0.1 --port 8000; " +
    "Write-Host ''; " +
    "Write-Host '[INFO] Backend stopped. Press any key to close...' -ForegroundColor Yellow; " +
    "[Console]::ReadKey() | Out-Null"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd `
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
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" `
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
    Write-Host "  [OK] Backend is up! http://localhost:8000/health" -ForegroundColor Green
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
Write-Host "  Backend   : http://localhost:8000" -ForegroundColor White
Write-Host "  Swagger   : http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Health    : http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "  Test login:" -ForegroundColor Gray
Write-Host "    Username : novice_dev"    -ForegroundColor Gray
Write-Host "    Password : password123"   -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Enter to open the app in browser (or Ctrl+C to exit)..." -ForegroundColor Yellow
$null = Read-Host

Start-Process "http://localhost:3000"
