# QuestionWork -- Run Database Migrations

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $ROOT "backend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QuestionWork -- Database Migrations    " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path $BACKEND_DIR)) {
    Write-Host "[ERROR] Backend directory not found: $BACKEND_DIR" -ForegroundColor Red
    exit 1
}

Push-Location $BACKEND_DIR

$ALEMBIC_EXE = Join-Path $BACKEND_DIR ".venv\Scripts\alembic.exe"
if (-not (Test-Path $ALEMBIC_EXE)) {
    Write-Host "[ERROR] Alembic not found at $ALEMBIC_EXE" -ForegroundColor Red
    Write-Host "        Make sure the virtual environment is set up and alembic is installed." -ForegroundColor Yellow
    Pop-Location
    exit 1
}

Write-Host "[INFO] Running 'alembic upgrade head'..." -ForegroundColor Gray

try {
    # Run alembic executable from the virtual environment
    & $ALEMBIC_EXE upgrade head

    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Alembic process exited with code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "[OK] Migrations applied successfully!" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "[ERROR] Failed to apply migrations." -ForegroundColor Red
    Write-Host $_ -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location
Write-Host "==========================================" -ForegroundColor Cyan
