# QuestionWork -- Test Database Connection

$ROOT = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR = Join-Path $ROOT "backend"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QuestionWork -- Test DB Connection     " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

Write-Host "[INFO] Checking port 5432..." -ForegroundColor Gray
$tcp = Test-NetConnection -ComputerName "localhost" -Port 5432 -WarningAction SilentlyContinue
if ($tcp.TcpTestSucceeded) {
    Write-Host "  [OK] Port 5432 is open" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Port 5432 is closed. Is PostgreSQL running?" -ForegroundColor Red
}

Write-Host "`n[INFO] Checking Docker container..." -ForegroundColor Gray
$status = docker inspect -f '{{.State.Status}}' questionwork_db 2>$null
if ($status -eq "running") {
    Write-Host "  [OK] Container 'questionwork_db' is running" -ForegroundColor Green

    Write-Host "`n[INFO] Running pg_isready inside container..." -ForegroundColor Gray
    $pgReady = docker exec questionwork_db pg_isready -U postgres -d questionwork 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Database is ready: $pgReady" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Database is not ready" -ForegroundColor Red
    }
} else {
    Write-Host "  [ERROR] Container 'questionwork_db' is not running" -ForegroundColor Red
}

Write-Host "`n[INFO] Testing asyncpg connection from Python..." -ForegroundColor Gray
$PYTHON_EXE = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"

if (Test-Path $PYTHON_EXE) {
    $testScript = @"
import asyncio
import sys

try:
    import asyncpg
except ImportError:
    print('  [ERROR] asyncpg not installed')
    sys.exit(1)

async def main():
    try:
        conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/questionwork')
        version = await conn.fetchval('SELECT version()')
        print('  [OK] Connected successfully via asyncpg!')
        print(f'  [INFO] DB Version: {version.split()[1]}')
        await conn.close()
    except Exception as e:
        print(f'  [ERROR] Connection failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
"@

    $testFile = Join-Path $BACKEND_DIR "test_db_conn.py"
    $testScript | Out-File -FilePath $testFile -Encoding utf8

    Push-Location $BACKEND_DIR
    try {
        & $PYTHON_EXE $testFile
    } finally {
        Remove-Item $testFile -ErrorAction SilentlyContinue
        Pop-Location
    }
} else {
    Write-Host "  [WARN] Python venv not found. Skipping asyncpg test." -ForegroundColor Yellow
}

Write-Host "`n==========================================" -ForegroundColor Cyan
