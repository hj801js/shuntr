$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CONDA_ENVS_PATH = Join-Path $workspace ".conda_envs"
$env:CONDA_PKGS_DIRS = Join-Path $workspace ".conda_pkgs"
$env:MPLCONFIGDIR = Join-Path $workspace ".mplconfig"
$env:PYTHONDONTWRITEBYTECODE = "1"

$envPath = Join-Path $env:CONDA_ENVS_PATH "shuntreactorengineering"

if (-not (Test-Path $envPath)) {
    throw "Conda environment not found at $envPath. Run the setup command from README.md first."
}

$condaHook = & conda shell.powershell hook
if (-not $condaHook) {
    throw "Failed to initialize the Conda PowerShell hook."
}

$condaHook | Out-String | Invoke-Expression
conda activate $envPath
