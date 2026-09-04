# Bench Studio launcher for this worktree. Starts the studio with no
# console of its own, waits until this run's own log says the server has
# bound, then opens the browser.
#
# There is deliberately no "already running, just open the browser" fast
# path here. The old launcher had one, and it is why the shortcut kept
# showing a stale studio: a stale server answers a port check perfectly
# well, so the fast path guaranteed the newest build could never be
# reached by double-clicking. The server takes the port back from any
# previous Bench Studio by itself (bench/studio/portcheck.py asks the
# holder to identify itself before stopping it), so the right launcher
# policy is: always start, let the server displace its predecessor.
#
# pythonw, not python, and the reason is a corpse that was found still
# warm: Start-Process with output redirects ignores -WindowStyle Hidden
# (that flag only applies on the ShellExecute path) and attaches the
# child to THIS console. Close the launcher's terminal -- by hand, or by
# it closing itself when the script ends -- and Windows kills the server
# with it. Measured live: the page and the library list loaded in the
# seconds the server was alive, then every thumbnail request hit a dead
# port and rendered as a broken image. pythonw is the GUI-subsystem
# interpreter: it has no console to inherit, so no terminal's fate is
# its fate, and the stdout/stderr redirects still capture its logs.
#
# -Quiet is for the silent shortcut (launcher/launch-quiet.vbs): nothing
# is printed anywhere, and a failure shows a message box instead of
# waiting on a Read-Host no one can see.

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

$venvPython = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $venvPython)) {
    # Fall back to the console interpreter rather than refusing to start;
    # it only costs the console-independence pythonw exists for.
    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
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
# that cannot be faked by the very server being replaced. (The err-log was
# watched for uvicorn's banner before, but under pythonw the stub does not
# always hand the stderr pipe through, and the banner never arrives.)
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
$serverProcess = Start-Process -FilePath $venvPython -ArgumentList "`"$servePy`"" `
    -WorkingDirectory $repoRoot -WindowStyle Hidden `
    -RedirectStandardOutput $logFile -RedirectStandardError $errFile -PassThru
Set-Content -LiteralPath $pidFile -Value $serverProcess.Id

$deadline = (Get-Date).AddSeconds(40)
$up = $false
while ((Get-Date) -lt $deadline) {
    $answering = Get-HealthPid $port
    if ($answering -and $answering -ne $previousPid) { $up = $true; break }
    if ($serverProcess.HasExited -and -not $answering) {
        # The stub exits once its child is up, so an exit alone is not a
        # failure; an exit with nothing answering is. Give the redirects a
        # beat to flush before reporting.
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
# the stub and orphans the actual server, which then squats on 8600 as
# the next "nothing has changed" mystery. netstat knows who owns it.
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
