# QuestionWork Connect Script
# Одновременный запуск frontend и backend

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Full Stack Launch" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "frontend"
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"

Write-Host "`nПроверка сервисов..." -ForegroundColor Yellow

# Проверка Redis
Write-Host "  Проверка Redis..." -ForegroundColor Gray
$redisTest = Test-NetConnection -ComputerName localhost -Port 6379 -WarningAction SilentlyContinue -InformationLevel Quiet
if ($redisTest) {
    Write-Host "  ✅ Redis доступен (порт 6379)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Redis не найден! Запустите: docker run -d -p 6379:6379 redis:latest" -ForegroundColor Yellow
}

# Проверка PostgreSQL (опционально)
Write-Host "  Проверка PostgreSQL..." -ForegroundColor Gray
$pgTest = Test-NetConnection -ComputerName localhost -Port 5432 -WarningAction SilentlyContinue -InformationLevel Quiet
if ($pgTest) {
    Write-Host "  ✅ PostgreSQL доступен (порт 5432)" -ForegroundColor Green
} else {
    Write-Host "  ℹ️ PostgreSQL не найден (будет использоваться позже)" -ForegroundColor Gray
}

Write-Host "`nЗапуск сервисов..." -ForegroundColor Yellow

# Запуск Backend (в фоне)
Write-Host "  Запуск Backend (FastAPI :8001)..." -ForegroundColor Gray
Set-Location $BACKEND_DIR

# Проверяем наличие venv
if (-not (Test-Path ".venv")) {
    Write-Host "  ❌ Виртуальное окружение не найдено!" -ForegroundColor Red
    Write-Host "  Запустите: .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# Активируем venv и запускаем backend
$backendScript = @"
& ".\.venv\Scripts\Activate.ps1"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
"@

$backendProcess = Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $backendScript `
    -WorkingDirectory $BACKEND_DIR `
    -WindowStyle Normal `
    -PassThru

Write-Host "  ✅ Backend запущен (PID: $($backendProcess.Id))" -ForegroundColor Green

# Ждём немного пока backend запустится
Start-Sleep -Seconds 3

# Запуск Frontend (в фоне)
Write-Host "  Запуск Frontend (Next.js :3000)..." -ForegroundColor Gray
Set-Location $FRONTEND_DIR

$frontendScript = @"
npm run dev
"@

$frontendProcess = Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $frontendScript `
    -WorkingDirectory $FRONTEND_DIR `
    -WindowStyle Normal `
    -PassThru

Write-Host "  ✅ Frontend запущен (PID: $($frontendProcess.Id))" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Сервисы запущены!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n📋 Полезные ссылки:" -ForegroundColor Cyan
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   Backend API: http://localhost:8001" -ForegroundColor White
Write-Host "   Swagger UI: http://localhost:8001/docs" -ForegroundColor White
Write-Host "   ReDoc: http://localhost:8001/redoc" -ForegroundColor White

Write-Host "`n⏹️  Для остановки:" -ForegroundColor Yellow
Write-Host "   1. Закройте окна PowerShell с серверами" -ForegroundColor White
Write-Host "   2. Или нажмите Ctrl+C в каждом окне" -ForegroundColor White

Write-Host "`n📝 Тестовые пользователи:" -ForegroundColor Cyan
Write-Host "   user_123456 - novice_dev (Lv.1)" -ForegroundColor White
Write-Host "   user_789012 - junior_coder (Lv.5)" -ForegroundColor White
Write-Host "   user_345678 - middle_master (Lv.15)" -ForegroundColor White

Write-Host "`nОткрываем браузер..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"

Write-Host "`n✅ Готово! Удачной разработки!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
