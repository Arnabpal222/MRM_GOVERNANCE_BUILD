# Starts the MRM Governance MIS (backend + frontend) and opens it in the browser.
# Development mode: SQLite database and local file storage under AB_backend\var (no Docker needed).
# First run creates the database and loads the 256-model seed (about 30 seconds).
# Used by the "MRM Governance MIS" desktop shortcut; safe to run again while it is already running.

$ErrorActionPreference = "Stop"
$codes    = Split-Path $PSScriptRoot -Parent          # ...\A_Codes
$backend  = Join-Path $codes "AB_backend"
$frontend = Join-Path $codes "AC_frontend"
$python   = Join-Path $backend ".venv\Scripts\python.exe"
$var      = Join-Path $backend "var"
$url      = "http://localhost:5173"
$host.UI.RawUI.WindowTitle = "MRM Governance MIS - starting"

function Test-Port([int]$port) {
    [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Url([string]$u, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try { Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 5 | Out-Null; return $true } catch { Start-Sleep -Milliseconds 700 }
    }
    return $false
}

function Fail([string]$message) {
    Write-Host ""
    Write-Host $message -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "MRM Governance MIS" -ForegroundColor Cyan
if (-not (Test-Path $python)) { Fail "Python environment not found at $python. See A_Codes\README.md (first run)." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "Node.js (npm) is not installed or not on PATH." }

# Development settings, inherited by the processes started below.
New-Item -ItemType Directory -Force $var | Out-Null
$env:MRM_DATABASE_URL    = "sqlite:///" + ((Join-Path $var "dev.db") -replace '\\', '/')
$env:MRM_STORAGE_BACKEND = "local"
$env:MRM_LOCAL_STORAGE_DIR = Join-Path $var "object_store"

# --- backend ------------------------------------------------------------------------------
if (Test-Port 8000) {
    Write-Host "Backend already running on port 8000."
} else {
    if (-not (Test-Path (Join-Path $var "dev.db"))) {
        Write-Host "First run: creating the database and loading the seed (about 30 seconds)..." -ForegroundColor Yellow
        Push-Location $backend
        try {
            & $python -c "from app.db import engine; from app.models import Base; Base.metadata.create_all(engine)"
            if ($LASTEXITCODE -ne 0) { throw "Database creation failed." }
            & $python -m app.cli reset
            if ($LASTEXITCODE -ne 0) { throw "Loading the seed failed." }
        } catch { Pop-Location; Fail $_ }
        Pop-Location
    }
    Write-Host "Starting backend (minimised window 'MRM backend')..."
    Start-Process powershell -WorkingDirectory $backend -WindowStyle Minimized -ArgumentList @(
        "-NoProfile", "-Command",
        "`$host.UI.RawUI.WindowTitle='MRM backend - close to stop'; & '$python' -m uvicorn app.main:app --port 8000")
}

# --- frontend -----------------------------------------------------------------------------
if (Test-Port 5173) {
    Write-Host "Frontend already running on port 5173."
} else {
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "First run: installing frontend packages..." -ForegroundColor Yellow
        Push-Location $frontend; npm install --no-fund --no-audit; Pop-Location
    }
    Write-Host "Starting frontend (minimised window 'MRM frontend')..."
    Start-Process powershell -WorkingDirectory $frontend -WindowStyle Minimized -ArgumentList @(
        "-NoProfile", "-Command", "`$host.UI.RawUI.WindowTitle='MRM frontend - close to stop'; npm run dev")
}

Write-Host "Waiting for the application..."
if (-not (Wait-Url "http://127.0.0.1:8000/api/health/live" 90)) { Fail "The backend did not start. Open the 'MRM backend' window to see the error." }
if (-not (Wait-Url $url 60)) { Fail "The frontend did not start. Open the 'MRM frontend' window to see the error." }

Write-Host "Ready - opening $url" -ForegroundColor Green
Start-Process $url
Start-Sleep -Seconds 2
