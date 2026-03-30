$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Split-Path -Parent $scriptDir
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
$processor = Join-Path $scriptDir "process_lead_nurture.py"

if (-not (Test-Path $pythonExe)) {
    throw "Python interpreter not found: $pythonExe"
}

if (-not (Test-Path $processor)) {
    throw "Processor script not found: $processor"
}

Set-Location $backendDir
& $pythonExe $processor