# Workspace Setup Notes

This workspace uses a local Conda environment so each project stays isolated.

## Environment Path

- Workspace slug: `shuntreactorengineering`
- Environment folder: `.conda_envs/shuntreactorengineering`

## Apply Setup

```powershell
$env:CONDA_ENVS_PATH = "$PWD/.conda_envs"
$env:CONDA_PKGS_DIRS = "$PWD/.conda_pkgs"
conda env update -p "$PWD/.conda_envs/shuntreactorengineering" -f environment.yml --prune
```

`conda env update` will create the environment if it is missing and keep it in sync with `environment.yml`.

## Normal VS Code Terminal Behavior

The default terminal stays unchanged. Switch manually when needed:

```powershell
.\activate_power_conda.ps1
```

You can also open the terminal profile `Power Conda (shuntreactorengineering)`.

## Verification

```powershell
$env:CONDA_ENVS_PATH = "$PWD/.conda_envs"
$env:CONDA_PKGS_DIRS = "$PWD/.conda_pkgs"
conda run -p "$PWD/.conda_envs/shuntreactorengineering" python -c "import numpy, scipy, pandas, matplotlib, seaborn, sklearn, openpyxl, PIL, tkinter; print('ok')"
```

## App Launch

```powershell
.\activate_power_conda.ps1
python -m shunt_reactor_engineering
```

## Packaging Prep

- Path-safe runtime outputs are written to `output/`.
- Read-only LaTeX templates stay under `src/shunt_reactor_engineering/resources`.
- Packaging notes live in `PACKAGING.md`.
- Planned onefile build script: `scripts/build_and_smoke.ps1`
