# Creates (or repoints) the desktop shortcuts for THIS worktree:
#
#   Vaulted.lnk      -- wscript runs launch-quiet.vbs, which runs
#                       launch.ps1 with no window. Double-click
#                       "Launch Bench Studio.cmd" instead when the boot
#                       needs watching.
#   Stop Vaulted.lnk -- runs launcher/stop.ps1 in a small console that
#                       says what it stopped and waits for Enter. Start
#                       and stop are the same gesture now: one
#                       double-click each.
#
# Run this after moving the studio between checkouts and the shortcuts
# follow.

$repoRoot = Split-Path -Parent $PSScriptRoot
$quiet = Join-Path $repoRoot "launcher\launch-quiet.vbs"
$stopper = Join-Path $repoRoot "launcher\stop.ps1"
$icon = (Join-Path $repoRoot "launcher\vaulted.ico") + ",0"
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

$launchPath = Join-Path $desktop "Vaulted.lnk"
$launch = $shell.CreateShortcut($launchPath)
$launch.TargetPath = "C:\Windows\System32\wscript.exe"
$launch.Arguments = '"' + $quiet + '"'
$launch.WorkingDirectory = $repoRoot
$launch.IconLocation = $icon
$launch.Description = "Vaulted"
$launch.Save()

$stopPath = Join-Path $desktop "Stop Vaulted.lnk"
$stop = $shell.CreateShortcut($stopPath)
$stop.TargetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$stop.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $stopper + '"'
$stop.WorkingDirectory = $repoRoot
$stop.IconLocation = $icon
$stop.Description = "Stop the Vaulted server"
$stop.Save()

Write-Host "Shortcut created at $launchPath"
Write-Host "It points at $quiet"
Write-Host "Shortcut created at $stopPath"
Write-Host "It points at $stopper"
Read-Host "Press Enter to close"
