# Contributing to svj-analyze

Thanks for your interest in helping out. This project is small and
deliberately low-ceremony; the guidelines below exist mostly to keep the
Python CLI and the HTML browser in sync and to keep the repo friendly for
future contributors.

## Ground rules

- **By submitting a pull request, you agree to license your contribution
  under the Apache License, Version 2.0** (the project's license). No CLA
  is required — the Apache License itself covers contributor grants.
- Be kind. The [Code of Conduct](./CODE_OF_CONDUCT.md) applies to all
  issue threads, pull requests, and discussions.
- Keep changes focused. One topic per pull request.

## Development setup

```bash
git clone https://github.com/RFloEng/svj-analyze.git
cd svj-analyze
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install flake8               # lint (CI runs this)
```

Smoke-test the CLI against the bundled demo zip:

```bash
python svj_analyze.py examples/test_library_multilevel.zip --out /tmp/svj_report
```

Open the HTML browser directly in any modern browser — no build step.

## Keeping Python and JS in sync

The Python summariser (`summarize_vehicle` in `svj_analyze.py`) and the
JavaScript summariser (`summarize` in `svj_library_browser.html`) must
produce the same output for the same SVJ document. Any schema-reading
change requires edits in **both** places, plus:

- new table columns → update `VEHICLE_COLUMNS` (Python) **and** `COLS`
  (JS);
- new curve families → update `extract_curves` (Python) **and** the
  curve-kind switch in `renderCurves` (JS), plus the `<select>` options.

See `MANUAL.md` for the full architecture overview.

## Coding style

- Python: PEP 8, 4-space indent, type-hinted where it helps. `flake8` runs
  in CI with the project config at `.flake8` (or sensible defaults if that
  file is absent).
- JavaScript: 2-space indent, semicolons, no frameworks. Keep the browser
  file self-contained — no build step, no bundler.
- Markdown: one sentence per paragraph is fine; no strict wrapping rule.

## Commit / PR hygiene

- Commit messages: imperative mood ("Add zip support"), not past tense.
- Reference issue numbers in the body when relevant.
- Pull requests should:
  1. Describe the problem and the approach (a paragraph is usually enough);
  2. Include before/after notes for any user-facing change;
  3. Update `CHANGELOG.md` under `## [Unreleased]` — no version bump needed.

## Testing

There is no formal test suite yet. Before pushing, at minimum:

- Run the CLI against `examples/test_library_multilevel.zip` and the seven
  `svjrepo/examples/*.svj.json` if you have the parent repo checked out.
  Both should report `"errors": 0`.
- Open the HTML browser and drop the same zip. Verify all seven vehicles
  appear, the Tires tab shows eight footprints, and the Curves tab plots.

A proper test suite is a welcome contribution.

## Reporting issues

Open a GitHub issue with:

- What you tried, what you expected, what happened.
- If it's a parsing bug, a minimal `.svj.json` that reproduces the
  problem (or a link to one in a public SVJ library).
- Python version and OS for CLI issues; browser + OS for HTML issues.

## Scope

This tool analyses SVJ documents. It is **not** the right place for:

- Assetto Corsa → SVJ conversion (lives in `ac_to_svj` tools).
- SVJ → target-simulator export (JBeam, CarSim, VI-CRT, …) — belongs in a
  sibling `svj_export_*` tool.
- Changes to the SVJ specification itself (lives in the parent
  SVJ-standard-vehicle-json repo).

See the Scope section above for the full out-of-scope list.

## Questions

If you're not sure whether an idea fits, open a draft issue and we'll
figure it out together. It's a small project; we'd rather talk than
merge something that doesn't fit.
