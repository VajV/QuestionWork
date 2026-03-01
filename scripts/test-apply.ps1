# QuestionWork Test Apply Script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Test Apply" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$API_URL = "http://localhost:8000/api/v1"

Write-Host "`n[Step 1] Logging in as freelancer..." -ForegroundColor Yellow

$loginBody = '{"username":"novice_dev","password":"password123"}'

try {
    $loginResponse = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
    Write-Host "  OK: Logged in as $($loginResponse.user.username)" -ForegroundColor Green
    $freelancerToken = $loginResponse.access_token
    $freelancerId = $loginResponse.user.id
    Write-Host "     Grade: $($loginResponse.user.grade)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[Step 2] Getting novice quests..." -ForegroundColor Yellow

try {
    $questsResponse = Invoke-RestMethod -Uri "$API_URL/quests/?status_filter=open&grade_filter=novice" -Method Get
    Write-Host "  OK: Found $($questsResponse.total) novice quests" -ForegroundColor Green
    
    $quest = $questsResponse.quests | Where-Object { $_.client_id -ne $freelancerId } | Select-Object -First 1
    
    if (-not $quest) {
        Write-Host "  Creating test quest..." -ForegroundColor Yellow
        $headers = @{"Authorization"="Bearer $freelancerToken";"Content-Type"="application/json"}
        $questBody = '{"title":"Simple Quest","description":"Easy quest for testing","required_grade":"novice","skills":["Testing"],"budget":1000}'
        $quest = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Post -Headers $headers -Body $questBody
    }
    
    $questId = $quest.id
    Write-Host "  Selected: $($quest.title)" -ForegroundColor Green
    Write-Host "     Required Grade: $($quest.required_grade)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`n[Step 3] Applying to quest..." -ForegroundColor Yellow

$headers = @{
    "Authorization" = "Bearer $freelancerToken"
    "Content-Type" = "application/json"
}

$applyBody = '{"cover_letter":"I am interested in this quest. Ready to start immediately.","proposed_price":900}'

Write-Host "  Sending application..." -ForegroundColor Gray

try {
    $applyResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/apply" -Method Post -Headers $headers -Body $applyBody
    Write-Host "  OK: Application submitted!" -ForegroundColor Green
    Write-Host "     App ID: $($applyResponse.application.id)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "     Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Test completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
