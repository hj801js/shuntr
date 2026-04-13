# Release Layout

Recommended Windows release layout for the report generator:

```text
Release/
  shunt-reactor-report.exe
  data/
    uptec_logo.jpg
  tools/
    tectonic.exe   # optional but recommended for portable PDF generation
```

Runtime outputs should appear here:

```text
Release/
  output/
    config/
      app_settings.json
    reports/
    runtime/
```

Notes:

- `data/uptec_logo.jpg` is the default logo location and can be replaced by the user.
- `output/config/app_settings.json` stores the admin-adjusted logo path and cable capacitance values.
- `output/reports` contains generated PDF and TEX files.
- `output/runtime` is scratch space for LaTeX compilation.
- Do not place mutable outputs inside packaged resources.
- If `tools/tectonic.exe` is missing, the app depends on a system LaTeX engine such as `xelatex`.
