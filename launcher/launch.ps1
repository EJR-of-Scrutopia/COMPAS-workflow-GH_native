# Bench Studio launcher for this worktree. Starts the server in a console
# that has NO WINDOW, waits until a fresh process answers on the port, then
# opens the browser.
#
# The architecture here is the residue of three measured failures, and each
# clause below closes one of them:
#
#   1. No "already running, just open the browser" fast path. A stale
#      server answers a port check perfectly well, so that path guaranteed
#      the newest build could never be reached by double-clicking. The
#      server takes the port back from any previous Bench Studio by itself
#      (bench/studio/portcheck.py); the launcher always starts.
#
#   2. The venv's CONSOLE python.exe, launched directly. Not pythonw: the
#      bootstrap (bench/demo/_bootstrap.py ensure_venv) hands a pythonw
#      process over to python.exe anyway, and that handover child allocated
#      a fresh VISIBLE console -- the terminal that kept popping up -- and
#      tied the server's life to it. Launching python.exe directly makes
#      ensure_venv a no-op: one process chain, no handover, no console of
#      its own.
#
#   3. CreateNoWindow via .NET, not Start-Process. PowerShell 5.1's
#      Start-Process silently drops -WindowStyle Hidden when redirects are
#      used and attaches the child to THIS console -- closing the terminal
#      then killed the studio mid-life (measured: page alive, every
#      thumbnail request hitting a dead port). CreateNoWindow gives the
#      child tree a windowless console: nothing to close, nothing to
#      inherit. The log redirection is done by cmd, so the server holds
#      real file handles, not pipes that fill or vanish with the launcher.
#
# -Quiet is for the silent shortcut (launcher/launch-quiet.vbs): nothing is
# printed anywhere, and a failure shows a message box instead of waiting on
# a Read-Host no one can see.

param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Fail([string]$message) {
    if ($Quiet) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(
            $message, "Bench Studio",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Warning)
    } else {
        Write-Host $message
        Read-Host "Press Enter to close"
    }
    exit 1
}

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Fail ("No Python environment at $venvPython.`n" +
        "This launcher belongs to the development worktree and expects its .venv to exist.")
}

$port = 8600

# Logs: one file per run, newest 10 kept, at %LOCALAPPDATA%\BenchStudio\logs.
# server.pid beside them is read by launcher/stop.ps1.
$stateDir = Join-Path $env:LOCALAPPDATA "BenchStudio"
$logDir = Join-Path $stateDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$logFile = Join-Path $logDir "server-$stamp.log"
$errFile = Join-Path $logDir "server-$stamp.err.log"
$pidFile = Join-Path $stateDir "server.pid"

# "server-*.log" also matches the ".err.log" companions, so filter those
# back out before counting or half as many runs as intended survive. Skip
# 9, not 10: this trim runs before today's log is written, so 9 old plus
# the new one lands on 10.
$existingLogs = Get-ChildItem -LiteralPath $logDir -Filter "server-*.log" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike "*.err.log" } |
    Sort-Object LastWriteTime -Descending
if ($existingLogs.Count -ge 10) {
    foreach ($stale in $existingLogs | Select-Object -Skip 9) {
        Remove-Item -LiteralPath $stale.FullName -Force -ErrorAction SilentlyContinue
        $staleErr = $stale.FullName -replace '\.log$', '.err.log'
        Remove-Item -LiteralPath $staleErr -Force -ErrorAction SilentlyContinue
    }
}

$servePy = Join-Path $repoRoot "bench\studio\serve.py"

# Who owns the port BEFORE this launch. Readiness below is "health answers
# from a different process than that": during a handover the old studio
# answers until the new one stops it, so the pid changing is the one signal
# that cannot be faked by the very server being replaced.
function Get-HealthPid([int]$onPort) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$onPort/api/health" -TimeoutSec 2
        if ($health.studio) { return [string]$health.pid }
    } catch { }
    return $null
}
$previousPid = Get-HealthPid $port

if (-not $Quiet) {
    Write-Host "Starting Bench Studio on port $port (logging to $logFile)..."
}
$redirect = '"' + $venvPython + '" "' + $servePy + '" > "' + $logFile + '" 2> "' + $errFile + '"'
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = Join-Path $env:SystemRoot "System32\cmd.exe"
$startInfo.Arguments = '/S /C " ' + $redirect + ' "'
$startInfo.WorkingDirectory = $repoRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$serverProcess = [System.Diagnostics.Process]::Start($startInfo)
Set-Content -LiteralPath $pidFile -Value $serverProcess.Id

$deadline = (Get-Date).AddSeconds(40)
$up = $false
while ((Get-Date) -lt $deadline) {
    $answering = Get-HealthPid $port
    if ($answering -and $answering -ne $previousPid) { $up = $true; break }
    if ($serverProcess.HasExited -and -not $answering) {
        # cmd waits on python, so an exited cmd with nothing answering is a
        # failed boot. Give the redirects a beat to flush, look once more,
        # then report.
        Start-Sleep -Milliseconds 700
        if (-not (Get-HealthPid $port)) { break }
    }
    Start-Sleep -Milliseconds 400
}

if (-not $up) {
    $report = "Bench Studio did not come up on port $port within 40 seconds.`n" +
        "The log says why: $logFile"
    foreach ($f in @($logFile, $errFile)) {
        if ((Test-Path $f) -and (Get-Item $f).Length -gt 0) {
            $tail = (Get-Content -LiteralPath $f -Tail 12) -join "`n"
            $report += "`n--- last lines of $(Split-Path -Leaf $f) ---`n$tail"
        }
    }
    Fail $report
}

# server.pid must hold the process that OWNS the port, or stop.ps1 kills
# the wrong link of the chain and orphans the actual server, which then
# squats on 8600 as the next "nothing has changed" mystery. netstat knows.
$listenerPid = $null
foreach ($line in (netstat -ano -p TCP | Select-String "LISTENING")) {
    $parts = $line.Line.Trim() -split "\s+"
    if ($parts[1] -match ":$port$") { $listenerPid = $parts[-1]; break }
}
if ($listenerPid) { Set-Content -LiteralPath $pidFile -Value $listenerPid }

Start-Process "http://127.0.0.1:$port"
if (-not $Quiet) {
    Write-Host "Bench Studio is up on http://127.0.0.1:$port (server PID $listenerPid). Log: $logFile"
}
