# svj_analyze

Library-wide analysis for [SVJ (Standard Vehicle JSON)](https://github.com/RFloEng/SVJ-standard-vehicle-json) files.
Two tools, one set of algorithms:

| Tool | What it is |
|---|---|
| `svj_analyze.py` | Python CLI. Scans a folder or `.zip` of `*.svj.json` files and writes a 5-sheet Excel workbook plus six JSON exports. |
| `svj_library_browser.html` | Single-file offline browser. Drop a folder, zip, or individual files onto it and explore your entire library without installing anything. |

Reads both SVJ layouts: the legacy `suspension.<corner>` form (spec v0.94–v0.97) and the `wheel_stations` + `constraints` form (v0.100+). Tested on the bundled examples and on a 2 046-file library (Assetto Corsa, Richard Burns Rally and Race07 conversions; not distributed here). Zero errors.

---

## HTML browser — no install

1. Open `svj_library_browser.html` in Chrome, Edge, Firefox, or Safari.
2. Drop a **folder**, a **`.zip`**, or individual **`.svj.json`** files onto the top bar — or use the *Pick folder* / *Pick files* buttons. Any combination, any depth of nesting.
3. Work across eight tabs:

| Tab | What you get |
|---|---|
| **📋 Index** | Sortable, filterable master table. Click any row to open Detail. Export filtered view as CSV. |
| **🛞 Tires** | Unique tire footprints with rim dimensions, per-corner counts, and attribution to cars. |
| **📈 Curves** | Overlay engine torque/power or damper bump/rebound across any subset of cars. |
| **🔍 Detail** | JSON summaries + engine torque/power chart + 4-corner damper chart for one car. |
| **⚖ Diff** | Field-by-field table (A vs B, with Δ column) + curve overlays for two cars. |
| **🔬 Pacejka** | Pacejka Magic Formula Fy(α) and Fx(κ) curves from embedded B/C/D/E coefficients. |
| **🕸 Fingerprint** | 9-axis normalised radar chart for at-a-glance shape comparison across cars. |
| **📊 Heatmap** | Per-car × per-subtree completeness grid. Click any column header to sort. |

Everything runs client-side. No server, no install, no data leaves the page. Plotly and JSZip load from a CDN (swap to local copies for air-gapped use).

---

## Python toolkit

```bash
pip install openpyxl
```

```bash
# Folder (recursive, any depth)
python svj_analyze.py /path/to/svj/library --out ./report

# Zip archive
python svj_analyze.py library.zip --out ./report

# Mix of folders and zips
python svj_analyze.py folder_a snapshot.zip folder_b --out ./report

# Physical sanity checks only (no XLSX)
python svj_analyze.py check /path/to/svj/library

# Tire library without car/game attribution (safe to share)
python svj_analyze.py /path/to/svj/library --out ./report --anonymize-tires
```

### Outputs written to `./report/`

| File | Contents |
|---|---|
| `library.xlsx` | 5-sheet workbook: Vehicles · Tires · Curves · Fingerprint · Heatmap |
| `index.json` | Full per-vehicle summary records |
| `tires.json` | Unique tire footprints with car attribution |
| `tires.svj.json` | **Tire library**: a tires-only SVJ document (`tires.sets`) with every tire set from the scanned files, de-duplicated; each set carries `x_library.used_by`. With `--anonymize-tires`: no car names, source files, game names, descriptions or vendor (`x_*`) blocks; every set gets a clean `size` block (size code, rim Ø/width, overall Ø) |
| `curves.json` | Every extracted curve with metadata |
| `fingerprint.json` | 9-axis normalised handling fingerprint, one record per car |
| `heatmap.json` | Per-subtree completeness scores, one record per car |
| `errors.json` | Files that failed to parse *(only written if any)* |

---

## What it extracts

**Per vehicle** — make, model, year, variant, drive type, EV flag, mass, wheelbase, front/rear track, CoG height, front weight fraction, front/rear suspension topology, steering type and ratio, spring rates F/R, engine configuration, displacement, idle/max rpm, peak torque + rpm, peak power (derived from torque curve) + rpm, power-to-weight, gearbox type, gear count, final drive, battery capacity, per-corner tire footprint, unique-tire count, estimated-corner count, completeness %, data-origin confidence, SVJ spec version.

**Per tire footprint** — identity tuple `(rim Ø mm, rim width mm, loaded radius mm)` rounded to 0.1 mm, same dimensions in inches, which corners and how many, which cars use it.

**Per curve** — car, kind (`engine_torque` / `engine_power` / `damper_bump` / `damper_rebound`), corner, x/y units, point count, full point list.

**Per fingerprint** — 9 normalised [0, 1] scores: mass (inverted), F/R balance, CoG height (inverted), contact patch, spring F, spring R, damper @0.2 m/s, torque @4000 rpm, power-to-weight. All axes normalised to the library's 5th–95th percentile.

**Per heatmap row** — 9 subtree scores (Identity, Chassis, Engine, Curves, Suspension, Dampers, Tires, Drivetrain, Brakes) plus an overall mean. Each score is the fraction of expected fields that are non-null within that group.

---

## Files

```
svj_analyze/
├── README.md                        this file
├── MANUAL.md                        full user documentation
├── CONTRIBUTING.md                  contributor guide
├── DEVELOPMENT_BRIEF.md             architecture + roadmap for contributors
├── LICENSE                          Apache 2.0
├── NOTICE
├── requirements.txt                 openpyxl only
├── svj_analyze.py                   Python CLI + importable library
├── svj_library_browser.html         8-tab single-page browser
├── svj_library_3d.html              companion 3D geometry viewer
├── examples/
│   └── test_library_multilevel.zip  bundled test input (7 cars, nested folders)
└── report/                          pre-generated output from the bundled zip
    ├── library.xlsx
    ├── index.json
    ├── tires.json
    ├── curves.json
    ├── fingerprint.json
    └── heatmap.json
```

---

## License

Apache License, Version 2.0 — see `LICENSE`.
