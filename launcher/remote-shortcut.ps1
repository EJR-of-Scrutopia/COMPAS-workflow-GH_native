# Creates the Vaulted shortcut on a REMOTE device -- a laptop or any other
# Windows machine on the tailnet. One double-click opens an Edge app
# window (no tabs, its own taskbar entry, feels like an installed app) on
# the /start page, which starts the studio on the desktop if it is asleep
# and hands over to it the moment it answers. Stopping lives inside the
# page: the Stop server button in the panel foot.
#
# Ship this script together with vaulted.ico to a folder on the device
# (scp does it) and run it there once. It is idempotent: running it again
# just repoints the shortcut.

param(
    [string]$Url = "https://edwards-desktop.tailb66524.ts.net:8443/start"
)

# Any Chromium browser can open an app window; take the first one this
# device has. Edwards-laptop-1 runs a per-user Brave, which is why the
# LocalAppData paths are on the list.
$browsers = @(
    (Join-Path ${env:ProgramFiles(x86)} "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:ProgramFiles "Microsoft\Edge\Application\msedge.exe"),
    (Join-Path $env:LOCALAPPDATA "BraveSoftware\Brave-Browser\Application\brave.exe"),
    (Join-Path $env:ProgramFiles "BraveSoftware\Brave-Browser\Application\brave.exe"),
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path $env:LOCALAPPDATA "Google\Chrome\Application\chrome.exe")
)
$browser = $browsers | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) {
    Write-Host "No app-window browser found; the shortcut will open the default browser instead."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop "Vaulted.lnk"))
if ($browser) {
    $shortcut.TargetPath = $browser
    $shortcut.Arguments = "--app=$Url"
} else {
    $shortcut.TargetPath = $Url
}
$icon = Join-Path $PSScriptRoot "vaulted.ico"
if (Test-Path $icon) {
    $shortcut.IconLocation = "$icon,0"
}
$shortcut.Description = "Vaulted, served from the studio desktop"
$shortcut.Save()

Write-Host "Shortcut created at $(Join-Path $desktop 'Vaulted.lnk')"
Write-Host "It opens $Url"
