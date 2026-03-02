# QuestionWork -- Smoke Baseline Runner (Week 1)
# Runs core smoke/regression checks with CI-friendly exit codes.

param(
    [switch]$SkipFlow,
    [switch]$SkipPytest,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $ROOT "backend"
$EXIT = 0

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "== $Name ==" -ForegroundColor Cyan
    try {
        & $Action
        Write-Host "✅ PASS  $Name" -ForegroundColor Green
    } catch {
        $script:EXIT = 1
        Write-Host "❌ FAIL  $Name -- $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  QuestionWork -- Smoke Baseline Runner" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Push-Location $ROOT

Run-Step "check-status.ps1" {
    if ($SkipDocker) {
        & (Join-Path $PSScriptRoot "check-status.ps1") -SkipDocker
    } else {
        & (Join-Path $PSScriptRoot "check-status.ps1")
    }
    if ($LASTEXITCODE -ne 0) {
        throw "check-status exited with code $LASTEXITCODE"
    }
}

if (-not $SkipFlow) {
    Run-Step "test-full-flow.ps1" {
        & (Join-Path $PSScriptRoot "test-full-flow.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "test-full-flow exited with code $LASTEXITCODE"
        }
    }
} else {
    Write-Host "⚠️ WARN  test-full-flow.ps1 skipped by flag" -ForegroundColor Yellow
}

if (-not $SkipPytest) {
    Run-Step "backend pytest" {
        Push-Location $BACKEND_DIR
        & .\.venv\Scripts\Activate.ps1
        pytest
        $code = $LASTEXITCODE
        Pop-Location
        if ($code -ne 0) {
            throw "pytest exited with code $code"
        }
    }
} else {
    Write-Host "⚠️ WARN  backend pytest skipped by flag" -ForegroundColor Yellow
}

Pop-Location

Write-Host ""
if ($EXIT -eq 0) {
    Write-Host "✅ PASS  Smoke baseline complete" -ForegroundColor Green
} else {
    Write-Host "❌ FAIL  Smoke baseline has failures" -ForegroundColor Red
}

exit $EXIT
