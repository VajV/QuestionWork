# QuestionWork Test Completion Flow

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Test Completion Flow" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$API_URL = "http://localhost:8001/api/v1"

Write-Host "`n[1/6] Login as CLIENT..." -ForegroundColor Yellow
$clientLogin = '{"username":"novice_dev","password":"password123"}'
$clientResponse = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $clientLogin
Write-Host "  OK: $($clientResponse.user.username)" -ForegroundColor Green
$clientToken = $clientResponse.access_token
$clientHeaders = @{"Authorization"="Bearer $clientToken";"Content-Type"="application/json"}

Write-Host "`n[2/6] CLIENT creates quest..." -ForegroundColor Yellow
$questBody = '{"title":"Test Quest","description":"Test quest for completion flow","required_grade":"novice","skills":["Testing"],"budget":10000}'
$quest = Invoke-RestMethod -Uri "$API_URL/quests/" -Method Post -Headers $clientHeaders -Body $questBody
Write-Host "  OK: Quest $($quest.id)" -ForegroundColor Green
$questId = $quest.id

Write-Host "`n[3/6] Login as FREELANCER..." -ForegroundColor Yellow
$freelancerLogin = '{"username":"junior_coder","password":"password123"}'
$freelancerResponse = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method Post -ContentType "application/json" -Body $freelancerLogin
Write-Host "  OK: $($freelancerResponse.user.username)" -ForegroundColor Green
$freelancerToken = $freelancerResponse.access_token
$freelancerId = $freelancerResponse.user.id
$freelancerHeaders = @{"Authorization"="Bearer $freelancerToken";"Content-Type"="application/json"}

Write-Host "`n[4/6] FREELANCER applies..." -ForegroundColor Yellow
$applyBody = '{"cover_letter":"Interested!","proposed_price":9000}'
$applyResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/apply" -Method Post -Headers $freelancerHeaders -Body $applyBody
Write-Host "  OK: Applied" -ForegroundColor Green

Write-Host "`n[5/6] CLIENT assigns..." -ForegroundColor Yellow
$assignResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/assign?freelancer_id=$freelancerId" -Method Post -Headers $clientHeaders
Write-Host "  OK: Status=$($assignResponse.quest.status)" -ForegroundColor Green

Write-Host "`n[6/6] FREELANCER completes..." -ForegroundColor Yellow
$completeResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/complete" -Method Post -Headers $freelancerHeaders
Write-Host "  OK: Status=$($completeResponse.quest.status)" -ForegroundColor Green

Write-Host "`n[7/7] CLIENT confirms..." -ForegroundColor Yellow
$confirmResponse = Invoke-RestMethod -Uri "$API_URL/quests/$questId/confirm" -Method Post -Headers $clientHeaders
Write-Host "  OK: CONFIRMED!" -ForegroundColor Green
Write-Host "     XP: $($confirmResponse.xp_reward)" -ForegroundColor Gray
Write-Host "     Money: $($confirmResponse.money_reward) RUB" -ForegroundColor Gray

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  ALL TESTS PASSED!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
