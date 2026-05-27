# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] — 2026-05-27

### Added

#### Python (`svj_analyze.py`)
- **Handling Fingerprint** — 9-axis normalised radar chart. `compute_fingerprint_norms()`, `compute_fingerprint()`. New axis: `power_to_weight_kW_per_tonne`.
- **Completeness Heatmap** — `compute_completeness_heatmap()` scores 9 subtree groups (Identity, Chassis, Engine, Curves, Suspension, Dampers, Tires, Drivetrain, Brakes) per car.
- **`fingerprint.json`** and **`heatmap.json`** outputs written by `run()`.
- **XLSX Heatmap sheet** (Sheet 5) with colour-coded cells (dark green → red) via `PatternFill`.
- **`HEATMAP_GROUPS`** and **`FP_DIM_DEFS`** as single sources of truth for group/dimension definitions.
- **`__version__`** constant.

#### HTML browser (`svj_library_browser.html`)
- **Fingerprint tab** (`🕸 Fingerprint`) — Plotly `scatterpolar` overlay for any subset of cars; normalised score table.
- **Heatmap tab** (`📊 Heatmap`) — sticky-column colour-coded completeness grid, sortable by any column.
- `interpCurve`, `FP_DIMS`, `computeFpNorms`, `fpVehicleValues` mirror Python fingerprint logic.
- `HEATMAP_GROUPS`, `_hmCellStyle`, `renderHeatmap`, `hmSetSort` mirror Python heatmap logic.

#### Documentation
- Completely rewritten **README.md** — 8-tab table, CLI reference, 7-output table, file tree.
- Completely rewritten **MANUAL.md** — full user guide for all 8 tabs, CLI reference, output schemas, conventions, troubleshooting.
- Updated **DEVELOPMENT_BRIEF.md** to v0.2 with new architecture, updated roadmap, and suggested next issues.

#### Project hygiene
- `.flake8` config (max-line-length=100, E221 suppressed).
- `.gitignore`.
- `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).
- `.github/workflows/ci.yml` — lint + smoke test on push/PR.

### Changed
- `export_xlsx` now accepts optional `fingerprints` and `heatmap` parameters; writes 5 sheets instead of 4.
- `run()` orchestrator returns `fingerprint` and `heatmap` keys in its result dict.

### Fixed
- Removed unused imports (`io`, `os`, `dataclasses.field`, `dataclasses.asdict`).
- All flake8 errors and warnings resolved (F401, F811, F841, E302, E501, E701, E127, E131).

---

## [0.1.0] — initial release

### Added
- `svj_analyze.py` — Python CLI producing XLSX (Vehicles / Tires / Curves / Fingerprint sheets) + four JSON exports (`index.json`, `tires.json`, `curves.json`, `errors.json`).
- `svj_library_browser.html` — single-file offline browser with Index, Tires, Curves, Detail, Diff, and Pacejka tabs.
- Physical sanity-check suite (`check` subcommand).
- Structural validation (`--validate` flag).
- Bundled test library (`examples/test_library_multilevel.zip`, 9 vehicles).
- Pre-generated demo output in `report/`.
