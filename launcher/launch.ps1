# Bench Studio launcher for this worktree. Starts the studio hidden with
# a rotating log file, waits until the new process itself answers on the
# port, then opens the browser.
#
# There is deliberately no "already running, just open the browser" fast
# path here. The old launcher had one, and it is why the shortcut kept
# showing a stale studio: a stale server answers the port check perfectly
# well, so the fast path guaranteed the newest build could never be
# reached by double-clicking. The server now takes the port back from any
# previous Bench Studio by itself (bench/studio/portcheck.py asks the
# holder to identify itself before stopping it), so the right launcher
# policy is: always start, let the server displace its predecessor.
#
# Hiding mechanism carried over from the previous launcher, where it was
# confirmed empirically on this machine (Windows 11, Windows Terminal as
# default): -WindowStyle Hidden genuinely produces no window when started
# from a script (the Task Scheduler gotcha does not apply here), and the
# stdout/stderr redirects still capture the child's output.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No Python environment at $venvPython."
    Write-Host "This launcher belongs to the development worktree and expects its .venv to exist."
    Read-Host "Press Enter to close"
    exit 1
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
Write-Host "Starting Bench Studio on port $port (hidden; logging to $logFile)..."
$serverProcess = Start-Process -FilePath $venvPython -ArgumentList "`"$servePy`"" `
    -WorkingDirectory $repoRoot -WindowStyle Hidden `
    -RedirectStandardOutput $logFile -RedirectStandardError $errFile -PassThru
Set-Content -LiteralPath $pidFile -Value $serverProcess.Id

# Wait for THIS run's own log to say the server has bound. Not "the port
# answers" (during a handover the OLD studio still answers until the new
# one stops it), and not a pid match against $serverProcess (on Windows a
# venv's python.exe is a stub that runs the real interpreter as a child,
# so the pid that binds the port is never the pid Start-Process returned;
# measured here: stub 56296 waiting, server 62352 on the port). The log
# file is stamped per run, so its "Uvicorn running" line can only mean
# this launch succeeded. uvicorn logs to stderr, hence $errFile.
$deadline = (Get-Date).AddSeconds(40)
$up = $false
while ((Get-Date) -lt $deadline) {
    if (Test-Path $errFile) {
        $said = Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue
        if ($said -match "Uvicorn running on") { $up = $true; break }
    }
    if ($serverProcess.HasExited) {
        # Exited without binding: portcheck refused, or the boot failed.
        # Give the redirects a beat to flush before reporting.
        Start-Sleep -Milliseconds 300
        break
    }
    Start-Sleep -Milliseconds 400
}

if (-not $up) {
    Write-Host "Bench Studio did not come up on port $port within 40 seconds."
    Write-Host "The log says why: $logFile"
    foreach ($f in @($logFile, $errFile)) {
        if ((Test-Path $f) -and (Get-Item $f).Length -gt 0) {
            Write-Host "--- last lines of $(Split-Path -Leaf $f) ---"
            Get-Content -LiteralPath $f -Tail 15
        }
    }
    Read-Host "Press Enter to close"
    exit 1
}

# server.pid must hold the process that OWNS the port, or stop.ps1 kills
# the stub and orphans the actual server, which then squats on 8600 as
# the next "nothing has changed" mystery. netstat knows who owns it.
$listenerPid = $null
foreach ($line in (netstat -ano -p TCP | Select-String "LISTENING")) {
    $parts = $line.Line.Trim() -split "\s+"
    if ($parts[1] -match ":$port$") { $listenerPid = $parts[-1]; break }
}
if ($listenerPid) { Set-Content -LiteralPath $pidFile -Value $listenerPid }

Start-Process "http://127.0.0.1:$port"
Write-Host "Bench Studio is up on http://127.0.0.1:$port (server PID $listenerPid). Log: $logFile"
