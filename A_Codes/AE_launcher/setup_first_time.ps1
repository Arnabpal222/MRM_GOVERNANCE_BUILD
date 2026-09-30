# One-time setup on a new machine after `git clone` (e.g. the office laptop).
# Creates the Python environment, installs frontend packages and creates the start/stop shortcuts
# in this folder. Nothing is written outside the project folder.
#   powershell -ExecutionPolicy Bypass -File "A_Codes\AE_launcher\setup_first_time.ps1"
# Needs: Python 3.11+ and Node.js 20+ installed, and access to the Python (pip) and npm package registries.

$ErrorActionPreference = "Stop"
$codes    = Split-Path $PSScriptRoot -Parent
$backend  = Join-Path $codes "AB_backend"
$frontend = Join-Path $codes "AC_frontend"
$venvPy   = Join-Path $backend ".venv\Scripts\python.exe"

function Step([string]$text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Fail([string]$text) { Write-Host ""; Write-Host $text -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

Step "Finding Python 3.11 or newer"
$python = $null
foreach ($v in "3.14", "3.13", "3.12", "3.11") {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py "-$v" -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = @("py", "-$v"); break }
    }
}
if (-not $python -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { $python = @("python") }
}
if (-not $python) { Fail "Python 3.11 or newer was not found. Install it (python.org or your company software centre) and run this again." }
Write-Host "Using: $($python -join ' ')"

Step "Creating the Python environment (A_Codes\AB_backend\.venv)"
if (-not (Test-Path $venvPy)) {
    $pyArgs = @(if ($python.Count -gt 1) { $python[1..($python.Count - 1)] })
    & $python[0] @pyArgs -m venv (Join-Path $backend ".venv")
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment." }
} else { Write-Host "Already exists." }

Step "Installing Python packages"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r (Join-Path $backend "requirements-lock.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "Exact versions failed (often a different Python version); trying minimum versions..." -ForegroundColor Yellow
    & $venvPy -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Fail "pip could not install the packages. If your office uses a proxy, configure pip (pip config set global.proxy ...) and run this again." }
}

Step "Installing frontend packages (A_Codes\AC_frontend\node_modules)"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "Node.js (npm) is not installed. Install Node.js 20 or newer and run this again." }
Push-Location $frontend
npm ci --no-fund --no-audit
if ($LASTEXITCODE -ne 0) { npm install --no-fund --no-audit }
$ok = $LASTEXITCODE -eq 0
Pop-Location
if (-not $ok) { Fail "npm could not install the packages. If your office uses a proxy, configure npm (npm config set proxy ...) and run this again." }

Step "Creating local settings files from the examples"
foreach ($dir in (Join-Path $codes "AA_infra"), $backend) {
    $example = Join-Path $dir ".env.example"; $target = Join-Path $dir ".env"
    if ((Test-Path $example) -and -not (Test-Path $target)) { Copy-Item $example $target; Write-Host "Created $target" }
}

Step "Creating the start/stop shortcuts in A_Codes\AE_launcher"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "create_shortcuts.ps1")

Write-Host ""
Write-Host "Setup complete. Double-click 'MRM Governance MIS' in $PSScriptRoot to start." -ForegroundColor Green
Write-Host "The first start creates the database and loads the demo data (about 30 seconds)."
Read-Host "Press Enter to close"
