# QuestionWork Quests Test Script
# Testing quests API

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Quests API Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$API_URL = "http://localhost:8000/api/v1"

# Test 1: Get all quests
Write-Host "`n[Test 1/5] Getting all quests..." -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Get
    Write-Host "  OK: Found $($response.total) quests" -ForegroundColor Green
    foreach ($quest in $response.quests) {
        Write-Host "    - $($quest.title): $($quest.budget) RUB, $($quest.xp_reward) XP" -ForegroundColor Gray
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 2: Get single quest
Write-Host "`n[Test 2/5] Getting quest details..." -ForegroundColor Cyan

try {
    $response = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Get
    $firstQuestId = $response.quests[0].id
    $quest = Invoke-RestMethod -Uri "$API_URL/quests/$firstQuestId" -Method Get
    Write-Host "  OK: Quest '$($quest.title)'" -ForegroundColor Green
    Write-Host "     Status: $($quest.status)" -ForegroundColor Gray
    Write-Host "     Required Grade: $($quest.required_grade)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 3: Create quest (requires auth)
Write-Host "`n[Test 3/5] Creating new quest..." -ForegroundColor Cyan

# First login
$loginBody = @{
    username = "novice_dev"
    password = "password123"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
    $token = $loginResponse.access_token
    Write-Host "  Logged in as $($loginResponse.user.username)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: Login error - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# Create quest
$questBody = @{
    title = "Test Quest from PowerShell"
    description = "This is a test quest created by the automated test script. Need to test the API."
    required_grade = "novice"
    skills = @("Python", "Testing")
    budget = 5000
    currency = "RUB"
} | ConvertTo-Json

try {
    $newQuest = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Post -Headers $headers -Body $questBody
    Write-Host "  OK: Quest created with ID $($newQuest.id)" -ForegroundColor Green
    Write-Host "     XP Reward: $($newQuest.xp_reward)" -ForegroundColor Gray
    $QUEST_ID = $newQuest.id
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Test 4: Apply to quest (different user)
Write-Host "`n[Test 4/5] Applying to quest..." -ForegroundColor Cyan

# Login as different user
$loginBody2 = @{
    username = "test_user"
    password = "TestPass123!"
} | ConvertTo-Json

try {
    $loginResponse2 = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $loginBody2
    $token2 = $loginResponse2.access_token
    Write-Host "  Logged in as $($loginResponse2.user.username)" -ForegroundColor Green
} catch {
    Write-Host "  INFO: Test user not found, skipping apply test" -ForegroundColor Yellow
    $token2 = $null
}

if ($token2) {
    $headers2 = @{
        "Authorization" = "Bearer $token2"
        "Content-Type" = "application/json"
    }
    
    $applyBody = @{
        cover_letter = "I'm interested in this quest!"
        proposed_price = 4500
    } | ConvertTo-Json
    
    try {
        $applyResponse = Invoke-RestMethod -Uri "$API_URL/quests/$QUEST_ID/apply" -Method Post -Headers $headers2 -Body $applyBody
        Write-Host "  OK: Application sent" -ForegroundColor Green
    } catch {
        Write-Host "  INFO: Apply failed - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# Test 5: Filter quests
Write-Host "`n[Test 5/5] Testing filters..." -ForegroundColor Cyan

try {
    $filtered = Invoke-RestMethod -Uri "$API_URL/quests/?status_filter=open&grade_filter=novice" -Method Get
    Write-Host "  OK: Found $($filtered.total) open novice quests" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Quests API tests completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
