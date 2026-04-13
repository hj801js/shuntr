Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".conda_envs\shuntreactorengineering\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Workspace environment was not found at $pythonExe"
}

try {
    & $pythonExe -m nuitka --version | Out-Null
}
catch {
    throw "Nuitka is not installed in the workspace environment. Install it before running this build script."
}

$buildDir = Join-Path $repoRoot "build\nuitka"
$smokeDir = Join-Path $repoRoot "build\smoke\exe-only"
$releaseDir = Join-Path $repoRoot "Release"
$entryScript = Join-Path $repoRoot "src\launch_app.py"
$resourceDir = Join-Path $repoRoot "src\shunt_reactor_engineering\resources"
$dataDir = Join-Path $repoRoot "data"
$exeName = "shunt-reactor-report.exe"

Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $smokeDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $buildDir | Out-Null

$env:PYTHONPATH = Join-Path $repoRoot "src"

& $pythonExe -m nuitka `
    --onefile `
    --windows-console-mode=disable `
    --enable-plugin=pyside6 `
    --include-package=shunt_reactor_engineering `
    --nofollow-import-to=scipy `
    --nofollow-import-to=sklearn `
    --nofollow-import-to=matplotlib `
    --nofollow-import-to=seaborn `
    --nofollow-import-to=sympy `
    --nofollow-import-to=pandas `
    --nofollow-import-to=tkinter `
    "--include-data-dir=$resourceDir=shunt_reactor_engineering\resources" `
    "--output-dir=$buildDir" `
    "--output-filename=$exeName" `
    --python-flag=no_docstrings `
    --remove-output `
    --lto=yes `
    $entryScript

if ($LASTEXITCODE -ne 0) {
    throw "Nuitka build failed."
}

$builtExe = Join-Path $buildDir $exeName
if (-not (Test-Path $builtExe)) {
    throw "Expected EXE was not created at $builtExe"
}

Remove-Item $releaseDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $releaseDir | Out-Null
Copy-Item $builtExe -Destination (Join-Path $releaseDir $exeName)

$toolsDir = Join-Path $repoRoot "tools"
if (Test-Path $toolsDir) {
    Copy-Item $toolsDir -Destination (Join-Path $releaseDir "tools") -Recurse
}
if (Test-Path $dataDir) {
    Copy-Item $dataDir -Destination (Join-Path $releaseDir "data") -Recurse
}

New-Item -ItemType Directory -Path $smokeDir -Force | Out-Null
Copy-Item (Join-Path $releaseDir $exeName) -Destination (Join-Path $smokeDir $exeName)
if (Test-Path (Join-Path $releaseDir "tools")) {
    Copy-Item (Join-Path $releaseDir "tools") -Destination (Join-Path $smokeDir "tools") -Recurse
}
if (Test-Path (Join-Path $releaseDir "data")) {
    Copy-Item (Join-Path $releaseDir "data") -Destination (Join-Path $smokeDir "data") -Recurse
}

$process = Start-Process -FilePath (Join-Path $smokeDir $exeName) -WorkingDirectory $smokeDir -PassThru
Start-Sleep -Seconds 20

if (-not $process.HasExited) {
    $null = $process.CloseMainWindow()
    Start-Sleep -Seconds 3
}

if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
}

$reportOutputDir = Join-Path $smokeDir "output\reports"
if (-not (Test-Path $reportOutputDir)) {
    throw "Smoke test failed. output\\reports was not created beside the EXE."
}

Write-Host "Build complete:" (Join-Path $releaseDir $exeName)
Write-Host "Smoke output:" $reportOutputDir
