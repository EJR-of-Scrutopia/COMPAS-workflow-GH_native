# Stops the hidden Bench Studio server launch.ps1 started, by PID.
#
# -NoPause exists for any caller that runs this from a script rather than
# a double-click, so it does not sit waiting on a Read-Host no one is
# going to answer.

param(
    [switch]$NoPause
)

function Wait-ForEnterUnlessNoPause {
    if (-not $NoPause) {
        Read-Host "Press Enter to close"
    }
}

$ErrorActionPreference = "Stop"
$stateDir = Join-Path $env:LOCALAPPDATA "BenchStudio"
$pidFile = Join-Path $stateDir "server.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "No server.pid found at $pidFile. Bench Studio does not look like it is running (or was stopped already)."
    Wait-ForEnterUnlessNoPause
    exit 0
}

$serverPid = (Get-Content -LiteralPath $pidFile -Raw).Trim()
$proc = Get-Process -Id $serverPid -ErrorAction SilentlyContinue

if (-not $proc) {
    Write-Host "PID $serverPid from server.pid is not running. Removing the stale pidfile."
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Wait-ForEnterUnlessNoPause
    exit 0
}

# Guard: only kill it if it is actually still a python process. server.pid
# is a plain text file outside our control once written; a PID can be
# reused by an unrelated process between the server exiting and this
# script running, and killing whatever now holds that number would be
# wrong. "python*", not "python": the real server shows up as python3.12
# (the venv stub is the one called plain python, and it is not the server).
if ($proc.ProcessName -notlike "python*") {
    Write-Host "PID $serverPid is running but is '$($proc.ProcessName)', not python. Not killing it (the PID was likely reused)."
    Write-Host "Removing the stale pidfile."
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Wait-ForEnterUnlessNoPause
    exit 0
}

Stop-Process -Id $serverPid -Force -Confirm:$false
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "Stopped Bench Studio (PID $serverPid) and removed server.pid."
Wait-ForEnterUnlessNoPause
