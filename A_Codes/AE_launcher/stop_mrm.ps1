# Stops the MRM Governance MIS: the processes listening on the backend (8000) and frontend (5173) ports,
# but only if they belong to this project's Python environment or Node.js.

$codes = Split-Path $PSScriptRoot -Parent
$python = (Join-Path $codes "AB_backend\.venv\Scripts\python.exe")
$stopped = 0

foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if (-not $p) { continue }
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)").CommandLine
        $ours = ($p.ProcessName -eq "node") -or ($cmd -and ($cmd -like "*uvicorn app.main:app*"))
        if ($ours) {
            Stop-Process -Id $p.Id -Force
            Write-Host "Stopped $($p.ProcessName) (PID $($p.Id)) on port $port"
            $stopped++
        } else {
            Write-Host "Port $port is used by $($p.ProcessName) (PID $($p.Id)), which is not part of MRM - left running." -ForegroundColor Yellow
        }
    }
}
# The minimised launcher windows close once their process has stopped.
if ($stopped -eq 0) { Write-Host "MRM Governance MIS was not running." }
Start-Sleep -Seconds 2
