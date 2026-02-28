# QuestionWork Backend Run Script
# Запуск FastAPI сервера

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Backend Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$BACKEND_ROOT = Split-Path -Parent $PSScriptRoot

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
Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "ReDoc: http://localhost:8000/redoc" -ForegroundColor Green
Write-Host "`nНажми Ctrl+C для остановки`n" -ForegroundColor Gray

# Запускаем uvicorn
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
