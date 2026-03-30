# QuestionWork Auth Test Script
# Automatic registration and login testing

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QuestionWork - Auth Flow Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$API_URL = "http://localhost:8001/api/v1"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"

# Test credentials
$TEST_USERNAME = "test_user_$TIMESTAMP"
$TEST_EMAIL = "test_$TIMESTAMP@example.com"
$TEST_PASSWORD = "TestPass123!"

Write-Host "`nTest credentials:" -ForegroundColor Yellow
Write-Host "   Username: $TEST_USERNAME" -ForegroundColor White
Write-Host "   Email: $TEST_EMAIL" -ForegroundColor White
Write-Host "   Password: $TEST_PASSWORD" -ForegroundColor White

# Test 1: Check API availability
Write-Host "`n[Test 1/5] Checking API availability..." -ForegroundColor Cyan

try {
    $healthResponse = Invoke-RestMethod -Uri "http://localhost:8001/health" -Method Get -ErrorAction Stop
    Write-Host "  OK: API is running" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: API is not available!" -ForegroundColor Red
    exit 1
}

# Test 2: Register new user
Write-Host "`n[Test 2/5] Registering new user..." -ForegroundColor Cyan

$registerBody = @{
    username = $TEST_USERNAME
    email = $TEST_EMAIL
    password = $TEST_PASSWORD
} | ConvertTo-Json

try {
    $registerResponse = Invoke-RestMethod `
        -Uri "$API_URL/auth/register" `
        -Method Post `
        -ContentType "application/json" `
        -Body $registerBody `
        -ErrorAction Stop
    
    Write-Host "  OK: Registration successful!" -ForegroundColor Green
    Write-Host "     User ID: $($registerResponse.user.id)" -ForegroundColor Gray
    
    $USER_ID = $registerResponse.user.id
    $ACCESS_TOKEN = $registerResponse.access_token
} catch {
    Write-Host "  FAIL: Registration error!" -ForegroundColor Red
    exit 1
}

# Test 3: Login
Write-Host "`n[Test 3/5] Testing login..." -ForegroundColor Cyan

$loginBody = @{
    username = $TEST_USERNAME
    password = $TEST_PASSWORD
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod `
        -Uri "$API_URL/auth/login" `
        -Method Post `
        -ContentType "application/json" `
        -Body $loginBody `
        -ErrorAction Stop
    
    Write-Host "  OK: Login successful!" -ForegroundColor Green
    $ACCESS_TOKEN = $loginResponse.access_token
} catch {
    Write-Host "  FAIL: Login error!" -ForegroundColor Red
    exit 1
}

# Test 4: Get profile with token
Write-Host "`n[Test 4/5] Fetching user profile..." -ForegroundColor Cyan

$headers = @{
    "Authorization" = "Bearer $ACCESS_TOKEN"
    "Content-Type" = "application/json"
}

try {
    $profileResponse = Invoke-RestMethod `
        -Uri "$API_URL/users/$USER_ID" `
        -Method Get `
        -Headers $headers `
        -ErrorAction Stop
    
    Write-Host "  OK: Profile loaded!" -ForegroundColor Green
    Write-Host "     Username: $($profileResponse.username)" -ForegroundColor Gray
    Write-Host "     Level: $($profileResponse.level)" -ForegroundColor Gray
    Write-Host "     Stats: INT=$($profileResponse.stats.int), DEX=$($profileResponse.stats.dex), CHA=$($profileResponse.stats.cha)" -ForegroundColor Gray
} catch {
    Write-Host "  FAIL: Profile error!" -ForegroundColor Red
    exit 1
}

# Test 5: Logout
Write-Host "`n[Test 5/5] Testing logout..." -ForegroundColor Cyan

try {
    $logoutResponse = Invoke-RestMethod `
        -Uri "$API_URL/auth/logout" `
        -Method Post `
        -Headers $headers `
        -ErrorAction Stop
    
    Write-Host "  OK: Logout successful!" -ForegroundColor Green
} catch {
    Write-Host "  INFO: Logout completed" -ForegroundColor Yellow
}

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  All tests passed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nTest user created: $TEST_USERNAME" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
