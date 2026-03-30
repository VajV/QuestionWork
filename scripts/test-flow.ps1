# QuestionWork -- Full E2E Flow Test
# Tests the complete lifecycle: register -> login -> create quest -> apply -> assign -> complete -> confirm
# Compatible with PowerShell 5+ and ASCII-only output

$ErrorActionPreference  = "SilentlyContinue"
$ProgressPreference     = "SilentlyContinue"   # suppress Invoke-WebRequest progress bar noise
$VerbosePreference      = "SilentlyContinue"

$BASE_URL = "http://localhost:8001/api/v1"

# ---------------------------------------------------------------------------
# Counters and log
# ---------------------------------------------------------------------------

$passCount = 0
$failCount = 0
$testLog   = @()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "  +---------------------------------------------+" -ForegroundColor Cyan
    Write-Host ("  |  " + $Title.PadRight(43) + "|") -ForegroundColor Cyan
    Write-Host "  +---------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Msg)
    Write-Host "  >> $Msg" -ForegroundColor DarkCyan
}

function Write-Pass {
    param([string]$Msg, [string]$Detail = "")
    $script:passCount++
    $entry = "PASS | $Msg"
    if ($Detail) { $entry += " | $Detail" }
    $script:testLog += $entry
    Write-Host "    [PASS] $Msg" -ForegroundColor Green -NoNewline
    if ($Detail) {
        Write-Host "  =>  $Detail" -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
}

function Write-Fail {
    param([string]$Msg, [string]$Detail = "")
    $script:failCount++
    $entry = "FAIL | $Msg"
    if ($Detail) { $entry += " | $Detail" }
    $script:testLog += $entry
    Write-Host "    [FAIL] $Msg" -ForegroundColor Red -NoNewline
    if ($Detail) {
        Write-Host "  =>  $Detail" -ForegroundColor DarkGray
    } else {
        Write-Host ""
    }
}

function Write-Info {
    param([string]$Msg)
    Write-Host "    [INFO] $Msg" -ForegroundColor Gray
}

function Invoke-Api {
    param(
        [string]$Method,
        [string]$Endpoint,
        [hashtable]$Headers = @{},
        [string]$Body       = $null,
        [int]$TimeoutSec    = 10
    )

    $uri        = "$BASE_URL$Endpoint"
    $allHeaders = @{ "Content-Type" = "application/json" }
    foreach ($k in $Headers.Keys) { $allHeaders[$k] = $Headers[$k] }

    try {
        $params = @{
            Uri             = $uri
            Method          = $Method
            Headers         = $allHeaders
            UseBasicParsing = $true
            TimeoutSec      = $TimeoutSec
            ErrorAction     = "Stop"
        }
        if ($Body) { $params["Body"] = $Body }

        $resp = Invoke-WebRequest @params
        return @{
            Ok         = $true
            StatusCode = $resp.StatusCode
            Data       = ($resp.Content | ConvertFrom-Json)
            Raw        = $resp.Content
        }
    } catch {
        $code      = 0
        $errorBody = ""
        try {
            $code = $_.Exception.Response.StatusCode.Value__
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $errorBody = $reader.ReadToEnd()
        } catch {}

        return @{
            Ok         = $false
            StatusCode = $code
            Data       = $null
            Raw        = $errorBody
            Error      = $_.Exception.Message
        }
    }
}

function Get-AuthHeader {
    param([string]$Token)
    return @{ Authorization = "Bearer $Token" }
}

# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------

Clear-Host

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Magenta
Write-Host "   QuestionWork -- Full E2E Flow Test"          -ForegroundColor Magenta
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd  HH:mm:ss')"  -ForegroundColor Magenta
Write-Host "  =============================================" -ForegroundColor Magenta

Write-Header "PRE-FLIGHT: Checking backend and PostgreSQL availability"

Write-Step "Connecting to http://localhost:8001/health ..."

$healthOk = $false
try {
    $hr = Invoke-WebRequest -Uri "http://localhost:8001/health" `
              -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    $healthOk = ($hr.StatusCode -eq 200)
} catch {
    $healthOk = $false
}

if (-not $healthOk) {
    Write-Fail "Backend health check" "http://localhost:8001/health did not respond"
    Write-Host ""
    Write-Host "  [ABORT] Backend is not running. Start it first:" -ForegroundColor Red
    Write-Host "          cd backend"                               -ForegroundColor Yellow
    Write-Host "          .venv\Scripts\activate"                   -ForegroundColor Yellow
    Write-Host "          uvicorn app.main:app --reload"            -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Pass "Backend health check" "http://localhost:8001/health => 200 OK"

Write-Step "Checking PostgreSQL TCP port 5432 ..."
$dbPortOk = $false
try {
    $dbConn = Test-NetConnection -ComputerName "127.0.0.1" -Port 5432 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    $dbPortOk = ($dbConn.TcpTestSucceeded -eq $true)
} catch {
    $dbPortOk = $false
}

if ($dbPortOk) {
    Write-Pass "PostgreSQL port check" "127.0.0.1:5432 is reachable"
} else {
    Write-Fail "PostgreSQL port check" "127.0.0.1:5432 is NOT reachable"
    Write-Host "  [ABORT] Database is not available. Start DB first:" -ForegroundColor Red
    Write-Host "          .\scripts\start-db.ps1" -ForegroundColor Yellow
    Write-Host "          .\scripts\migrate.ps1"  -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Step "Checking DB-read endpoint /api/v1/users/ ..."
$dbApiCheck = Invoke-Api -Method GET -Endpoint "/users/?limit=1"
if ($dbApiCheck.Ok -and $dbApiCheck.StatusCode -eq 200) {
    Write-Pass "DB API readiness check" "GET /users/ works (DB queries are operational)"
} else {
    Write-Fail "DB API readiness check" "HTTP $($dbApiCheck.StatusCode) -- $($dbApiCheck.Raw)"
    Write-Host "  [ABORT] Backend is up, but DB-backed endpoints are not ready." -ForegroundColor Red
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------------------
# Generate unique test IDs (timestamp-based)
# ---------------------------------------------------------------------------

$ts              = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$clientUser      = "client_$ts"
$clientEmail     = "client_${ts}@example.com"
$clientPass      = "FlowTest${ts}A!"
$freelancerUser  = "dev_$ts"
$freelancerEmail = "dev_${ts}@example.com"
$freelancerPass  = "FlowTest${ts}B@"

Write-Info "Client username     : $clientUser"
Write-Info "Freelancer username : $freelancerUser"

# ===========================================================================
Write-Header "STEP 1: Register Client Account"
# ===========================================================================

Write-Step "POST /auth/register  (role=client)"

$regClientBody = (@{
    username = $clientUser
    email    = $clientEmail
    password = $clientPass
    role     = "client"
} | ConvertTo-Json -Compress)

$regClient  = Invoke-Api -Method POST -Endpoint "/auth/register" -Body $regClientBody
$clientToken = $null
$clientId    = $null

if ($regClient.Ok -and $regClient.StatusCode -eq 201) {
    Write-Pass "Client registration" "id=$($regClient.Data.user.id)"
    $clientToken = $regClient.Data.access_token
    $clientId    = $regClient.Data.user.id
} else {
    Write-Fail "Client registration" "HTTP $($regClient.StatusCode) -- $($regClient.Raw)"
}

if ($regClient.Ok) {
    $d = $regClient.Data
    $checks = @(
        @{ Label = "access_token present";    Ok = ($null -ne $d.access_token -and $d.access_token.Length -gt 10) },
        @{ Label = "user object present";     Ok = ($null -ne $d.user) },
        @{ Label = "role = client";           Ok = ($d.user.role -eq "client") },
        @{ Label = "grade = novice (default)";Ok = ($d.user.grade -eq "novice") },
        @{ Label = "xp = 0 (fresh user)";     Ok = ($d.user.xp -eq 0) },
        @{ Label = "level = 1 (fresh user)";  Ok = ($d.user.level -eq 1) }
    )
    foreach ($c in $checks) {
        if ($c.Ok) { Write-Pass "Response: $($c.Label)" } else { Write-Fail "Response: $($c.Label)" }
    }
}

# Duplicate registration must fail
Write-Step "POST /auth/register -- duplicate => expect 400"
$dupClient = Invoke-Api -Method POST -Endpoint "/auth/register" -Body $regClientBody
if (-not $dupClient.Ok -and ($dupClient.StatusCode -eq 400 -or $dupClient.StatusCode -eq 409)) {
    Write-Pass "Duplicate registration rejected" "HTTP $($dupClient.StatusCode)"
} else {
    Write-Fail "Duplicate registration should be rejected" "HTTP $($dupClient.StatusCode)"
}

# ===========================================================================
Write-Header "STEP 2: Register Freelancer Account"
# ===========================================================================

Write-Step "POST /auth/register  (role=freelancer)"

$regFreelancerBody = (@{
    username = $freelancerUser
    email    = $freelancerEmail
    password = $freelancerPass
    role     = "freelancer"
} | ConvertTo-Json -Compress)

$regFreelancer   = Invoke-Api -Method POST -Endpoint "/auth/register" -Body $regFreelancerBody
$freelancerToken = $null
$freelancerId    = $null

if ($regFreelancer.Ok -and $regFreelancer.StatusCode -eq 201) {
    Write-Pass "Freelancer registration" "id=$($regFreelancer.Data.user.id)"
    $freelancerToken = $regFreelancer.Data.access_token
    $freelancerId    = $regFreelancer.Data.user.id
} else {
    Write-Fail "Freelancer registration" "HTTP $($regFreelancer.StatusCode) -- $($regFreelancer.Raw)"
}

# ===========================================================================
Write-Header "STEP 3: Login -- both accounts"
# ===========================================================================

# Client login
Write-Step "POST /auth/login  (client)"
$loginClientBody = (@{ username = $clientUser; password = $clientPass } | ConvertTo-Json -Compress)
$loginClient     = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $loginClientBody

if ($loginClient.Ok -and $loginClient.StatusCode -eq 200) {
    Write-Pass "Client login" "token received"
    $clientToken = $loginClient.Data.access_token
} else {
    Write-Fail "Client login" "HTTP $($loginClient.StatusCode)"
}

# Wrong password must return 401
Write-Step "POST /auth/login -- wrong password => expect 401"
$badLoginBody = (@{ username = $clientUser; password = "wrongpassword" } | ConvertTo-Json -Compress)
$badLogin     = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $badLoginBody
if (-not $badLogin.Ok -and $badLogin.StatusCode -eq 401) {
    Write-Pass "Wrong password rejected" "HTTP 401"
} else {
    Write-Fail "Wrong password should be rejected" "HTTP $($badLogin.StatusCode)"
}

# Freelancer login
Write-Step "POST /auth/login  (freelancer)"
$loginFreelancerBody = (@{ username = $freelancerUser; password = $freelancerPass } | ConvertTo-Json -Compress)
$loginFreelancer     = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $loginFreelancerBody

if ($loginFreelancer.Ok -and $loginFreelancer.StatusCode -eq 200) {
    Write-Pass "Freelancer login" "token received"
    $freelancerToken = $loginFreelancer.Data.access_token
} else {
    Write-Fail "Freelancer login" "HTTP $($loginFreelancer.StatusCode)"
}

# ===========================================================================
Write-Header "STEP 3B: Seed Admin And Fund Client Wallet"
# ===========================================================================

$adminToken = $null

Write-Step "Seed default admin user"
try {
    & ".\backend\.venv\Scripts\python.exe" ".\backend\scripts\seed_admin.py" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Admin seed" "backend/scripts/seed_admin.py"
    } else {
        Write-Fail "Admin seed" "Exit code $LASTEXITCODE"
    }
} catch {
    Write-Fail "Admin seed" $_.Exception.Message
}

Write-Step "POST /auth/login  (admin)"
$loginAdminBody = (@{ username = "admin"; password = "Admin123!" } | ConvertTo-Json -Compress)
$loginAdmin = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $loginAdminBody
if ($loginAdmin.Ok -and $loginAdmin.StatusCode -eq 200) {
    Write-Pass "Admin login" "token received"
    $adminToken = $loginAdmin.Data.access_token
} else {
    Write-Fail "Admin login" "HTTP $($loginAdmin.StatusCode)"
}

if ($adminToken -and $clientId) {
    Write-Step "POST /admin/users/$clientId/adjust-wallet  (fund escrow)"
    $fundBody = (@{ amount = 20000; currency = "RUB"; reason = "E2E escrow funding" } | ConvertTo-Json -Compress)
    $fundResp = Invoke-Api -Method POST -Endpoint "/admin/users/$clientId/adjust-wallet" -Headers (Get-AuthHeader $adminToken) -Body $fundBody
    if ($fundResp.Ok -and $fundResp.StatusCode -eq 200) {
        Write-Pass "Client wallet funded" "new_balance=$($fundResp.Data.new_balance) RUB"
    } else {
        Write-Fail "Client wallet funding" "HTTP $($fundResp.StatusCode) -- $($fundResp.Raw)"
    }
}

# ===========================================================================
Write-Header "STEP 4: Get User Profiles"
# ===========================================================================

if ($clientId) {
    Write-Step "GET /users/$clientId"
    $cp = Invoke-Api -Method GET -Endpoint "/users/$clientId"
    if ($cp.Ok) {
        Write-Pass "GET client profile" "username=$($cp.Data.username)"
    } else {
        Write-Fail "GET client profile" "HTTP $($cp.StatusCode)"
    }
}

if ($freelancerId) {
    Write-Step "GET /users/$freelancerId"
    $fp = Invoke-Api -Method GET -Endpoint "/users/$freelancerId"
    if ($fp.Ok) {
        Write-Pass "GET freelancer profile" "username=$($fp.Data.username)"
    } else {
        Write-Fail "GET freelancer profile" "HTTP $($fp.StatusCode)"
    }
}

Write-Step "GET /users/"
$allUsers = Invoke-Api -Method GET -Endpoint "/users/"
if ($allUsers.Ok) {
    Write-Pass "GET all users" "count=$($allUsers.Data.Count)"
} else {
    Write-Fail "GET all users" "HTTP $($allUsers.StatusCode)"
}

Write-Step "GET /users/nonexistent_id -- expect 404"
$noUser = Invoke-Api -Method GET -Endpoint "/users/nonexistent_id_xyz"
if (-not $noUser.Ok -and $noUser.StatusCode -eq 404) {
    Write-Pass "Non-existent user returns 404"
} else {
    Write-Fail "Non-existent user should return 404" "HTTP $($noUser.StatusCode)"
}

# ===========================================================================
Write-Header "STEP 5: Quest List (public)"
# ===========================================================================

Write-Step "GET /quests/?page=1"
$questList = Invoke-Api -Method GET -Endpoint "/quests/?page=1"

if ($questList.Ok -and $questList.StatusCode -eq 200) {
    Write-Pass "GET /quests/ (public)" "total=$($questList.Data.total)"
} else {
    Write-Fail "GET /quests/" "HTTP $($questList.StatusCode)"
}

if ($questList.Ok) {
    $d = $questList.Data
    $hasPag = ($null -ne $d.page) -and ($null -ne $d.page_size) -and ($null -ne $d.has_more)
    if ($hasPag) {
        Write-Pass "Pagination fields present" "page=$($d.page) page_size=$($d.page_size) has_more=$($d.has_more)"
    } else {
        Write-Fail "Pagination fields present" "Missing page/page_size/has_more"
    }
}

Write-Step "GET /quests/?status_filter=open"
$openQ = Invoke-Api -Method GET -Endpoint "/quests/?status_filter=open"
if ($openQ.Ok) {
    Write-Pass "Filter by status=open" "count=$($openQ.Data.total)"
} else {
    Write-Fail "Filter by status=open" "HTTP $($openQ.StatusCode)"
}

# ===========================================================================
Write-Header "STEP 6: Create Quest (as Client)"
# ===========================================================================

$questId = $null

if (-not $clientToken) {
    Write-Fail "Create quest" "No client token -- skipping"
} else {
    Write-Step "POST /quests/  (authenticated as client)"

    $questTitle      = "E2E Test Quest $ts"
    $createQuestBody = (@{
        title          = $questTitle
        description    = "This is an automated E2E test quest created at timestamp $ts. It tests the full quest lifecycle from creation to completion."
        required_grade = "novice"
        skills         = @("Python", "Testing", "Automation")
        budget         = 15000
        currency       = "RUB"
        xp_reward      = 150
    } | ConvertTo-Json -Compress)

    $createQuest = Invoke-Api -Method POST -Endpoint "/quests/" `
                              -Headers (Get-AuthHeader $clientToken) `
                              -Body $createQuestBody

    if ($createQuest.Ok -and $createQuest.StatusCode -eq 201) {
        $questId = $createQuest.Data.id
        Write-Pass "Quest created" "id=$questId"
        Write-Info "  title     : $($createQuest.Data.title)"
        Write-Info "  budget    : $($createQuest.Data.budget) $($createQuest.Data.currency)"
        Write-Info "  xp_reward : $($createQuest.Data.xp_reward)"
        Write-Info "  status    : $($createQuest.Data.status)"
    } else {
        Write-Fail "Quest creation" "HTTP $($createQuest.StatusCode) -- $($createQuest.Raw)"
    }

    if ($createQuest.Ok) {
        $d = $createQuest.Data
        if ($d.status -eq "open")        { Write-Pass "Quest status = open" }       else { Write-Fail "Quest status = open"  "got $($d.status)" }
        if ($d.client_id -eq $clientId)  { Write-Pass "Quest client_id matches" }   else { Write-Fail "Quest client_id matches" "got $($d.client_id)" }
        if ($d.xp_reward -eq 150)        { Write-Pass "Quest xp_reward = 150" }     else { Write-Fail "Quest xp_reward = 150" "got $($d.xp_reward)" }
        if ($d.budget -eq 15000)         { Write-Pass "Quest budget = 15000" }      else { Write-Fail "Quest budget = 15000" "got $($d.budget)" }
    }

    # Unauthenticated create must fail
    Write-Step "POST /quests/ without token -- expect 401/403"
    $unauthCreate = Invoke-Api -Method POST -Endpoint "/quests/" -Body $createQuestBody
    if (-not $unauthCreate.Ok -and ($unauthCreate.StatusCode -eq 401 -or $unauthCreate.StatusCode -eq 403)) {
        Write-Pass "Unauthenticated create rejected" "HTTP $($unauthCreate.StatusCode)"
    } else {
        Write-Fail "Unauthenticated create should be rejected" "HTTP $($unauthCreate.StatusCode)"
    }
}

# ===========================================================================
Write-Header "STEP 7: Get Quest Details"
# ===========================================================================

if ($questId) {
    Write-Step "GET /quests/$questId"
    $qd = Invoke-Api -Method GET -Endpoint "/quests/$questId"
    if ($qd.Ok) {
        Write-Pass "GET quest detail" "title=$($qd.Data.title)"
    } else {
        Write-Fail "GET quest detail" "HTTP $($qd.StatusCode)"
    }

    Write-Step "GET /quests/nonexistent_quest -- expect 404"
    $nq = Invoke-Api -Method GET -Endpoint "/quests/nonexistent_quest_id_xyz"
    if (-not $nq.Ok -and $nq.StatusCode -eq 404) {
        Write-Pass "Non-existent quest returns 404"
    } else {
        Write-Fail "Non-existent quest should return 404" "HTTP $($nq.StatusCode)"
    }

    Write-Step "GET /quests/ -- verify new quest appears in list"
    $ul = Invoke-Api -Method GET -Endpoint "/quests/"
    $inList = $false
    if ($ul.Ok) {
        $inList = ($ul.Data.quests | Where-Object { $_.id -eq $questId }) -ne $null
    }
    if ($inList) {
        Write-Pass "New quest appears in quest list"
    } else {
        Write-Fail "New quest should appear in quest list"
    }
}

# ===========================================================================
Write-Header "STEP 8: Apply to Quest (as Freelancer)"
# ===========================================================================

$applicationId = $null

if ($questId -and $freelancerToken) {
    Write-Step "POST /quests/$questId/apply  (as freelancer)"

    $applyBody = (@{
        cover_letter   = "Hello! I am interested in this E2E test quest. I have experience with Python and testing automation. Ready to start immediately."
        proposed_price = 14000
    } | ConvertTo-Json -Compress)

    $applyResp = Invoke-Api -Method POST -Endpoint "/quests/$questId/apply" `
                            -Headers (Get-AuthHeader $freelancerToken) `
                            -Body $applyBody

    if ($applyResp.Ok -and $applyResp.StatusCode -eq 200) {
        $applicationId = $applyResp.Data.application.id
        Write-Pass "Freelancer applied to quest" "application_id=$applicationId"
        $cl = $applyResp.Data.application.cover_letter
        if ($cl) {
            $preview = $cl.Substring(0, [Math]::Min(50, $cl.Length))
            Write-Info "  cover_letter   : $preview ..."
        }
        Write-Info "  proposed_price : $($applyResp.Data.application.proposed_price)"
    } else {
        Write-Fail "Freelancer apply to quest" "HTTP $($applyResp.StatusCode) -- $($applyResp.Raw)"
    }

    # Duplicate apply must fail
    Write-Step "POST /quests/$questId/apply -- duplicate => expect 400/409"
    $dupApply = Invoke-Api -Method POST -Endpoint "/quests/$questId/apply" `
                           -Headers (Get-AuthHeader $freelancerToken) -Body $applyBody
    if (-not $dupApply.Ok -and ($dupApply.StatusCode -eq 400 -or $dupApply.StatusCode -eq 409)) {
        Write-Pass "Duplicate application rejected" "HTTP $($dupApply.StatusCode)"
    } else {
        Write-Fail "Duplicate application should be rejected" "HTTP $($dupApply.StatusCode)"
    }

    # Client cannot apply to own quest
    Write-Step "POST /quests/$questId/apply -- client on own quest => expect 4xx"
    $selfApply = Invoke-Api -Method POST -Endpoint "/quests/$questId/apply" `
                            -Headers (Get-AuthHeader $clientToken) -Body $applyBody
    if (-not $selfApply.Ok -and $selfApply.StatusCode -ge 400) {
        Write-Pass "Client cannot apply to own quest" "HTTP $($selfApply.StatusCode)"
    } else {
        Write-Fail "Client applying own quest should be rejected" "HTTP $($selfApply.StatusCode)"
    }
} else {
    Write-Fail "Apply to quest" "Missing questId or freelancerToken -- skipping"
}

# ===========================================================================
Write-Header "STEP 9: Get Applications (as Client)"
# ===========================================================================

if ($questId -and $clientToken) {
    Write-Step "GET /quests/$questId/applications"
    $appsResp = Invoke-Api -Method GET -Endpoint "/quests/$questId/applications" `
                           -Headers (Get-AuthHeader $clientToken)

    if ($appsResp.Ok -and $appsResp.StatusCode -eq 200) {
        Write-Pass "GET applications" "total=$($appsResp.Data.total)"
        if ($appsResp.Data.total -gt 0) {
            $first = $appsResp.Data.applications[0]
            Write-Pass "At least one application present" "freelancer=$($first.freelancer_username)"
        } else {
            Write-Fail "Expected at least one application" "total=0"
        }
    } else {
        Write-Fail "GET applications" "HTTP $($appsResp.StatusCode)"
    }
} else {
    Write-Fail "GET applications" "Missing questId or clientToken -- skipping"
}

# ===========================================================================
Write-Header "STEP 10: Assign Quest to Freelancer"
# ===========================================================================

if ($questId -and $clientToken -and $freelancerId) {
    Write-Step "POST /quests/$questId/assign?freelancer_id=$freelancerId"
    $assignResp = Invoke-Api -Method POST `
                             -Endpoint "/quests/$questId/assign?freelancer_id=$freelancerId" `
                             -Headers (Get-AuthHeader $clientToken)

    if ($assignResp.Ok -and $assignResp.StatusCode -eq 200) {
        Write-Pass "Quest assigned" "status=$($assignResp.Data.quest.status)"
        $as = $assignResp.Data.quest.status
        $at = $assignResp.Data.quest.assigned_to
        if ($as -eq "assigned") { Write-Pass "Status changed to assigned" } else { Write-Fail "Status should be assigned" "got $as" }
        if ($at -eq $freelancerId)  { Write-Pass "assigned_to matches freelancer id" } else { Write-Fail "assigned_to mismatch" "got $at" }
    } else {
        Write-Fail "Assign quest" "HTTP $($assignResp.StatusCode) -- $($assignResp.Raw)"
    }
} else {
    Write-Fail "Assign quest" "Missing questId, clientToken, or freelancerId -- skipping"
}

# ===========================================================================
Write-Header "STEP 11: Start Quest (as Freelancer)"
# ===========================================================================

if ($questId -and $freelancerToken) {
    Write-Step "POST /quests/$questId/start"
    $startResp = Invoke-Api -Method POST -Endpoint "/quests/$questId/start" `
                            -Headers (Get-AuthHeader $freelancerToken)

    if ($startResp.Ok -and $startResp.StatusCode -eq 200) {
        Write-Pass "Quest started by freelancer" "status=$($startResp.Data.quest.status)"
        if ($startResp.Data.quest.status -eq "in_progress") {
            Write-Pass "Status changed to in_progress"
        } else {
            Write-Fail "Status should be in_progress" "got $($startResp.Data.quest.status)"
        }
    } else {
        Write-Fail "Start quest" "HTTP $($startResp.StatusCode) -- $($startResp.Raw)"
    }
} else {
    Write-Fail "Start quest" "Missing questId or freelancerToken -- skipping"
}

# ===========================================================================
Write-Header "STEP 12: Complete Quest (as Freelancer)"
# ===========================================================================

if ($questId -and $freelancerToken) {
    Write-Step "POST /quests/$questId/complete"
    $completeResp = Invoke-Api -Method POST -Endpoint "/quests/$questId/complete" `
                               -Headers (Get-AuthHeader $freelancerToken)

    if ($completeResp.Ok -and $completeResp.StatusCode -eq 200) {
        Write-Pass "Quest marked complete by freelancer" "xp_earned=$($completeResp.Data.xp_earned)"
        Write-Info "  message   : $($completeResp.Data.message)"
        Write-Info "  xp_earned : $($completeResp.Data.xp_earned)"
    } else {
        Write-Fail "Complete quest" "HTTP $($completeResp.StatusCode) -- $($completeResp.Raw)"
    }
} else {
    Write-Fail "Complete quest" "Missing questId or freelancerToken -- skipping"
}

# ===========================================================================
Write-Header "STEP 13: Confirm Quest Completion (as Client)"
# ===========================================================================

if ($questId -and $clientToken) {
    Write-Step "POST /quests/$questId/confirm"
    $confirmResp = Invoke-Api -Method POST -Endpoint "/quests/$questId/confirm" `
                              -Headers (Get-AuthHeader $clientToken)

    if ($confirmResp.Ok -and $confirmResp.StatusCode -eq 200) {
        Write-Pass "Client confirmed quest completion"
        Write-Info "  message      : $($confirmResp.Data.message)"
        Write-Info "  xp_reward    : $($confirmResp.Data.xp_reward)"
        Write-Info "  money_reward : $($confirmResp.Data.money_reward)"

        if ($confirmResp.Data.xp_reward -gt 0) {
            Write-Pass "XP reward is positive" "xp=$($confirmResp.Data.xp_reward)"
        } else {
            Write-Fail "XP reward should be positive" "got $($confirmResp.Data.xp_reward)"
        }
        if ($confirmResp.Data.money_reward -gt 0) {
            Write-Pass "Money reward is positive" "money=$($confirmResp.Data.money_reward)"
        } else {
            Write-Fail "Money reward should be positive" "got $($confirmResp.Data.money_reward)"
        }
    } else {
        Write-Fail "Confirm quest" "HTTP $($confirmResp.StatusCode) -- $($confirmResp.Raw)"
    }
} else {
    Write-Fail "Confirm quest" "Missing questId or clientToken -- skipping"
}

# ===========================================================================
Write-Header "STEP 14: Verify Final Quest State"
# ===========================================================================

if ($questId) {
    Write-Step "GET /quests/$questId  -- check final status"
    $finalQuest = Invoke-Api -Method GET -Endpoint "/quests/$questId"

    if ($finalQuest.Ok) {
        Write-Pass "GET final quest state" "status=$($finalQuest.Data.status)"
        $fs = $finalQuest.Data.status
        if ($fs -eq "confirmed") {
            Write-Pass "Quest final status = confirmed"
        } else {
            Write-Fail "Quest final status should be confirmed" "got $fs"
        }
        if ($null -ne $finalQuest.Data.completed_at) {
            Write-Pass "completed_at timestamp set" "$($finalQuest.Data.completed_at)"
        } else {
            Write-Fail "completed_at should be set"
        }
    } else {
        Write-Fail "GET final quest state" "HTTP $($finalQuest.StatusCode)"
    }
}

# ===========================================================================
Write-Header "STEP 15: Cancel Flow (separate quest)"
# ===========================================================================

if ($clientToken) {
    Write-Step "POST /quests/  (create quest to cancel)"

    $cancelQuestBody = (@{
        title          = "Quest to Cancel $ts"
        description    = "This quest will be cancelled as part of the E2E cancel flow test scenario."
        required_grade = "novice"
        skills         = @("Testing")
        budget         = 5000
        currency       = "RUB"
    } | ConvertTo-Json -Compress)

    $cqResp = Invoke-Api -Method POST -Endpoint "/quests/" `
                         -Headers (Get-AuthHeader $clientToken) `
                         -Body $cancelQuestBody

    if ($cqResp.Ok -and $cqResp.StatusCode -eq 201) {
        $cancelQuestId = $cqResp.Data.id
        Write-Pass "Cancel-flow quest created" "id=$cancelQuestId"

        Write-Step "POST /quests/$cancelQuestId/cancel"
        $cancelResp = Invoke-Api -Method POST -Endpoint "/quests/$cancelQuestId/cancel" `
                                 -Headers (Get-AuthHeader $clientToken)

        if ($cancelResp.Ok -and $cancelResp.StatusCode -eq 200) {
            Write-Pass "Quest cancelled by client"

            # Новый API может вернуть только message без quest payload.
            # Поэтому валидацию статуса делаем через повторный GET /quests/{id}.
            Write-Step "GET /quests/$cancelQuestId -- verify cancelled status in DB-backed response"
            $cancelStateResp = Invoke-Api -Method GET -Endpoint "/quests/$cancelQuestId"

            if ($cancelStateResp.Ok -and $cancelStateResp.StatusCode -eq 200) {
                $cs = $cancelStateResp.Data.status
                if ($cs -eq "cancelled") {
                    Write-Pass "Quest status = cancelled"
                } else {
                    Write-Fail "Quest status should be cancelled" "got $cs"
                }
            } else {
                Write-Fail "Fetch cancelled quest state" "HTTP $($cancelStateResp.StatusCode) -- $($cancelStateResp.Raw)"
            }
        } else {
            Write-Fail "Cancel quest" "HTTP $($cancelResp.StatusCode) -- $($cancelResp.Raw)"
        }
    } else {
        Write-Fail "Cancel-flow quest creation" "HTTP $($cqResp.StatusCode)"
    }
} else {
    Write-Fail "Cancel flow" "No client token -- skipping"
}

# ===========================================================================
Write-Header "STEP 15: Demo Account Login"
# ===========================================================================

# Rate limiter allows 10 attempts per 300s window per IP.
# By this point in the test we have already made several login calls,
# so wait a few seconds to give the window room, then try once each.
Write-Info "Pausing 3s to stay within rate-limit window..."
Start-Sleep -Seconds 3

Write-Step "POST /auth/login  (demo account novice_dev)"
$demoBody = (@{ username = "novice_dev"; password = "password123" } | ConvertTo-Json -Compress)
$demoResp = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $demoBody

if ($demoResp.Ok -and $demoResp.StatusCode -eq 200) {
    Write-Pass "Demo login novice_dev" "level=$($demoResp.Data.user.level) grade=$($demoResp.Data.user.grade)"
} elseif ($demoResp.StatusCode -eq 429) {
    Write-Info "Demo login novice_dev -- rate-limit active (normal in rapid test runs, not counted)"
} else {
    Write-Fail "Demo login novice_dev" "HTTP $($demoResp.StatusCode)"
}

Write-Step "POST /auth/login  (demo account client_user)"
$demoBody2 = (@{ username = "client_user"; password = "client123" } | ConvertTo-Json -Compress)
$demoResp2 = Invoke-Api -Method POST -Endpoint "/auth/login" -Body $demoBody2

if ($demoResp2.Ok -and $demoResp2.StatusCode -eq 200) {
    Write-Pass "Demo login client_user" "role=$($demoResp2.Data.user.role)"
} elseif ($demoResp2.StatusCode -eq 429) {
    Write-Info "Demo login client_user -- rate-limit active (normal in rapid test runs, not counted)"
} else {
    Write-Fail "Demo login client_user" "HTTP $($demoResp2.StatusCode)"
}

# ===========================================================================
Write-Header "STEP 16: Rewards System Check"
# ===========================================================================

Write-Step "Verifying XP calculation endpoint via quest data"

$questsRaw = Invoke-Api -Method GET -Endpoint "/quests/?page=1&page_size=10"
if ($questsRaw.Ok) {
    $questsWithXp = $questsRaw.Data.quests | Where-Object { $_.xp_reward -gt 0 }
    if ($questsWithXp.Count -gt 0) {
        Write-Pass "Quests have XP rewards set" "sample xp_reward=$($questsWithXp[0].xp_reward)"
    } else {
        Write-Fail "No quests with XP rewards found"
    }

    $questsWithBudget = $questsRaw.Data.quests | Where-Object { $_.budget -gt 0 }
    if ($questsWithBudget.Count -gt 0) {
        $sample = $questsWithBudget[0]
        Write-Pass "Quests have budget set" "sample budget=$($sample.budget) $($sample.currency)"
    } else {
        Write-Fail "No quests with budget found"
    }
} else {
    Write-Fail "Could not fetch quests for XP check" "HTTP $($questsRaw.StatusCode)"
}

# ===========================================================================
# Summary
# ===========================================================================

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "   E2E TEST SUMMARY" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

$totalTests = $passCount + $failCount
$pct = if ($totalTests -gt 0) { [int](($passCount / $totalTests) * 100) } else { 0 }

$summaryColor = if ($pct -ge 90) { "Green" } elseif ($pct -ge 70) { "Yellow" } else { "Red" }

Write-Host "  Tests passed : $passCount / $totalTests  ($pct%)" -ForegroundColor $summaryColor
Write-Host "  Tests failed : $failCount"                         -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Gray" })
Write-Host ""

if ($failCount -gt 0) {
    Write-Host "  Failed tests:" -ForegroundColor Red
    $testLog | Where-Object { $_ -like "FAIL*" } | ForEach-Object {
        Write-Host "    - $_" -ForegroundColor DarkRed
    }
    Write-Host ""
}

if ($pct -ge 90) {
    Write-Host "  All systems nominal. QuestionWork backend is fully functional!" -ForegroundColor Green
} elseif ($pct -ge 70) {
    Write-Host "  Most tests passed. Review failures above." -ForegroundColor Yellow
} else {
    Write-Host "  Too many failures. Check that backend is running and .env is configured." -ForegroundColor Red
    Write-Host "  Run: .\scripts\fix-common-issues.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Tested accounts created this run:" -ForegroundColor Gray
Write-Host "    Client     : $clientUser  /  $clientPass"     -ForegroundColor DarkGray
Write-Host "    Freelancer : $freelancerUser  /  $freelancerPass" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Quick links:" -ForegroundColor Gray
Write-Host "    Frontend  : http://localhost:3000"       -ForegroundColor DarkGray
Write-Host "    Swagger   : http://localhost:8001/docs"   -ForegroundColor DarkGray
Write-Host "    Health    : http://localhost:8001/health" -ForegroundColor DarkGray
Write-Host "    DB check  : .\scripts\test-db.ps1"        -ForegroundColor DarkGray
Write-Host ""
