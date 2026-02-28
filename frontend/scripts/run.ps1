# QuestionWork Frontend Run Script
# Запуск dev сервера

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Dev Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$FRONTEND_ROOT = Split-Path -Parent $PSScriptRoot

Set-Location $FRONTEND_ROOT

Write-Host "`nЗапуск Next.js dev сервера..." -ForegroundColor Yellow
Write-Host "Открой браузер: http://localhost:3000" -ForegroundColor Green
Write-Host "`nНажми Ctrl+C для остановки`n" -ForegroundColor Gray

npm run dev
