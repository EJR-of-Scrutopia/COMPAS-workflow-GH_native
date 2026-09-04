# Creates (or repoints) the desktop shortcut to the SILENT launcher in
# THIS worktree: wscript runs launch-quiet.vbs, which runs launch.ps1
# with no window. Double-click "Launch Bench Studio.cmd" instead when
# the boot needs watching. Run this after moving the studio between
# checkouts and the shortcut follows.

$repoRoot = Split-Path -Parent $PSScriptRoot
$quiet = Join-Path $repoRoot "launcher\launch-quiet.vbs"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Vaulted.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "C:\Windows\System32\wscript.exe"
$shortcut.Arguments = '"' + $quiet + '"'
$shortcut.WorkingDirectory = $repoRoot
$shortcut.IconLocation = (Join-Path $repoRoot "launcher\vaulted.ico") + ",0"
$shortcut.Description = "Vaulted"
$shortcut.Save()

Write-Host "Shortcut created at $shortcutPath"
Write-Host "It points at $target"
Read-Host "Press Enter to close"
