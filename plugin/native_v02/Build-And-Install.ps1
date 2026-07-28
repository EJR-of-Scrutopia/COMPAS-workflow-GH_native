[CmdletBinding()]
param(
    [string] $InstallPath = (
        Join-Path $env:APPDATA "Grasshopper\Libraries\Ananke_COMPAS"
    ),
    [string] $EnvironmentName = "catenary-compas-2026",
    [string] $PythonExecutable = "",
    [string] $SiteEnvironmentPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..\..")
)
$projectPath = Join-Path $PSScriptRoot "Ananke.COMPAS.Native.csproj"
$assemblySource = Join-Path $PSScriptRoot (
    "bin\Release\net8.0-windows\Ananke.COMPAS.gha"
)

& dotnet build $projectPath -c Release -t:Rebuild --nologo
if ($LASTEXITCODE -ne 0) {
    throw "The native Ananke COMPAS Grasshopper build failed."
}
if (-not (Test-Path -LiteralPath $assemblySource -PathType Leaf)) {
    throw "The build did not produce the expected .gha: $assemblySource"
}

if (-not $PythonExecutable) {
    $PythonExecutable = Join-Path $env:USERPROFILE (
        ".rhinocode\py39-rh8\python.exe"
    )
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw "Python executable was not found: $PythonExecutable"
}
$PythonExecutable = (
    Resolve-Path -LiteralPath $PythonExecutable
).Path

if (-not $SiteEnvironmentPath) {
    $siteEnvironments = Join-Path $env:USERPROFILE (
        ".rhinocode\py39-rh8\site-envs"
    )
    if (Test-Path -LiteralPath $siteEnvironments -PathType Container) {
        $match = Get-ChildItem `
            -LiteralPath $siteEnvironments `
            -Directory |
            Where-Object {
                $_.Name.StartsWith(
                    $EnvironmentName + "-",
                    [System.StringComparison]::OrdinalIgnoreCase
                )
            } |
            Sort-Object LastWriteTimeUtc -Descending |
            Select-Object -First 1
        if ($null -ne $match) {
            $SiteEnvironmentPath = $match.FullName
        }
    }
}
if (
    -not $SiteEnvironmentPath -or
    -not (Test-Path -LiteralPath $SiteEnvironmentPath -PathType Container)
) {
    throw (
        "Rhino Python environment '$EnvironmentName' was not found. " +
        "Pass -SiteEnvironmentPath with its exact site-envs folder."
    )
}
$SiteEnvironmentPath = (
    Resolve-Path -LiteralPath $SiteEnvironmentPath
).Path

New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
$assemblyDestination = Join-Path $InstallPath "Ananke.COMPAS.gha"
Copy-Item `
    -LiteralPath $assemblySource `
    -Destination $assemblyDestination `
    -Force

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
        Copy-Item `
            -LiteralPath $file.FullName `
            -Destination $destination `
            -Force
    }
}

$backendConfiguration = [ordered]@{
    protocolVersion = 1
    executable = $PythonExecutable
    arguments = @("-m", "ananke_equilibrium.worker")
    workingDirectory = $InstallPath
    pythonPaths = @(
        $pythonDestination,
        $SiteEnvironmentPath
    )
    environmentName = $EnvironmentName
    environment = [ordered]@{
        PYTHONUTF8 = "1"
        PYTHONUNBUFFERED = "1"
        OMP_NUM_THREADS = "1"
        OPENBLAS_NUM_THREADS = "1"
        MKL_NUM_THREADS = "1"
    }
    startupTimeoutMs = 20000
    requestTimeoutMs = 120000
    cancellationGraceMs = 1500
    maxFrameBytes = 33554432
}
$backendPath = Join-Path $InstallPath "backend.json"
$backendJson = $backendConfiguration | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText(
    $backendPath,
    $backendJson,
    [System.Text.UTF8Encoding]::new($false)
)

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

Unblock-File `
    -LiteralPath $assemblyDestination `
    -ErrorAction SilentlyContinue

$assemblyName = [System.Reflection.AssemblyName]::GetAssemblyName(
    $assemblyDestination
)
$assemblyHash = (
    Get-FileHash -LiteralPath $assemblyDestination -Algorithm SHA256
).Hash

Write-Host "Installed native Ananke COMPAS Grasshopper plugin"
Write-Host "  Folder:      $InstallPath"
Write-Host "  Assembly:    $($assemblyName.FullName)"
Write-Host "  Python:      $PythonExecutable"
Write-Host "  Environment: $SiteEnvironmentPath"
Write-Host "  SHA256:      $assemblyHash"
