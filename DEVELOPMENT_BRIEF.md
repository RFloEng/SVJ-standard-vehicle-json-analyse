# svj_analyze — Development Brief

For anyone extending this toolkit. Current state is **v0.2** (Tier 1 complete + first Tier 4 feature landed). This brief covers architecture, extension points, and a prioritised feature list so a future contributor can pick up work without re-deriving context.

## 1. Scope and intent

`svj_analyze` is a library-wide analysis layer on top of SVJ. It does not parse Assetto Corsa (that's the sibling `ac_to_svj` converter), it does not validate against the schema (that's `svj-py/validator.py`), and it does not render 3-D geometry (that's `svj_viewer_v4.0.html` / `svj_library_3d.html`). It reads SVJ documents and produces comparative views, aggregates, and curated merges.

Two design constraints drive the architecture:

1. **Same algorithms, two surfaces.** The Python summariser and the browser summariser produce identical output for the same input. This is deliberate — the XLSX export and the HTML table should never disagree. New fields should be added in both places together.
2. **No backend.** The HTML viewer runs entirely client-side; the Python toolkit is a single file + one pip dependency (openpyxl). Anything more heavyweight should be opt-in and isolated.

## 2. Architecture

### Python side — `svj_analyze.py`

Single module, stdlib-only except for openpyxl. Deliberately not a package yet.

```
find_svj_files(root)              →  list[Path]     file discovery (rglob, recursive)
iter_sources(path)                →  Iter[SvjSource] folder-OR-zip input adapter
load_svj(path)                    →  dict           json.load wrapper
summarize_vehicle(doc, src)       →  dict           one-car record (flat + nested)
extract_curves(doc, car_id)       →  list[dict]     one record per curve
build_tire_catalogue(vehicles)    →  list[dict]     unique footprints + attribution
compute_fingerprint_norms(vs)     →  dict           {p5, p95} per FP dimension
compute_fingerprint(v, norms)     →  dict           8 normalised scores [0,1]
export_xlsx(v, t, c, path, fp)    →  None           4-sheet workbook
run(inputs, out_dir)              →  dict           orchestrator, used by CLI;
                                                    inputs is list of Path, each
                                                    either a folder or a .zip
```

Zip input is handled by `_iter_zip` inside `iter_sources`: the archive is opened with `zipfile.ZipFile`, every entry is scanned (nested directories inside the zip are fine), and each `.svj.json` is streamed through `json.loads`.

Helpers: `_dig`, `_num`, `_interp_curve`, `_peak_of_curve`, `_power_curve_from_torque`, `_tire_key`, `_tire_label`, `_fp_contact_patch`, `_fp_damper_at_02`, `_fp_raw`, `_percentile`. All pure functions.

`VEHICLE_COLUMNS` — single source of truth for the Vehicles sheet header + field mapping.
`FP_DIM_DEFS` — single source of truth for the 8 fingerprint dimensions (key, label, invert).

### Browser side — `svj_library_browser.html`

Single HTML file, inline CSS + inline JS. Two external deps from a CDN (swap to local copies for air-gapped use):

- **Plotly** — charts in Curves, Detail, Diff, Pacejka, and Fingerprint tabs.
- **JSZip** — extracts `.zip` inputs client-side, any nesting depth.

```
summarize(doc, src)           ← mirrors summarize_vehicle
tireKey(w), tireLabel(k)      ← mirror _tire_key / _tire_label
buildTireCatalogue(v)         ← mirrors build_tire_catalogue
interpCurve(pts, qx)          ← mirrors _interp_curve
FP_DIMS                       ← mirrors FP_DIM_DEFS (raw-value extractor per dim)
computeFpNorms(vehicles)      ← mirrors compute_fingerprint_norms
fpVehicleValues(v, norms)     ← mirrors compute_fingerprint
expandZip(file)               ← returns virtual File-shaped entries for zip contents
ingestFiles(fileList)         ← splits zips from regular files, expands zips, parses all

state  = { vehicles, tires, errors, sortKey, sortDir, tab,
           selected, pjSelected, fpSelected }
COLS   = column definitions for the master table (add new columns here)
```

Rendering is vanilla DOM: `renderIndex`, `renderTires`, `renderCurves`, `showDetail`, `renderDiff`, `renderPacejka`, `renderFingerprint`, `rebuildCarPicker`, `rebuildDiffPickers`, `rebuildPacejkaPicker`, `rebuildFpPicker`. No framework. No build step.

### Keeping Python and JS in sync

Any schema-reading change must be applied in both:

1. Add the field to `summarize_vehicle` (Python) **and** `summarize` (JS).
2. If it's a table column, add it to `VEHICLE_COLUMNS` (Python) **and** `COLS` (JS).
3. If it's a curve, add it to `extract_curves` (Python) **and** the curve-type dropdown in the HTML.
4. If it's a fingerprint dimension, add it to `FP_DIM_DEFS` (Python) **and** `FP_DIMS` (JS).

There's no shared source of truth today — long-term, generating both from a TypeScript or Pydantic schema would be worth it (see §5).

## 3. Data contract

The tools expect SVJ documents at spec version ≥ 0.9. The minimum viable document has `_metadata.version`, `vehicle_info.{make,model}`, `chassis.mass_total`, and a `suspension.{FL,FR,RL,RR}` block with at least `wheel.rim_diameter`. Everything else is optional and degrades gracefully to `null` / omitted fields.

Fields the toolkit reads today:

- `_metadata`: `version`, `data_origin.confidence`
- `vehicle_info`: `make`, `model`, `year`, `variant`, `drive_type`
- `chassis`: `mass_total`, `wheelbase`, `track_front`, `track_rear`, `center_of_gravity`
- `steering`: `type`, `overall_ratio`
- `suspension.{FL,FR,RL,RR}`: `topology.system_type`, `wheel.{rim_diameter,rim_width,loaded_radius,mass,rotational_inertia}`, `spring.{type,rate}`, `damper.{type,bump_curve,rebound_curve}`, `brake.disc.{type,outer_diameter}`, `_est`, `tire.pacejka.{lat,lon}.{B,C,D,E}`
- `powertrain`: `layout`, `engine.{torque_curve,idle_rpm,max_rpm,displacement,configuration}`, `gearbox.{type,ratios}`, `differentials[0].final_drive`
- `electric`: `motors`, `battery.capacity_kwh`

## 4. Extension points

Four concrete places to hook new behaviour:

**Add a derived field.** Edit `summarize_vehicle` (Python) and `summarize` (JS). If it's table-worthy, add it to `VEHICLE_COLUMNS` (Python) and `COLS` (JS).

**Add a new curve family.** Edit `extract_curves` (Python) and the kind switch in `renderCurves` (JS). Add the option to `#curveKind` in HTML. The curves index sheet picks it up automatically.

**Add a new fingerprint dimension.** Add an entry to `FP_DIM_DEFS` (Python) and `FP_DIMS` (JS). The XLSX Fingerprint sheet and the HTML radar update automatically.

**Add a new sheet to the XLSX.** Extend `export_xlsx` with a new `wb.create_sheet("...")` block using the same header/border/font pattern.

**Add a new tab to the browser.** Three touch-points: a `<div class="tab" data-tab="...">` in the tab bar, a `<div class="tab-pane" id="pane-...">` in main, and the corresponding render logic. `switchTab()` handles show/hide; add a line there to call your render function. Add an entry to `state` for any selection set and initialise it in `ingestFiles`.

## 5. Feature roadmap

Ordered roughly by dependency and value.

### Tier 1 — library-wide summarisation ✅ DONE

- Per-vehicle summarisation (mass, chassis, engine, gearbox, suspension, tires) ✅
- Tire catalogue (unique footprints + car attribution) ✅
- Curve extraction (engine torque/power, damper bump/rebound) ✅
- XLSX export (Vehicles / Tires / Curves sheets) ✅
- HTML browser: Index, Tires, Curves, Detail tabs ✅
- Engine fields (idle_rpm, max_rpm, displacement, configuration) ✅
- Completeness % column ✅
- Structural validation (--validate CLI flag) ✅
- Physical sanity-check suite (check subcommand) ✅
- Two-car diff view (Diff tab in browser + curves overlay) ✅
- Pacejka Magic Formula visualisation (Pacejka tab) ✅

### Tier 2 — fingerprint and visual comparison ✅ PARTIALLY DONE

- **Handling fingerprint radar chart** ✅ — 8-axis normalised polar chart in browser + `fingerprint.json` + XLSX Fingerprint sheet
- **Curated merge** — click-to-pick at every node: "take this field from A", "from B", "average", or "keep A's bounds, B's shape" for curves. Output is a new SVJ document with a `_provenance` sidecar. *Not started.*
- **Donor search** — given a partial SVJ, find the k nearest neighbours in the library by mass, wheelbase, era, drivetrain, and topology. Suggest donor values for each missing field with uncertainty bands. *Not started.*

### Tier 3 — validation and QA

**Completeness heatmap.** Per car, per subtree, `filled / (filled + missing)`. Aggregate a library-wide heatmap (cars × subtrees) in the browser — currently only per-car % is shown in the Index table.

**Outlier detection.** For each numeric field, compute the distribution within peer cohorts (defined by drive type and mass class). Flag values ≥ 3σ from the cohort median. Catches unit errors (kgf vs N, mm vs m) and bad conversions instantly.

**Schema validation in browser.** Run `svj-py/validator.py` per file at ingest time and surface failures alongside parse errors. Currently Python-only via `--validate`.

### Tier 4 — derived insights ✅ PARTIALLY DONE

**Handling fingerprint** ✅ — see Tier 2 above (landed ahead of schedule).

**Computed characteristics per car.** Unsprung mass per corner, sprung/unsprung ratio, wheel rate from spring rate + motion ratio (needs motion ratio — either from hardpoints or an `_est` field), front/rear natural frequencies, static weight distribution from hardpoints, theoretical top speed from gearing + power.

**Fingerprint extensions.** The current 8 axes cover the most available data. With richer libraries: add power-to-weight, brake disc size, unsprung mass fraction, gear spread ratio.

### Tier 5 — nice-to-have

**Lineage tracker.** Where did each SVJ come from? Map `source SVJ → AC folder → converter version → date`. Either a sidecar file or a `_lineage` block in metadata.

**Template seeder.** Pick a reference car + override a few fields (new mass, new wheelbase) → generate a partial SVJ skeleton for a new car, with `_est: true` marks everywhere untouched.

**Export bridges.** Once a curated SVJ is clean, emit JBeam (BeamNG), CarSim par-files, VI-CRT, or Simumak inputs via Jinja templates. Belongs in a sibling tool (`svj_export_*`), not this one.

## 6. Testing strategy (when it grows)

Today: verified against the 7 bundled examples in `test_library_multilevel.zip`. Each case covers a different topology, drivetrain, and era. Zero errors reported.

Recommended path when adding features:

1. **Unit tests** on the pure helpers (`_tire_key`, `_tire_label`, `_peak_of_curve`, `_power_curve_from_torque`, `_interp_curve`) with numeric-equivalence assertions.
2. **Fixture tests** with the bundled examples as golden inputs. Snapshot `index.json`, `tires.json`, `fingerprint.json` outputs; diff on every change.
3. **Property tests** (hypothesis) for `summarize_vehicle` invariants: front weight fraction in [0, 1], peak torque/power rpm within torque-curve rpm range, tire identity tuple stable under equivalent reorderings.
4. **Cross-tool parity.** A small Node script that loads the browser's `summarize` and `fpVehicleValues` via `jsdom` and diffs their output against `summarize_vehicle` / `compute_fingerprint` on the same doc.

## 7. Tech debt acknowledged

- No package install (`pyproject.toml`) for `svj_analyze.py` yet. It's one file on purpose.
- No schema-driven code generation — Python and JS are hand-synced. `FP_DIM_DEFS` (Python) and `FP_DIMS` (JS) must be kept in sync manually.
- No streaming XLSX writer — the whole workbook is built in memory. Fine up to ~10 000 cars.
- Fingerprint normalisation is per-loaded-library (browser) / per-run (Python) — results shift as the library grows. A fixed reference percentile file would make scores stable across runs.
- CSS is inline in the HTML file.
- No theme switcher. The current palette is a dark theme; a light variant is a 20-minute edit of the `:root` variables at the top.

## 8. Out-of-scope (intentionally)

- **AC → SVJ conversion.** Lives in `ac_to_svj_*` converters.
- **SVJ → target-format export.** A future `svj_export` tool (JBeam, CarSim, VI-CRT, Simumak).
- **3-D geometry visualisation.** Lives in `svj_viewer_v4.0.html` / `svj_library_3d.html`.
- **Schema evolution.** Owned by the SVJ spec itself.

## 9. Suggested next issues

Ordered by effort vs. value:

1. **Fingerprint: add power-to-weight axis.** The value exists in `power_to_weight_kW_per_tonne`; add it as a 9th axis in `FP_DIM_DEFS` + `FP_DIMS`. 30 min.
2. **Completeness heatmap tab.** Show a grid of cars × subtrees with colour-coding by fill rate. Uses only already-extracted fields. One new tab, ~100 lines of JS + corresponding Python helper. 2–3 h.
3. **Outlier detection CLI + browser badge.** Python: compute per-cohort σ, return a list of `{car, field, value, cohort_median, z_score}`. Browser: show a small ⚠ badge in Index rows that have flagged fields. 4–6 h.
4. **Donor search.** Given a vehicle record with null fields, rank library cars by Euclidean distance in the flat numeric space (mass, wheelbase, track, spring rates, etc.), weighted by data availability. Return top-k with per-field uncertainty. 1 day.
5. **Curated merge.** Two-pane editor — car A on the left, car B on the right, merged output in the centre. Click to pick a field source; save as new `.svj.json` with `_provenance` sidecar. The biggest Tier 2 feature; start with read-only diff (already done) and add the merge layer on top. 2–3 days.

## 10. Reference

- SVJ specification: `svjrepo/spec/SVJ_Spec.md`
- JSON schema: `svjrepo/schema/svj.schema.json`
- Validator: `svjrepo/svj-py/svj/validator.py`
- 3D geometry viewer: `svj_viewer_v4.0.html`, `svj_library_3d.html`
- AC converter: `ac_to_svj/AC_to_SVJ-main/`
