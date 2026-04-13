# Packaging Notes

## Runtime Path Rules

- Read-only LaTeX templates stay inside `src/shunt_reactor_engineering/resources`.
- Generated files always go to `output/` under the workspace or executable directory.
- For compiled onefile builds, the app must never write into the extractor temp directory.
- If `tools/tectonic.exe` exists beside the executable, the app prefers that LaTeX engine.
- If no bundled engine exists, the app falls back to system `xelatex`, then PATH `tectonic`.
- Default branding is loaded from `data/uptec_logo.jpg`, but the UI safely falls back to `UPTEC` text when the file is missing.

## Recommended Release Layout

See `references/release-layout.md`.

## Planned EXE Flow

1. Build a onefile GUI EXE with Nuitka.
2. Copy the EXE into `Release/`.
3. Copy `data/` when you want the default logo to ship with the EXE.
4. Add `tools/tectonic.exe` only if you want a self-contained LaTeX engine.
5. Smoke-test from an EXE-only folder and verify that `output/reports` is created beside the EXE.

## Build Script

Use `scripts/build_and_smoke.ps1` after installing Nuitka into the workspace environment.
