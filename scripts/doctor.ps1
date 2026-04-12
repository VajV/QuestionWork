# QuestionWork Doctor
# One command to verify your dev environment is healthy.
# Usage: .\scripts\doctor.ps1 [-SkipDocker] [-Fix]

param(
    [switch]$SkipDocker,
    [switch]$Fix
)

$scriptRoot = $PSScriptRoot

Write-Host ""
Write-Host "  QuestionWork Doctor" -ForegroundColor Cyan
Write-Host "  Running full environment health check..." -ForegroundColor Gray
Write-Host ""

# Run the comprehensive check-status script
$checkArgs = @()
if ($SkipDocker) { $checkArgs += "-SkipDocker" }

& "$scriptRoot\check-status.ps1" @checkArgs
$checkExit = $LASTEXITCODE

if ($checkExit -ne 0 -and $Fix) {
    Write-Host ""
    Write-Host "  Attempting auto-fix..." -ForegroundColor Yellow
    & "$scriptRoot\fix-common-issues.ps1"
    Write-Host ""
    Write-Host "  Re-running checks..." -ForegroundColor Cyan
    & "$scriptRoot\check-status.ps1" @checkArgs
    $checkExit = $LASTEXITCODE
}

if ($checkExit -eq 0) {
    Write-Host "  Doctor verdict: HEALTHY" -ForegroundColor Green
} else {
    Write-Host "  Doctor verdict: NEEDS ATTENTION" -ForegroundColor Red
    Write-Host "  Run  .\scripts\doctor.ps1 -Fix  to attempt auto-fix." -ForegroundColor Yellow
}

Write-Host ""
exit $checkExit
