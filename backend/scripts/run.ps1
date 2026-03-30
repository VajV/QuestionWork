# QuestionWork Backend Run Script
# Запуск FastAPI сервера

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$BACKEND_ROOT = Split-Path -Parent $PSScriptRoot
$ExpectedApiPaths = @(
    "/api/v1/analytics/events",
    "/api/v1/analytics/funnel-kpis",
    "/api/v1/notifications/preferences"
)

function Test-ExpectedApiPaths {
    param(
        [string]$OpenApiUrl,
        [string[]]$ExpectedPaths
    )

    $doc = Invoke-RestMethod -Uri $OpenApiUrl -TimeoutSec 5
    $missing = @()

    foreach ($path in $ExpectedPaths) {
        if (-not ($doc.paths.PSObject.Properties.Name -contains $path)) {
            $missing += $path
        }
    }

    return $missing
}

Set-Location $BACKEND_ROOT

# Проверяем наличие venv
if (-not (Test-Path ".venv")) {
    Write-Host "`nОшибка: Виртуальное окружение не найдено!" -ForegroundColor Red
    Write-Host "Запустите сначала: .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Активируем виртуальное окружение
Write-Host "`nАктивация виртуального окружения..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Запуск FastAPI сервера..." -ForegroundColor Yellow
Write-Host "Swagger UI: http://localhost:8001/docs" -ForegroundColor Green
Write-Host "ReDoc: http://localhost:8001/redoc" -ForegroundColor Green
Write-Host "`nНажми Ctrl+C для остановки`n" -ForegroundColor Gray

# Запускаем uvicorn через venv python и проверяем route map
$serverProcess = Start-Process `
    -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001" `
    -NoNewWindow `
    -PassThru

$maxWait = 15
$started = $false

for ($attempt = 0; $attempt -lt $maxWait; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($health.StatusCode -eq 200) {
            $started = $true
            break
        }
    } catch {
        if ($serverProcess.HasExited) {
            break
        }
    }
}

if (-not $started) {
    Write-Host "Ошибка: backend не поднялся на http://127.0.0.1:8001/health" -ForegroundColor Red
    if (-not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

try {
    $missingPaths = Test-ExpectedApiPaths -OpenApiUrl "http://127.0.0.1:8001/openapi.json" -ExpectedPaths $ExpectedApiPaths
    if ($missingPaths.Count -gt 0) {
        Write-Host "Ошибка: backend поднялся, но runtime route map неполная:" -ForegroundColor Red
        foreach ($path in $missingPaths) {
            Write-Host "  - $path" -ForegroundColor Red
        }
        if (-not $serverProcess.HasExited) {
            Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
        }
        exit 1
    }
    Write-Host "[OK] Runtime route map verified" -ForegroundColor Green
} catch {
    Write-Host "Ошибка проверки runtime route map: $($_.Exception.Message)" -ForegroundColor Red
    if (-not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
    exit 1
}

Wait-Process -Id $serverProcess.Id
