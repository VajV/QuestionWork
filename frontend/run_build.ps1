$env:NODE_OPTIONS = '--max-old-space-size=4096'
Set-Location C:\QuestionWork\frontend
$logFile = 'C:\QuestionWork\build_log_clean.txt'
"BUILD_START: $(Get-Date -Format o)" | Out-File $logFile -Encoding ascii

try {
    $output = & node .\node_modules\next\dist\bin\next build 2>&1
    $exitCode = $LASTEXITCODE
    $output | Out-File $logFile -Append -Encoding ascii
    "`nEXIT_CODE: $exitCode" | Out-File $logFile -Append -Encoding ascii
} catch {
    "ERROR: $_" | Out-File $logFile -Append -Encoding ascii
}

"BUILD_END: $(Get-Date -Format o)" | Out-File $logFile -Append -Encoding ascii
