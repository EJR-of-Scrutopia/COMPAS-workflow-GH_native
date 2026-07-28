[CmdletBinding()]
param(
    [string] $InstallPath = (
        Join-Path $env:APPDATA "Grasshopper\Libraries\Ananke_COMPAS"
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\..")
)
$projectPath = Join-Path $PSScriptRoot "Ananke.COMPAS.csproj"
$configuration = "Release"
$targetFramework = "net48"
$assemblySource = Join-Path $PSScriptRoot (
    "bin\$configuration\$targetFramework\Ananke.COMPAS.gha"
)

& dotnet build $projectPath -c $configuration --nologo
if ($LASTEXITCODE -ne 0) {
    throw "The Ananke COMPAS Grasshopper build failed."
}

if (-not (Test-Path -LiteralPath $assemblySource -PathType Leaf)) {
    throw "The build did not produce the expected .gha: $assemblySource"
}

[void][System.Reflection.AssemblyName]::GetAssemblyName($assemblySource)

New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
$assemblyDestination = Join-Path $InstallPath "Ananke.COMPAS.gha"
Copy-Item -LiteralPath $assemblySource -Destination $assemblyDestination -Force

$pythonDestination = Join-Path $InstallPath "python"
New-Item -ItemType Directory -Path $pythonDestination -Force | Out-Null

foreach ($packageName in @("ananke_equilibrium", "tree_forest_compas")) {
    $sourceRoot = Join-Path $repositoryRoot ("src\" + $packageName)
    $targetRoot = Join-Path $pythonDestination $packageName
    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null

    foreach (
        $file in Get-ChildItem `
            -LiteralPath $sourceRoot `
            -Recurse `
            -File `
            -Filter "*.py"
    ) {
        $relativePath = $file.FullName.Substring(
            $sourceRoot.Length
        ).TrimStart("\")
        $destination = Join-Path $targetRoot $relativePath
        New-Item `
            -ItemType Directory `
            -Path (Split-Path -Parent $destination) `
            -Force |
            Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
}

$iconSource = Join-Path $repositoryRoot "plugin\icons"
$iconDestination = Join-Path $InstallPath "icons"
New-Item -ItemType Directory -Path $iconDestination -Force | Out-Null
Get-ChildItem -LiteralPath $iconSource -File -Filter "*.png" |
    ForEach-Object {
        Copy-Item `
            -LiteralPath $_.FullName `
            -Destination $iconDestination `
            -Force
    }

Unblock-File -LiteralPath $assemblyDestination -ErrorAction SilentlyContinue

$assemblyName = [System.Reflection.AssemblyName]::GetAssemblyName(
    $assemblyDestination
)
$assemblyHash = (
    Get-FileHash -LiteralPath $assemblyDestination -Algorithm SHA256
).Hash

Write-Host "Installed Ananke COMPAS Grasshopper plugin"
Write-Host "  Folder:   $InstallPath"
Write-Host "  Assembly: $($assemblyName.FullName)"
Write-Host "  SHA256:   $assemblyHash"
