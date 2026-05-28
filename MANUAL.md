# svj_analyze — User Manual

This manual covers both delivery modes — the single-file HTML browser and the Python command-line toolkit — plus a complete output format reference and troubleshooting guide.

---

## Quick start

### HTML browser (no install)

1. Locate `svj_library_browser.html` in the project folder.
2. Double-click it — it opens in your default browser. Or right-click → *Open with* → choose Chrome, Edge, Firefox, or Safari.
3. Drag your SVJ library (folder, `.zip`, or individual `.svj.json` files) onto the **drop bar** at the top of the page, or use the **Pick folder** / **Pick files** buttons.
4. Done — all tabs are live immediately.

> **No internet? No problem.** The file works offline once opened. The only online requirement is the first load of Plotly and JSZip from their CDN. For permanent air-gapped use, download both JS libraries and replace the two `<script src="…">` lines at the top of the HTML.

### Python toolkit

**Requirements:** Python 3.9 or later, plus one package:

```bash
pip install openpyxl
```

**Run it:**

```bash
# Point at a folder of .svj.json files (any depth of subfolders)
python svj_analyze.py /path/to/your/svj_library --out ./report

# Or point at a .zip archive
python svj_analyze.py library_snapshot.zip --out ./report
```

Outputs land in `./report/`: an Excel workbook (`library.xlsx`) plus six JSON files. Drop `index.json` and `curves.json` from that folder onto the HTML browser for instant large-library browsing — no re-parsing needed.

**Sanity checks only (no file output):**

```bash
python svj_analyze.py check /path/to/your/svj_library
```

---

## Contents

1. [HTML browser](#1-html-browser)
   - [Loading a library](#loading-a-library)
   - [Tab: Index](#tab-index)
   - [Tab: Tires](#tab-tires)
   - [Tab: Curves](#tab-curves)
   - [Tab: Detail](#tab-detail)
   - [Tab: Diff](#tab-diff)
   - [Tab: Pacejka](#tab-pacejka)
   - [Tab: Fingerprint](#tab-fingerprint)
   - [Tab: Heatmap](#tab-heatmap)
2. [Python toolkit](#2-python-toolkit)
   - [CLI reference](#cli-reference)
   - [Sanity check subcommand](#sanity-check-subcommand)
   - [Library API](#library-api)
3. [Output format reference](#3-output-format-reference)
4. [Conventions and caveats](#4-conventions-and-caveats)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. HTML browser

`svj_library_browser.html` is a self-contained single-page application. External dependencies: **Plotly** (charts) and **JSZip** (zip extraction), both loaded from a CDN. Any modern browser works — Chrome, Edge, Firefox, Safari. No data ever leaves the page.

### Loading a library

Four methods, and they can be mixed in one drag-drop:

| Method | How |
|---|---|
| **Drop a folder** | Drag it onto the top bar. Subfolders are walked recursively to any depth. |
| **Drop a zip** | Drag a `.zip` file onto the top bar. Extracted in-memory via JSZip; nested folders inside the zip are fine. Paths in the Index show as `archive.zip!/sub/car.svj.json`. |
| **Drop individual files** | Drag one or more `.svj.json` files directly. |
| **Use the pickers** | *Pick folder* opens an OS folder picker (recursive). *Pick files / zip* opens a file picker for individual files or a zip. |

The header counters (`vehicles`, `unique tires`, `curves`) update as soon as parsing finishes. Any files that fail to parse or aren't SVJ documents are listed in the red strip at the bottom of the page.

---

### Tab: Index

A sortable, filterable master table. One row per vehicle.

**Sorting** — click any column header to sort by it ascending; click again to reverse. The active sort column gains a ▲ or ▼ indicator.

**Filtering** — four controls above the table, all live (no submit button needed):

- **Text search** — matches make, model, year, variant, or source filename.
- **Drive type** — drop-down populated from your data (RWD, FWD, AWD, 4WD, …).
- **Suspension** — matches *either* front or rear topology.
- **EVs only** — checkbox; restricts to cars where `is_ev` is true.

**Export CSV** — downloads a comma-separated file of the currently-visible (filtered + sorted) rows.

**Click a row** — opens that vehicle in the Detail tab.

Columns shown: Make, Model, Year, Drive, EV, Mass (kg), Wheelbase (m), Track F (m), Track R (m), CoG height (m), Front weight %, Suspension F, Suspension R, Peak torque (Nm), Peak power (kW), Peak power (hp), Peak power rpm, Engine config, Displacement (cc), Idle rpm, Max rpm, Gears, Final drive, Battery (kWh), Unique tires, Estimated corners, Completeness %, Data confidence, Source file.

---

### Tab: Tires

A card grid of every unique tire footprint in the loaded library. Each card shows:

- A synthesised label, e.g. `6.0Jx14" (~77% AR, R=295mm)`
- Rim diameter and width in both inches and millimetres
- Loaded radius (when available)
- Which corners it appears on and with what count (e.g. `FL×1, FR×1, RL×1, RR×1`)
- Which cars use it

**Filters** — text search (matches the label and car list), rim diameter, rim width, and loaded radius drop-downs. All drop-downs are populated from your data.

---

### Tab: Curves

Overlay any curve family across any subset of cars on a single Plotly chart.

1. Choose a **curve type**: Engine torque (Nm vs rpm), Engine power (kW vs rpm, derived), Damper bump (N vs m/s), or Damper rebound (N vs m/s).
2. For damper curves, optionally restrict to one **corner** (FL / FR / RL / RR).
3. Use the **car picker** pills below the controls to toggle cars in or out. `select all` and `clear` buttons help with large libraries.

The chart re-renders immediately on any change. Hover any point to see its value. Click a legend entry to toggle its trace; double-click to isolate it.

The `curves` counter in the page header shows how many traces are currently plotted.

---

### Tab: Detail

Opens automatically when you click a row in the Index tab. You can also switch to this tab manually — it shows the last car you clicked.

**Vehicle summary** — a JSON block with all flat fields: identity, chassis dimensions, steering, engine, powertrain, data quality.

**Per-corner suspension** — a second JSON block with topology, spring type and rate, damper type, brake disc spec, tire label, and estimated flag for each of the four corners.

**Engine chart** — torque (Nm, left axis) and power (kW, right axis) on a shared rpm axis.

**Damper chart** — bump (solid lines) and rebound (dashed lines) for all four corners overlaid on one chart.

Both charts are blank and show a message when the relevant curves are absent.

---

### Tab: Diff

Field-by-field comparison between two cars, with numeric deltas.

**Filtering the picker lists** — use the filter bar at the top (free text, make, drive type) to narrow both car A and car B dropdowns to a relevant subset. A car-count indicator shows how many cars match the current filter. Use *✕ clear* to reset all filters at once.

**Diff table** — organised into six sections: Identity, Chassis, Engine, Powertrain, Suspension, Data quality. Within each section, each row shows the field name, car A's value, car B's value, and Δ (B − A). Rows where A and B differ are shaded. For numeric fields, Δ shows the absolute difference and a percentage relative to A.

**Per-corner suspension table** — below the main table; shows topology, spring rate, and tire footprint side-by-side for all four corners.

**Curve overlays** — if either car has an engine torque/power curve, a combined chart is shown with A traces in red and B traces in blue. Similarly for damper bump curves. Overlays are hidden when both cars lack the relevant curves.

---

### Tab: Pacejka

Visualises Pacejka '89 Magic Formula tire model coefficients: `F = D · sin(C · atan(B·x − E·(B·x − atan(B·x))))`.

Coefficients are read from `suspension.{corner}.tire.pacejka.{lat|lon}.{B,C,D,E}` in the SVJ document. Cars without these fields do not appear in the picker.

**Controls:**

| Control | Options |
|---|---|
| Curve | Lateral Fy(α) — slip angle, or Longitudinal Fx(κ) — slip ratio |
| Corner | All four corners, or a single one (FL / FR / RL / RR) |
| Filter make | Restrict picker to one make |
| Filter rim Ø | Restrict picker to cars with a specific rim diameter |

The chart plots normalised force (y/D) vs slip angle in degrees (lateral) or slip ratio (longitudinal). Each trace is coloured and corner-dashed distinctly.

The **coefficient table** below the chart lists B, C, D (peak), E, and initial stiffness (B·C·D) for every plotted trace.

---

### Tab: Fingerprint

A 9-axis normalised radar (polar) chart. Each selected car is one filled polygon; overlaying multiple cars reveals handling character at a glance.

**The 9 axes:**

| Axis | Source data | Outer edge means… |
|---|---|---|
| Mass | `mass_total_kg` | Lightest in library |
| F/R balance | `1 − 2·|fwf − 0.5|` | Perfect 50/50 weight split |
| CoG height | `cog_height_m` | Lowest centre of gravity |
| Contact patch | Average `rim_width_mm` across corners | Widest footprint |
| Spring F | `spring_rate_front_Nm` | Stiffest front spring |
| Spring R | `spring_rate_rear_Nm` | Stiffest rear spring |
| Damper @0.2 m/s | Bump curve interpolated at 0.2 m/s, averaged across corners | Highest bump force |
| Torque @4000 rpm | Torque curve interpolated at 4000 rpm | Highest torque at that point |
| Power/weight | `peak_power_kW / (mass_total_kg / 1000)` in kW/t | Highest power-to-weight |

**Normalisation** — each axis is rescaled to [0, 1] using the loaded library's 5th and 95th percentile as the floor and ceiling. Values outside that range are clamped. The scale therefore adjusts to your library: if you load only track cars, the mass axis compresses around what's normal for track cars. An axis shows `—` (rendered as 0) when the underlying data is absent.

**Below the chart** — a table of numeric percentile scores for each selected car. Cells are colour-coded: green ≥ 75%, red ≤ 25%, amber in between.

Use the **car-picker** pills to select or deselect cars. `select all` / `clear` manage large libraries.

---

### Tab: Heatmap

A completeness grid: rows are cars, columns are data subtrees, cells show what fraction of expected fields are non-null within each group. Use this to find which cars need data entry work and which subtrees are systematically under-populated.

**The 9 subtree groups:**

| Group | Fields checked |
|---|---|
| Identity | make, model, year, drive type (4 fields) |
| Chassis | mass, wheelbase, track F/R, CoG height, front weight % (6 fields) |
| Engine | config, displacement, idle rpm, max rpm, peak torque, peak power (6 fields) |
| Curves | torque curve present — binary 0 or 1 |
| Suspension | topology + spring rate per corner (8 fields across FL/FR/RL/RR) |
| Dampers | bump curve present per corner (fraction of 4) |
| Tires | rim diameter present per corner (fraction of 4) |
| Drivetrain | gearbox type, gear count, final drive (3 fields) |
| Brakes | brake disc diameter per corner (fraction of 4) |

**Overall** — the simple mean of all nine group scores.

**Colour scale:**

| Colour | Score range |
|---|---|
| Dark green | 100% |
| Light green | 75–99% |
| Amber | 50–74% |
| Orange | 25–49% |
| Red | 0–24% |

**Sorting** — click any column header. The Overall column defaults to descending (best first). Individual group columns default to ascending (worst first) so gaps surface immediately. Click a second time to reverse.

---

### Keyboard and interaction notes

- Plotly charts: pan/zoom toolbar appears top-right on hover. Click a legend entry to toggle its trace; double-click to isolate it and hide the rest.
- Index table: keyboard-scroll works normally once the table has focus.
- The browser retains all loaded data for the session — switching tabs does not re-parse.

---

### Limitations

- The browser reads files into memory only. There is no "save back" path — curated merges must be done with the Python toolkit.
- Fingerprint normalisation is relative to the currently-loaded library. Adding or removing cars shifts all scores.
- Parsing is synchronous; a library of 1 000+ cars may take a few seconds but stays responsive.
- CDN dependencies (Plotly, JSZip) require internet access. For fully air-gapped use, download both libraries locally and update the two `<script src="…">` tags near the top of the HTML file.

---

## 2. Python toolkit

### Install

```bash
pip install openpyxl
```

No other dependencies. The toolkit is a single file — place `svj_analyze.py` anywhere on your `PYTHONPATH` or invoke it directly.

### CLI reference

```
python svj_analyze.py <input> [<input> …] [--out <dir>] [--validate]
```

| Argument | Description |
|---|---|
| `<input>` | One or more paths. Each may be a **folder** (recursive, any depth) or a **`.zip` archive** (also recursive). Mix freely. |
| `--out <dir>` | Output directory. Default: `./svj_report`. Created if it does not exist. |
| `--validate` | Run structural validation on every SVJ document and write `validation.json` alongside the other outputs. |

**Examples:**

```bash
# Single folder
python svj_analyze.py ~/cars/svj_library --out ~/reports/2026-06

# Single zip
python svj_analyze.py ~/cars/snapshot.zip --out ./report

# Mix of sources
python svj_analyze.py folder_a snapshot.zip folder_b --out ./combined

# With structural validation
python svj_analyze.py ~/cars/svj_library --out ./report --validate
```

On success the script prints a JSON summary to stdout:

```json
{
  "inputs": ["test_library.zip (zip)"],
  "scanned_files": 7,
  "vehicles": 7,
  "unique_tires": 8,
  "curves": 68,
  "errors": 0,
  "out_dir": "report"
}
```

Exit code is `0` on success, `2` if an input path does not exist.

---

### Sanity check subcommand

```
python svj_analyze.py check <input> [<input> …] [--json]
```

Runs a suite of physical plausibility checks on every SVJ file. No XLSX or JSON outputs — results go to stdout only.

Checks performed:

- CoG x-coordinate is between `−wheelbase` and `0` (behind front axle, in front of rear)
- Rim diameter is smaller than twice the loaded radius (tire can't be thinner than the rim)
- Damper bump curves are monotonically non-decreasing
- Torque curve contains no negative values
- Gear ratios are strictly descending
- Final drive ratio > 1.0 for RWD/FWD layouts
- Battery capacity is present when the vehicle is flagged EV
- Front weight fraction is in the range [0, 1]

Use `--json` to get machine-readable output instead of the human-readable table.

Exit code: `0` if no errors (warnings are allowed), `1` if any errors.

---

### Library API

```python
from pathlib import Path
from svj_analyze import (
    find_svj_files, load_svj, iter_sources,
    summarize_vehicle, build_tire_catalogue, extract_curves,
    compute_fingerprint_norms, compute_fingerprint,
    compute_completeness_heatmap,
    export_xlsx,
)

# --- scan a folder ---
vehicles, curves = [], []
for p in find_svj_files(Path("my_library")):
    doc = load_svj(p)
    vehicles.append(summarize_vehicle(doc, source=p.name))
    curves.extend(extract_curves(doc, car_id=f"{p.stem}"))

tires = build_tire_catalogue(vehicles)

# --- handling fingerprint (normalised per-library) ---
fp_norms = compute_fingerprint_norms(vehicles)
fingerprints = [
    {"car": f"{v['make']} {v['model']}", **compute_fingerprint(v, fp_norms)}
    for v in vehicles
]

# --- completeness heatmap ---
heatmap = compute_completeness_heatmap(vehicles)

# --- export ---
export_xlsx(
    vehicles, tires, curves,
    Path("library.xlsx"),
    fingerprints=fingerprints,
    heatmap=heatmap,
)
```

`iter_sources` accepts both folders and `.zip` archives, yielding `SvjSource(display_name, doc)` objects. Use it when you want a single loop over mixed inputs:

```python
for src in iter_sources(Path("library.zip")):
    vehicles.append(summarize_vehicle(src.doc, source=src.display_name))
```

---

## 3. Output format reference

### `index.json`

Array of vehicle summary records. All fields except `source`, `make`, and `model` may be `null` if the data is absent.

```
source                       string    filename or zip-qualified path
spec_version                 string    SVJ _metadata.version
data_confidence              string    low | medium | high
make                         string
model                        string
year                         integer
variant                      string
drive_type                   string    RWD | FWD | AWD | 4WD | …
is_ev                        boolean
mass_total_kg                number
wheelbase_m                  number
track_front_m                number
track_rear_m                 number
cog_height_m                 number    positive = above ground
front_weight_fraction        number    0..1
steering_type                string
steering_ratio               number
topology_front               string    e.g. macpherson, double_wishbone
topology_rear                string
spring_rate_front_Nm         number    N/m
spring_rate_rear_Nm          number    N/m
peak_torque_Nm               number
peak_torque_rpm              number
peak_power_kW                number    derived from torque curve: T·ω/1000
peak_power_hp                number    kW × 1.341
peak_power_rpm               number
engine_configuration         string    e.g. inline-4, V8
engine_displacement_cc       number
engine_idle_rpm              number
engine_max_rpm               number
power_to_weight_kW_per_tonne number
gearbox_type                 string
gear_count                   integer
final_drive                  number
battery_kwh                  number    EVs only
completeness_pct             number    0..100
unique_tires_on_car          integer
estimated_corners            integer   count of corners flagged _est
torque_curve                 array     [[rpm, Nm], …]
power_curve                  array     [[rpm, kW], …]   derived
corners                      object    { FL, FR, RL, RR }  — see below
tires_by_corner              object    { FL, FR, RL, RR }  — see below
has_pacejka                  boolean
```

**`corners[c]`** — per-corner suspension block:

```
topology           string    suspension system type
spring_type        string
spring_rate_Nm     number    N/m
damper_type        string
damper_bump        array     [[m/s, N], …]
damper_rebound     array     [[m/s, N], …]
brake_disc_type    string
brake_disc_mm      number    outer diameter
estimated          boolean   true if any _est flag is set on this corner
```

**`tires_by_corner[c]`** — per-corner tire identity:

```
key                [number, number, number]   [rim_Ø_mm, rim_w_mm, loaded_r_mm]
label              string
rim_diameter_mm    number
rim_width_mm       number
loaded_radius_mm   number
wheel_mass_kg      number
```

---

### `tires.json`

Array of unique tire footprints, sorted by rim diameter then width.

```
key                [number, number, number]   identity tuple (mm)
label              string                     synthesised human label
rim_diameter_mm    number
rim_diameter_in    number
rim_width_mm       number
rim_width_in       number
loaded_radius_mm   number
corner_counts      object                     { FL: n, FR: n, … }
car_count          integer
cars               string[]                   "Make Model (Year)" list
```

Two tires collapse to one footprint only when all three of `(rim_Ø, rim_width, loaded_radius)` match to 0.1 mm. Missing `loaded_radius` is allowed — tires with the same rim but different (or absent) loaded radius are bucketed separately.

---

### `curves.json`

Array of curve records, one per extracted curve segment.

```
car       string             "Make Model (Year)"
kind      string             engine_torque | engine_power | damper_bump | damper_rebound
corner    string | null      FL | FR | RL | RR  (null for engine curves)
x_unit    string             rpm | m/s
y_unit    string             Nm | kW | N
points    [[x, y], …]
derived   boolean            true for engine_power (computed from torque)
```

---

### `fingerprint.json`

Array of normalised handling fingerprint records, one per vehicle. Each score is `null` when the underlying field is absent or when the library's p5–p95 band collapses to a single value.

```
car           string        "Make Model (Year)"
source        string        filename
mass          number|null   0..1   inverted: 1 = lightest in library
balance       number|null   0..1   1 = perfect 50/50 front/rear weight split
cog           number|null   0..1   inverted: 1 = lowest centre of gravity
contact       number|null   0..1   average rim_width normalised
spring_f      number|null   0..1   front spring rate normalised
spring_r      number|null   0..1   rear spring rate normalised
damper        number|null   0..1   average bump force at 0.2 m/s normalised
torque        number|null   0..1   torque at 4000 rpm normalised
pw_ratio      number|null   0..1   power-to-weight (kW/t) normalised
```

---

### `heatmap.json`

Array of completeness records, one per vehicle.

```
car           string    "Make Model (Year)"
source        string    filename
overall       number    0..1  mean of the nine group scores below
identity      number    0..1  make, model, year, drive type
chassis       number    0..1  mass, wheelbase, track F/R, CoG, front weight %
engine        number    0..1  config, displacement, idle/max rpm, peak T/P
curves        number    0|1   torque curve present (binary)
suspension    number    0..1  topology + spring rate, all 4 corners
dampers       number    0..1  bump curve present, fraction of 4 corners
tires         number    0..1  rim diameter present, fraction of 4 corners
drivetrain    number    0..1  gearbox type, gear count, final drive
brakes        number    0..1  brake disc diameter, fraction of 4 corners
```

---

### `library.xlsx`

Five sheets, all with frozen header rows and column autofilter.

| Sheet | Contents |
|---|---|
| **Vehicles** | One row per car — all flat fields from `index.json` (excludes nested curves and corner data). |
| **Tires** | One row per unique footprint — 9 columns including a `Corners` text summary and a pipe-joined `Used on` car list. |
| **Curves** | One row per curve — car, kind, corner, units, point count, x min/max, y min/max. Use the x/y range columns to spot unit errors without opening a chart. |
| **Fingerprint** | One row per car — car name, source file, and the 9 normalised dimension scores as decimals [0..1]. |
| **Heatmap** | One row per car — car name, source file, overall score, and the 9 group scores as `0%` formatted cells with colour fills (dark green = 100%, red = 0%). |

---

### `errors.json` (optional)

Only written when at least one file fails. Each record:

```
file     string    filename or zip-qualified path
error    string    "load: <message>" or "summarize: <message>"
```

### `validation.json` (optional, `--validate` only)

Written when `--validate` is passed and at least one validation issue is found.

```
source      string    filename
field       string    SVJ path of the offending field
issue       string    description of the problem
severity    string    error | warning | info
```

---

## 4. Conventions and caveats

**Units** — everything downstream is SI: metres, kilograms, newtons, newton-metres, watts, radians. Derived display values (horsepower, inches) are computed at render time from SI originals.

**Coordinate system** — SVJ follows SAE J670: X forward, Y right, Z down. The CoG z-coordinate is therefore negative when the CoG is above the ground plane, so `cog_height_m = −cog_z`. Front weight fraction is `1 + cog_x / wheelbase` (valid when `cog_x` is negative, i.e. behind the front axle).

**Peak power is derived** — computed from the torque curve as `P = T · ω = T · rpm · 2π / 60 / 1000` kW. If the torque curve has `_est` flags or low confidence, that uncertainty propagates to all power values. A vehicle with no torque curve will show `null` for peak power, power-to-weight, and the power/weight fingerprint axis.

**Tire identity** — two tires become one footprint only when `(rim_Ø, rim_width, loaded_radius)` all match to 0.1 mm. Cars with staggered tires (different front/rear sizes) correctly show multiple footprints. Front weight fraction, `unique_tires_on_car`, and the Tires heatmap score all respect this.

**Fingerprint normalisation is per-run** — the p5/p95 band is computed from the vehicles you load (HTML) or the current CLI run (Python). A score of 0.7 means "70 % of the way from the 5th to the 95th percentile in this library", not an absolute value. Results shift as you add or remove cars.

**Completeness % vs heatmap** — the `completeness_pct` column in the Index table uses a flat list of ~25 key fields (`_COMP_KEYS` in the source). The Heatmap tab uses nine subtree groups with different denominators and is better for pinpointing *where* data is missing. They will not always agree numerically.

---

## 5. Troubleshooting

**"No .svj.json files found"**
The browser accepts `.json`, `.svj.json`, and `.zip`. The Python toolkit globs for `*.svj.json`. If your files use a different extension, rename them or (for the Python toolkit only) use `iter_sources` directly and filter by your own pattern.

**Zip extraction fails in the browser**
JSZip is loaded from a CDN. If you are offline or behind a firewall, download `jszip.min.js` locally and change the `<script src="…">` tag at the top of the HTML to point to your local copy. Plotly can be substituted the same way.

**"not an SVJ document"**
The browser requires both `_metadata` and `vehicle_info` at the top level. Files missing either are skipped and reported in the red strip. The Python toolkit emits them in `errors.json`.

**Blank engine or power chart**
The vehicle has no `powertrain.engine.torque_curve`. This is expected for EV-only documents (no ICE torque curve) and for skeleton files that haven't been filled in yet. Check the Heatmap tab — if the Curves group shows 0%, the curve is genuinely absent.

**XLSX shows blank Peak power / Power-to-weight**
Same cause as above — no torque curve means no derived power.

**Fingerprint axis shows `—` in the table**
Either the underlying field is `null` for that vehicle, or the entire library has the same value for that axis (p5 = p95), so normalisation is undefined. The second case is rare and only occurs with very small or homogeneous libraries.

**Heatmap Curves column is always red**
The bundled test library (`test_library_multilevel.zip`) contains skeleton SVJs without torque curves, so every Curves cell shows 0%. This is correct — add a `powertrain.engine.torque_curve` array to a document and reloading will turn that cell green.

**Tire label says "unspecified"**
The `wheel` block for that corner has none of `rim_diameter`, `rim_width`, or `loaded_radius`. Add at least `rim_diameter` (in metres) to get a usable label.

**Sanity check reports "gear ratios not strictly descending"**
The SVJ `gearbox.ratios` array is ordered lowest gear first (highest ratio). If the ratios are in ascending order (highest gear first), the check will flag every car. Check the spec and the converter that produced the file.

**Large library is slow to load in the browser**
Parsing is synchronous JavaScript. ~200 cars with full damper curves typically takes 1–3 seconds. For 1 000+ cars consider using the Python CLI (`python svj_analyze.py`) and opening the resulting `library.xlsx` directly.
