param(
    [switch]$RunAsSystem,
    [string]$UserName,
    [string]$Password,
    [int]$IntervalHours = 6,
    [string]$TaskName = "QuestionWork Lead Nurture"
)

$ErrorActionPreference = "Stop"

function Assert-Elevated {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated PowerShell session."
    }
}

function Build-TaskAction {
    return New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\QuestionWork\backend\scripts\run_lead_nurture.ps1"'
}

function Build-TaskTrigger {
    $startAt = (Get-Date).AddMinutes(10)
    $trigger = New-ScheduledTaskTrigger -Once -At $startAt

    $trigger.Repetition = New-ScheduledTaskTrigger -Once -At $startAt
    $trigger.Repetition.Interval = (New-TimeSpan -Hours $IntervalHours)
    return $trigger
}

Assert-Elevated

if (-not $RunAsSystem -and [string]::IsNullOrWhiteSpace($UserName)) {
    throw "Specify -RunAsSystem or provide -UserName."
}

if (-not $RunAsSystem -and [string]::IsNullOrWhiteSpace($Password)) {
    throw "When -UserName is provided, -Password is also required so the task can run without an interactive logon."
}

$action = Build-TaskAction
$trigger = Build-TaskTrigger

if ($RunAsSystem) {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
} else {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -User $UserName -Password $Password -RunLevel Highest -Force | Out-Null
}

Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State, @{Name = "UserId"; Expression = { $_.Principal.UserId } }, @{Name = "LogonType"; Expression = { $_.Principal.LogonType } }, @{Name = "RunLevel"; Expression = { $_.Principal.RunLevel } }