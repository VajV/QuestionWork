# QuestionWork -- Start Database

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QuestionWork -- Starting Database      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if Docker is running
try {
    docker info > $null 2>&1
} catch {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Start the database using docker-compose
Push-Location $ROOT
Write-Host "[INFO] Starting PostgreSQL via Docker Compose..." -ForegroundColor Gray

docker-compose -f docker-compose.db.yml up -d

Write-Host "[INFO] Database container started. Waiting for it to be ready..." -ForegroundColor Gray

# Wait for healthy state
$maxWait = 30
$waited = 0
$isReady = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited += 2

    # Check container status
    $status = docker inspect -f '{{.State.Health.Status}}' questionwork_db 2>$null

    if ($status -eq "healthy") {
        $isReady = $true
        break
    }
    Write-Host -NoNewline "."
}

Pop-Location
Write-Host ""

if ($isReady) {
    Write-Host "[OK] Database is up and healthy!" -ForegroundColor Green
} else {
    Write-Host "[WARN] Database container started, but might not be fully ready yet." -ForegroundColor Yellow
    Write-Host "       Check logs: docker logs questionwork_db" -ForegroundColor Yellow
}

Write-Host "==========================================" -ForegroundColor Cyan
