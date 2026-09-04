# Creates (or repoints) the desktop shortcut to "Launch Bench Studio.cmd"
# in THIS worktree. Run it after moving the studio between checkouts and
# the shortcut follows.

$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot "Launch Bench Studio.cmd"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Bench Studio.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $repoRoot
$shortcut.IconLocation = "shell32.dll,220"
$shortcut.Description = "Launch Bench Studio"
$shortcut.Save()

Write-Host "Shortcut created at $shortcutPath"
Write-Host "It points at $target"
Read-Host "Press Enter to close"
