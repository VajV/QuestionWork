# QuestionWork - Complete Quest Flow Test
# Tests: Create -> Apply -> Assign -> Complete -> Confirm

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Complete Quest Flow Test" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$API_URL = "http://localhost:8000/api/v1"

# ============================================
# Step 1: Login as CLIENT (quest creator)
# ============================================
Write-Host "`n[1/6] Login as CLIENT (quest creator)..." -ForegroundColor Yellow

$clientLogin = '{"username":"novice_dev","password":"password123"}'

try {
    $clientResponse = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $clientLogin
    Write-Host "  SUCCESS: Logged in as $($clientResponse.user.username)" -ForegroundColor Green
    Write-Host "  User ID: $($clientResponse.user.id)" -ForegroundColor Gray
    $clientToken = $clientResponse.access_token
    $clientId = $clientResponse.user.id
    $clientHeaders = @{"Authorization"="Bearer $clientToken";"Content-Type"="application/json"}
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ============================================
# Step 2: Client creates a quest
# ============================================
Write-Host "`n[2/6] CLIENT creates quest..." -ForegroundColor Yellow

$questBody = '{
    "title": "Test Quest for Flow Verification",
    "description": "This quest is created to test the complete quest flow including application, completion, and confirmation.",
    "required_grade": "novice",
    "skills": ["Testing", "API", "Verification"],
    "budget": 5000,
    "currency": "RUB"
}'

try {
    $quest = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Post -Headers $clientHeaders -Body $questBody
    Write-Host "  SUCCESS: Quest created" -ForegroundColor Green
    Write-Host "  Quest ID: $($quest.id)" -ForegroundColor Gray
    Write-Host "  Budget: $($quest.budget) RUB" -ForegroundColor Gray
    Write-Host "  XP Reward: $($quest.xp_reward)" -ForegroundColor Gray
    $questId = $quest.id
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ============================================
# Step 3: Register as FREELANCER (new user)
# ============================================
Write-Host "`n[3/6] Register as FREELANCER (new user)..." -ForegroundColor Yellow

$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$freelancerUsername = "test_freelancer_$timestamp"
$freelancerEmail = "freelancer_$timestamp@test.com"

$registerBody = "{
    `"username`": `"$freelancerUsername`",
    `"email`": `"$freelancerEmail`",
    `"password`": `"TestPass123!`"
}"

try {
    $registerResponse = Invoke-RestMethod -Uri "$API_URL/auth/register" -Method Post -ContentType "application/json" -Body $registerBody
    Write-Host "  SUCCESS: Registered as $($registerResponse.user.username)" -ForegroundColor Green
    Write-Host "  User ID: $($registerResponse.user.id)" -ForegroundColor Gray
    $freelancerToken = $registerResponse.access_token
    $freelancerId = $registerResponse.user.id
    $freelancerHeaders = @{"Authorization"="Bearer $freelancerToken";"Content-Type"="application/json"}
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "  Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

# ============================================
# Step 4: Freelancer applies to the quest
# ============================================
Write-Host "`n[4/6] FREELANCER applies to quest..." -ForegroundColor Yellow

$applyBody = '{
    "cover_letter": "I am very interested in this quest! I have experience with testing and API verification. Ready to start immediately and deliver high quality results.",
    "proposed_price": 4500
}'

try {
    $applyResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/apply" -Method Post -Headers $freelancerHeaders -Body $applyBody
    Write-Host "  SUCCESS: Application submitted" -ForegroundColor Green
    Write-Host "  Application ID: $($applyResponse.application.id)" -ForegroundColor Gray
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "  Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

# ============================================
# Step 5: Client assigns freelancer
# ============================================
Write-Host "`n[5/6] CLIENT assigns freelancer..." -ForegroundColor Yellow

try {
    $assignResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/assign?freelancer_id=$freelancerId" -Method Post -Headers $clientHeaders
    Write-Host "  SUCCESS: Freelancer assigned" -ForegroundColor Green
    Write-Host "  Quest Status: $($assignResponse.quest.status)" -ForegroundColor Gray
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "  Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

# ============================================
# Step 6: Freelancer completes the quest
# ============================================
Write-Host "`n[6/7] FREELANCER completes quest..." -ForegroundColor Yellow

try {
    $completeResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/complete" -Method Post -Headers $freelancerHeaders
    Write-Host "  SUCCESS: Quest completed" -ForegroundColor Green
    Write-Host "  Quest Status: $($completeResponse.quest.status)" -ForegroundColor Gray
    Write-Host "  XP Earned: $($completeResponse.xp_earned)" -ForegroundColor Gray
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "  Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

# ============================================
# Step 7: Client confirms completion
# ============================================
Write-Host "`n[7/7] CLIENT confirms completion..." -ForegroundColor Yellow

try {
    $confirmResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/confirm" -Method Post -Headers $clientHeaders
    Write-Host "  SUCCESS: Quest CONFIRMED!" -ForegroundColor Green
    Write-Host "  XP Reward: $($confirmResponse.xp_reward)" -ForegroundColor Gray
    Write-Host "  Money Reward: $($confirmResponse.money_reward) RUB" -ForegroundColor Gray
    Write-Host "  Message: $($confirmResponse.message)" -ForegroundColor Green
} catch {
    Write-Host "  FAILED: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.ErrorDetails.Message) {
        $errorData = $_.ErrorDetails.Message | ConvertFrom-Json
        Write-Host "  Detail: $($errorData.detail)" -ForegroundColor Red
    }
    exit 1
}

# ============================================
# Summary
# ============================================
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  ALL TESTS PASSED!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

Write-Host "`nQuest Flow Completed:" -ForegroundColor Yellow
Write-Host "  1. Client: novice_dev" -ForegroundColor White
Write-Host "  2. Freelancer: $freelancerUsername" -ForegroundColor White
Write-Host "  3. Quest: $questId" -ForegroundColor White
Write-Host "  4. Status: CONFIRMED" -ForegroundColor White

Write-Host "`nOpen in browser:" -ForegroundColor Cyan
Write-Host "  http://localhost:3000/quests/$questId" -ForegroundColor White
Write-Host "`n============================================" -ForegroundColor Cyan
