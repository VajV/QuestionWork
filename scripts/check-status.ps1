# QuestionWork -- Check Status
# Comprehensive health check for all project components
# Compatible with PowerShell 5+ and ASCII-safe

param(
    [switch]$SkipDocker
)

$ErrorActionPreference = "SilentlyContinue"

$ROOT         = Split-Path -Parent $PSScriptRoot
$BACKEND_DIR  = Join-Path $ROOT "backend"
$FRONTEND_DIR = Join-Path $ROOT "frontend"

$totalChecks  = 0
$passedChecks = 0
$hardFailedChecks = 0

function Write-Check {
    param(
        [string]$Label,
        [bool]$Ok,
        [string]$Detail = "",
        [bool]$IsWarn   = $false
    )
    $script:totalChecks++
    if ($Ok) {
        $script:passedChecks++
        Write-Host "  ✅ PASS  $Label" -ForegroundColor Green -NoNewline
    } elseif ($IsWarn) {
        Write-Host "  ⚠️ WARN  $Label" -ForegroundColor Yellow -NoNewline
    } else {
        $script:hardFailedChecks++
        Write-Host "  ❌ FAIL  $Label" -ForegroundColor Red -NoNewline
    }
    if ($Detail) {
        Write-Host "  -- $Detail" -ForegroundColor Gray
    } else {
        Write-Host ""
    }
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "  === $Title ===" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Port {
    param([int]$Port)
    $conn = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port `
                -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $conn.TcpTestSucceeded
}

function Invoke-ApiGet {
    param([string]$Url, [int]$TimeoutSec = 4)
    try {
        $resp = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec `
                    -UseBasicParsing -ErrorAction Stop
        return $resp
    } catch {
        return $null
    }
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host "   QuestionWork -- Status Check" -ForegroundColor Cyan
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd  HH:mm:ss')" -ForegroundColor Cyan
Write-Host "  ============================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Project Structure
# ---------------------------------------------------------------------------

Write-Section "1. Project Structure"

Write-Check "Root directory exists"    (Test-Path -LiteralPath $ROOT)         $ROOT
Write-Check "Backend directory"        (Test-Path -LiteralPath $BACKEND_DIR)  $BACKEND_DIR
Write-Check "Frontend directory"       (Test-Path -LiteralPath $FRONTEND_DIR) $FRONTEND_DIR
Write-Check "Scripts directory"        (Test-Path -LiteralPath (Join-Path $ROOT "scripts"))
Write-Check "Backend .env file"        (Test-Path -LiteralPath (Join-Path $BACKEND_DIR ".env"))       "backend\.env"
Write-Check "Frontend .env.local"      (Test-Path -LiteralPath (Join-Path $FRONTEND_DIR ".env.local")) "frontend\.env.local"
Write-Check "Backend requirements.txt" (Test-Path -LiteralPath (Join-Path $BACKEND_DIR "requirements.txt"))
Write-Check "Frontend package.json"    (Test-Path -LiteralPath (Join-Path $FRONTEND_DIR "package.json"))
Write-Check "CHECKLIST.md"             (Test-Path -LiteralPath (Join-Path $ROOT "CHECKLIST.md"))

# ---------------------------------------------------------------------------
# 2. Python / venv
# ---------------------------------------------------------------------------

Write-Section "2. Python Environment"

$venvActivate = Join-Path $BACKEND_DIR ".venv\Scripts\activate.ps1"
$venvPython   = Join-Path $BACKEND_DIR ".venv\Scripts\python.exe"
$venvUvicorn  = Join-Path $BACKEND_DIR ".venv\Scripts\uvicorn.exe"

Write-Check "Python venv exists"       (Test-Path -LiteralPath $venvActivate) ".venv\Scripts\activate.ps1"
Write-Check "Python executable"        (Test-Path -LiteralPath $venvPython)   $venvPython
Write-Check "Uvicorn installed"        (Test-Path -LiteralPath $venvUvicorn)  $venvUvicorn

$packagesToCheck = @("fastapi", "uvicorn", "pydantic", "python_jose", "bcrypt", "asyncpg")
foreach ($pkg in $packagesToCheck) {
    $sitePackages = Join-Path $BACKEND_DIR ".venv\Lib\site-packages"
    $found = $false
    if (Test-Path -LiteralPath $sitePackages) {
        $found = [bool](Get-ChildItem $sitePackages -Filter "${pkg}*" -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
    Write-Check "Package: $pkg" $found
}

# ---------------------------------------------------------------------------
# 3. Node.js / Frontend Dependencies
# ---------------------------------------------------------------------------

Write-Section "3. Node.js / Frontend Dependencies"

$nodeModules  = Join-Path $FRONTEND_DIR "node_modules"
$nextBin      = Join-Path $FRONTEND_DIR "node_modules\.bin\next"

$nodeModsCount = 0
if (Test-Path -LiteralPath $nodeModules) {
    $nodeModsCount = (Get-ChildItem $nodeModules -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
}

Write-Check "node_modules exists"      (Test-Path -LiteralPath $nodeModules)  "$nodeModsCount packages"
Write-Check "next binary present"      (Test-Path -LiteralPath $nextBin)
Write-Check "tailwindcss installed"    (Test-Path -LiteralPath (Join-Path $nodeModules "tailwindcss"))
Write-Check "framer-motion installed"  (Test-Path -LiteralPath (Join-Path $nodeModules "framer-motion"))
Write-Check "typescript installed"     (Test-Path -LiteralPath (Join-Path $nodeModules "typescript"))

# ---------------------------------------------------------------------------
# 4. Backend API
# ---------------------------------------------------------------------------

Write-Section "4. Backend API (http://localhost:8000)"

$backendPort = Test-Port 8000
Write-Check "Port 8000 is listening" $backendPort "uvicorn"

if ($backendPort) {
    $health = Invoke-ApiGet "http://localhost:8000/health"
    Write-Check "GET /health -- 200"      ($health -and $health.StatusCode -eq 200)

    $swagger = Invoke-ApiGet "http://localhost:8000/docs"
    Write-Check "GET /docs -- 200"        ($swagger -and $swagger.StatusCode -eq 200)

    $openapi = Invoke-ApiGet "http://localhost:8000/openapi.json"
    Write-Check "GET /openapi.json"       ($openapi -and $openapi.StatusCode -eq 200)

    # Auth register endpoint (400 = already exists = endpoint is alive)
    $regBody = '{"username":"__sc__","email":"sc@sc.sc","password":"StatusCheck1!","role":"freelancer"}'
    $regOk   = $false
    try {
        $regResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/register" `
                       -Method POST -Body $regBody -ContentType "application/json" `
                       -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        $regOk = ($regResp.StatusCode -eq 201)
    } catch {
        $code  = $_.Exception.Response.StatusCode.Value__
        $regOk = ($code -eq 400 -or $code -eq 409 -or $code -eq 201)
    }
    Write-Check "POST /api/v1/auth/register reachable" $regOk

    # Login with demo account
    $loginBody  = '{"username":"novice_dev","password":"password123"}'
    $loginOk    = $false
    $demoToken  = $null
    try {
        $loginResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" `
                         -Method POST -Body $loginBody -ContentType "application/json" `
                         -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        $loginData = $loginResp.Content | ConvertFrom-Json
        $loginOk   = ($loginResp.StatusCode -eq 200) -and ($null -ne $loginData.access_token)
        $demoToken = $loginData.access_token
    } catch {
        $loginOk  = $false
        $demoToken = $null
    }
    Write-Check "POST /api/v1/auth/login (novice_dev)" $loginOk

    # Quests list
    $questsResp = Invoke-ApiGet "http://localhost:8000/api/v1/quests/?page=1"
    $questsOk   = ($null -ne $questsResp) -and ($questsResp.StatusCode -eq 200)
    $questCount = 0
    if ($questsOk) {
        try {
            $qData      = $questsResp.Content | ConvertFrom-Json
            $questCount = $qData.total
        } catch {}
    }
    Write-Check "GET /api/v1/quests/" $questsOk "$questCount quests in memory"

    # Users list (requires auth since Week 2 hardening)
    $usersOk = $false
    if ($demoToken) {
        try {
            $authHeaders2 = @{ Authorization = "Bearer $demoToken" }
            $usersAuth = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/users/" `
                             -Headers $authHeaders2 -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            $usersOk = ($usersAuth.StatusCode -eq 200)
        } catch {
            $usersOk = $false
        }
        Write-Check "GET /api/v1/users/ (auth)" $usersOk
    } else {
        # No demo token -- just confirm endpoint responds (401 is correct behaviour)
        $usersNoAuth = $null
        try {
            Invoke-WebRequest -Uri "http://localhost:8000/api/v1/users/" `
                -UseBasicParsing -TimeoutSec 4 -ErrorAction Stop | Out-Null
        } catch {
            $usersNoAuth = $_.Exception.Response.StatusCode.Value__
        }
        $usersOk = ($usersNoAuth -eq 401)
        Write-Check "GET /api/v1/users/ reachable (401 expected)" $usersOk
    }

    # Authenticated request
    if ($demoToken) {
        $protectedOk = $false
        try {
            $authHeaders = @{ Authorization = "Bearer $demoToken" }
            $protResp    = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/quests/" `
                               -Headers $authHeaders -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            $protectedOk = ($protResp.StatusCode -eq 200)
        } catch {
            $protectedOk = $false
        }
        Write-Check "Authenticated request (JWT Bearer)" $protectedOk "token accepted"
    }

} else {
    Write-Host "  [INFO] Backend not running -- skipping API checks" -ForegroundColor DarkGray
    Write-Host "         Start: cd backend ; .venv\Scripts\activate ; uvicorn app.main:app --reload" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 5. Frontend
# ---------------------------------------------------------------------------

Write-Section "5. Frontend (http://localhost:3000)"

$frontendPort = Test-Port 3000
Write-Check "Port 3000 is listening" $frontendPort "Next.js"

if ($frontendPort) {
    $pages = @(
        @{ Url = "http://localhost:3000";                  Label = "GET / (homepage)" },
        @{ Url = "http://localhost:3000/auth/login";       Label = "GET /auth/login" },
        @{ Url = "http://localhost:3000/auth/register";    Label = "GET /auth/register" },
        @{ Url = "http://localhost:3000/quests";           Label = "GET /quests" },
        @{ Url = "http://localhost:3000/quests/create";    Label = "GET /quests/create" },
        @{ Url = "http://localhost:3000/marketplace";      Label = "GET /marketplace" },
        @{ Url = "http://localhost:3000/profile";          Label = "GET /profile" }
    )

    foreach ($page in $pages) {
        $resp = Invoke-ApiGet $page.Url 5
        Write-Check $page.Label ($null -ne $resp -and $resp.StatusCode -eq 200)
    }
} else {
    Write-Host "  [INFO] Frontend not running -- skipping page checks" -ForegroundColor DarkGray
    Write-Host "         Start: cd frontend ; npm run dev" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 6. Docker / Infrastructure
# ---------------------------------------------------------------------------

Write-Section "6. Docker / Infrastructure"

if ($SkipDocker) {
    Write-Check "Docker checks skipped" $true "SkipDocker flag enabled" -IsWarn:$true
} else {

$dockerRunning = $false
try {
    docker info 2>&1 | Out-Null
    $dockerRunning = ($LASTEXITCODE -eq 0)
} catch {
    $dockerRunning = $false
}
Write-Check "Docker Desktop running" $dockerRunning

if ($dockerRunning) {
    $containers = docker ps --format "{{.Names}}" 2>&1

    $redisName = $null
    if (($containers | Where-Object { $_ -eq "questionwork_redis" }).Count -gt 0) {
        $redisName = "questionwork_redis"
    } elseif (($containers | Where-Object { $_ -eq "questionwork-redis" }).Count -gt 0) {
        $redisName = "questionwork-redis"
    }

    $postgresName = $null
    if (($containers | Where-Object { $_ -eq "questionwork_postgres" }).Count -gt 0) {
        $postgresName = "questionwork_postgres"
    } elseif (($containers | Where-Object { $_ -eq "questionwork_db" }).Count -gt 0) {
        $postgresName = "questionwork_db"
    } elseif (($containers | Where-Object { $_ -eq "questionwork-postgres" }).Count -gt 0) {
        $postgresName = "questionwork-postgres"
    }

    $redisUp    = ($null -ne $redisName)
    $postgresUp = ($null -ne $postgresName)

    Write-Check "Redis container"      $redisUp    "port 6379"
    Write-Check "PostgreSQL container" $postgresUp "port 5432"

    if ($redisUp) {
        try {
            $ping = docker exec $redisName redis-cli ping 2>&1
            Write-Check "Redis PING response" ($ping -eq "PONG") "$ping"
        } catch {
            Write-Check "Redis PING response" $false "exec failed"
        }
    }
} else {
    Write-Host "  [INFO] Docker not running -- skipping container checks" -ForegroundColor DarkGray
}
}

# ---------------------------------------------------------------------------
# 7. Configuration
# ---------------------------------------------------------------------------

Write-Section "7. Configuration"

$backendEnvPath = Join-Path $BACKEND_DIR ".env"
if (Test-Path -LiteralPath $backendEnvPath) {
    $envTxt = Get-Content $backendEnvPath -Raw

    Write-Check "SECRET_KEY is set"         ($envTxt -match "SECRET_KEY=.{8,}")
    Write-Check "FRONTEND_URL configured"   ($envTxt -match "FRONTEND_URL=http://localhost:3000")
    Write-Check "DATABASE_URL present"      ($envTxt -match "DATABASE_URL=")
    Write-Check "JWT_ALGORITHM=HS256"       ($envTxt -match "JWT_ALGORITHM=HS256")
} else {
    Write-Check "backend\.env readable" $false "file not found"
}

$frontendEnvPath = Join-Path $FRONTEND_DIR ".env.local"
if (Test-Path -LiteralPath $frontendEnvPath) {
    $feTxt = Get-Content $frontendEnvPath -Raw
    Write-Check "NEXT_PUBLIC_API_URL set" ($feTxt -match "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1")
} else {
    Write-Check "frontend\.env.local readable" $false "file not found"
}

# ---------------------------------------------------------------------------
# 8. Key Source Files
# ---------------------------------------------------------------------------

Write-Section "8. Key Source Files"

$sourceFiles = @(
    @{ Path = "backend\app\main.py";                         Label = "Backend: main.py" },
    @{ Path = "backend\app\api\v1\api.py";                   Label = "Backend: api router" },
    @{ Path = "backend\app\api\v1\endpoints\auth.py";        Label = "Backend: auth endpoint" },
    @{ Path = "backend\app\api\v1\endpoints\quests.py";      Label = "Backend: quests endpoint" },
    @{ Path = "backend\app\api\v1\endpoints\users.py";       Label = "Backend: users endpoint" },
    @{ Path = "backend\app\core\security.py";                Label = "Backend: security (JWT)" },
    @{ Path = "backend\app\core\rewards.py";                 Label = "Backend: rewards (XP)" },
    @{ Path = "backend\app\models\user.py";                  Label = "Backend: user models" },
    @{ Path = "backend\app\models\quest.py";                 Label = "Backend: quest models" },
    @{ Path = "frontend\src\app\page.tsx";                   Label = "Frontend: homepage" },
    @{ Path = "frontend\src\app\auth\login\page.tsx";        Label = "Frontend: login" },
    @{ Path = "frontend\src\app\auth\register\page.tsx";     Label = "Frontend: register" },
    @{ Path = "frontend\src\app\quests\page.tsx";            Label = "Frontend: quests list" },
    @{ Path = "frontend\src\app\quests\create\page.tsx";     Label = "Frontend: create quest" },
    @{ Path = "frontend\src\app\quests\[id]\page.tsx";       Label = "Frontend: quest detail" },
    @{ Path = "frontend\src\app\marketplace\page.tsx";       Label = "Frontend: marketplace" },
    @{ Path = "frontend\src\app\profile\page.tsx";           Label = "Frontend: profile" },
    @{ Path = "frontend\src\context\AuthContext.tsx";        Label = "Frontend: AuthContext" },
    @{ Path = "frontend\src\lib\api.ts";                     Label = "Frontend: API client" }
)

foreach ($f in $sourceFiles) {
    $full = Join-Path $ROOT $f.Path
    Write-Check $f.Label (Test-Path -LiteralPath $full)
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  ============================================" -ForegroundColor Cyan
Write-Host ""

$failedChecks = $totalChecks - $passedChecks
$percent      = if ($totalChecks -gt 0) { [int](($passedChecks / $totalChecks) * 100) } else { 0 }

$summaryColor = if ($percent -ge 90) { "Green" } elseif ($percent -ge 60) { "Yellow" } else { "Red" }

Write-Host "  Checks passed : $passedChecks / $totalChecks  ($percent%)" -ForegroundColor $summaryColor

if ($failedChecks -gt 0) {
    Write-Host "  Failed checks : $failedChecks" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Run  .\scripts\fix-common-issues.ps1  to auto-fix common problems." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "  All checks passed! QuestionWork is healthy." -ForegroundColor Green
}

Write-Host ""
Write-Host "  Quick links:" -ForegroundColor Gray
Write-Host "    Frontend  : http://localhost:3000"       -ForegroundColor DarkGray
Write-Host "    Backend   : http://localhost:8000"       -ForegroundColor DarkGray
Write-Host "    Swagger   : http://localhost:8000/docs"  -ForegroundColor DarkGray
Write-Host "    Health    : http://localhost:8000/health" -ForegroundColor DarkGray
Write-Host ""

# Deterministic exit code for CI
if ($hardFailedChecks -gt 0) {
    exit 1
}

exit 0
