# SBEMimage Engineering Notebook - 2026-03-10

## Persistent Notebook Guidelines (Carry Forward)

These guidelines must be copied into every new notebook file so human contributors and LLM agents have consistent operating instructions.

1. Repository context must always be stated first.
   - SBEMimage is a Python + PyQt desktop application for SEM/SBEM acquisition control.
   - Main entrypoint: `src/sbemimage.py` (also launched by `SBEMimage.bat`).
   - Core high-impact modules: `src/Viewport.py`, `src/MainControls.py`, `src/Acquisition.py`.
   - Hardware adapters live in `src/sem/` and `src/microtome/`.
   - Config model: templates in `src/default_cfg/`, runtime configs in `cfg/`.
   - Acquaintance step: read `Notebook/guidelines.md` before making changes.

2. All repository changes must protect existing functionality.
   - Any new work must avoid breaking current acquisition and operator workflows.
   - Treat unintended side effects as high-risk defects.

3. Implement changes in a modular and reversible way.
   - Prefer isolated components, clear interfaces, and small patch sets.
   - Avoid deep cross-module coupling that makes rollback difficult.

4. Write notes and annotations for low-context readers.
   - Documentation must be understandable to someone new to this codebase.
   - Assume an LLM with write access may rely on these notes as operating context.

5. Every notebook must include a carry-forward "Major Changes Implemented" section.
   - Build this section by scanning previous notebooks so change history is preserved.

6. Every new notebook must retain these guidelines.
   - Keep them at the top or bottom, but always present and easy to find.

7. Before coding, review developer conventions.
   - Check `Notebook/guidelines.md` and the development docs link it contains.

## Repository Context Snapshot (2026-03-10)

- Objective: rework SBEMimage for reliability, operator safety, and large-ROI usability on GEMINISEM acquisitions without disrupting core acquisition behavior.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Rework constraint: prioritize stability, reversibility, and regression safety before deeper refactors.
- Current carry-forward focus: continue from the polygon ROI / deferred-materialization work, the KLAB UI usability pass, and the remaining grid / overview workflow defects captured on 2026-03-09.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `ENGINEERING_NOTEBOOK_2026-03-03.md`, `ENGINEERING_NOTEBOOK_2026-03-04.md`, `ENGINEERING_NOTEBOOK_2026-03-05.md`, `ENGINEERING_NOTEBOOK_2026-03-06.md`, and `ENGINEERING_NOTEBOOK_2026-03-09.md`.

### Implemented change groups

- [x] Acquisition reliability and diagnostics
  - Added `src/acq_guardrails.py`.
  - Added OV diagnostics and guardrail checks.
  - Added stage-arrival validation and motion sanity checks.
  - Added grid acquisition reliability hotfixes in `src/Acquisition.py` for loop/error-state gating and safer tile progression.

- [x] Viewport acquisition control updates
  - `Acquire Grid` from viewport right-click runs asynchronously.
  - Added right-click `Pause acquisition...` on grids with Main Controls pause flow consistency.

- [x] Spatial provenance and registration foundations
  - Added acquired/locked/timestamp state for grids and OVs.
  - Persisted provenance state through config load/save paths.
  - Registration export prefers acquired coordinates when available.
  - Fixed tile registration origin calculation bug.

- [x] New Project workflow in Main Controls
  - Added guided `New Project...` flow with config/base-directory setup and reset/preview logic.

- [x] Experimental KLAB UI path
  - Added KLAB stylesheet path and startup toggle flow.
  - Added KLAB-only geometry/spacing tuning for Main Controls and Viewport elements.
  - Added startup Config dialog option (`klab gui`) with lightweight bird animation when enabled.
  - Set default KLAB startup state to unchecked (`use_klab_ui = False` by default).

- [x] Global UI change (native + KLAB)
  - Removed the top toolbar row containing the `Create New Project...` icon action in Main Controls.

- [x] Polygon ROI workflow in Viewport
  - Added ROI tools row with `Rectangle`, `Circle`, `Triangle`, `Draw your own`, and `Import`.
  - Implemented polygon-backed grids as masked rectangular carrier grids.
  - Added predefined-shape resizing, custom/imported vertex editing, SVG import, SVG deletion, and config persistence.
  - Disabled manual rows/columns editing for polygon-backed grids and preserved polygon perimeters across settings changes.

- [x] Large-ROI protection flow
  - Added tile-count guardrails for large polygon ROIs.
  - Added deferred polygon ROI mode to avoid immediate materialization of extremely large grids.
  - Added persistence and load-time auto-defer for oversized legacy polygon grids.
  - Updated viewport and Main Controls handling so deferred ROIs remain visible/selectable without full tile expansion.

## Latest Known Validation State (Carry-Forward)

- [x] Manual grid acquisition from viewport supports pause control without freezing the viewport.
- [x] KLAB and native UI modes are selectable at startup via configuration dialog.
- [x] Config persistence validation completed for guardrail keys, OV fallback/default keys, viewport render keys, and OV/grid provenance persistence.
- [x] Startup dialog validation completed: default fallback is unchecked, config-driven auto-check works, and the bird animation only runs when `klab gui` is enabled.
- [x] Polygon ROI baseline workflow is implemented and basic interaction/persistence wiring exists.
- [x] Large-ROI deferred workflow was exercised and documented through 2026-03-09.
- [ ] The current local tree has additional uncommitted behavior changes that still need runtime validation today.

## Current Local Working Tree Snapshot (2026-03-10)

- Branch: `master`
- Latest committed baseline: `84b4b04` (`KLAB UI updates: startup animation, default unchecked, and layout refinements`)
- Local state: substantial uncommitted source changes remain in core files, plus important untracked local helper files.

### Modified tracked files currently in the worktree

- `gui/klab.qss`
- `src/Acquisition.py`
- `src/Grid.py`
- `src/GridManager.py`
- `src/MainControls.py`
- `src/Viewport.py`
- `src/config_template.py`
- `src/default_cfg/default.ini`
- `src/dialog/ConfigDlg.py`
- `src/dialog/GridSettingsDlg.py`
- `src/dialog/PreStackDlg.py`
- `src/sbemimage.py`

### Untracked local files currently present

- `Notebook/ENGINEERING_NOTEBOOK_2026-03-06.md`
- `Notebook/ENGINEERING_NOTEBOOK_2026-03-09.md`
- `gui/klab_spin_arrow_up.svg`
- `src/klab_ui.py`
- `src/viewport_polygon_roi.py`

### High-signal local implementation state (code review only; not runtime-validated today)

- `src/Acquisition.py`
  - Added single-surface rerun state flags and logic for explicit overwrite handling on reruns of `number_slices == 0`.
  - Added `single_surface_output_exists()` to detect stale/conflicting output files before using the "Continue acquisition" flow.
  - Preserves completed-grid progress for successful single-surface runs so later continuation can target only newly added grids on the same surface.

- `src/dialog/PreStackDlg.py`
  - `Continue acquisition` is now shown only when the acquisition is paused and there is no conflicting single-surface output on disk.

- `src/Grid.py`, `src/GridManager.py`, `src/dialog/GridSettingsDlg.py`, `src/Viewport.py`
  - Polygon ROI state is now represented explicitly with persisted shape metadata (`roi_shape_type`, `roi_shape_name`, `roi_points_norm`, materialized/deferred state, and estimated deferred layout values).
  - Deferred polygon grids can load as lightweight placeholders, remain visible based on true ROI bounds, and round-trip through config save/load.
  - Grid Settings now supports `Keep Deferred` versus `Materialize Grid` for polygon ROIs and preserves rectangular grid footprint when tile geometry changes.

- `src/default_cfg/default.ini` and `src/config_template.py`
  - Config schema has been extended for polygon ROI persistence and imported polygon shape library persistence.
  - `CFG_NUMBER_KEYS` was increased from `249` to `277`.

- `src/dialog/ConfigDlg.py`
  - Startup config list is sorted.
  - Missing/invalid `status.dat` now falls back to the read-only default configuration instead of an arbitrary first `.ini`.
  - KLAB startup animation frames were refreshed.

- `src/klab_ui.py`, `gui/klab.qss`, `src/sbemimage.py`
  - KLAB-only theme polishing is now installed at app startup.
  - The stylesheet adds more compact metrics, disabled-state styling, and custom spinbox arrow treatment.
  - The new `src/klab_ui.py` helper is currently untracked even though `src/sbemimage.py` imports it.

- `src/viewport_polygon_roi.py`
  - Central polygon geometry helper module exists locally for normalization, denormalization, hit-testing, SVG parsing, SVG unit conversion, and ROI bounds helpers.
  - `src/Grid.py` imports this module, so it is also implementation-critical and currently untracked.

## Current Task Checklist (Imported)

### Open workflow / UX issues carried forward from 2026-03-09

- [ ] Issue `2026-03-09-01`: newly created grids default to inactive tiles.
- [ ] Issue `2026-03-09-02`: Overview settings dialog opens on `OV 0` instead of the currently selected overview.
- [ ] Issue `2026-03-09-03`: grid outlines are always visible and obstruct close image inspection.
- [ ] Issue `2026-03-09-04`: right-click grid interactions are inconsistent between polygon grids and standard grids.
- [ ] Issue `2026-03-09-05`: feature alignment is inconsistent across imaging modalities and across separate grids.
- [ ] Issue `2026-03-09-06`: KLAB GUI adaptive font shrinking hurts readability and exposes layout sizing problems.

### Fresh validation tasks implied by the current local tree

- [ ] Validate the single-surface rerun / overwrite behavior in `PreStackDlg` and `Acquisition.py`.
- [ ] Validate the new `single_surface_output_exists()` conflict detection against real paused and already-completed single-surface runs.
- [ ] Validate deferred polygon ROI save/load using the new persisted config keys (`roi_*` and polygon shape library keys).
- [ ] Verify that important local helper files (`src/klab_ui.py`, `src/viewport_polygon_roi.py`, `gui/klab_spin_arrow_up.svg`) are staged before any sync or commit workflow.
- [ ] Recheck KLAB readability after the new compact-on-overflow polisher, especially in fixed-geometry dialogs and dense control rows.

## Session Change Log (2026-03-10)

Use this section to record work completed today.

- [x] Created `ENGINEERING_NOTEBOOK_2026-03-10.md` using the established notebook layout and carry-forward structure.
- [x] Reviewed `Notebook/guidelines.md` and prior engineering notebooks from 2026-03-03, 2026-03-04, 2026-03-05, 2026-03-06, and 2026-03-09 before creating this entry.
- [x] Reviewed the repository structure and reconfirmed the main runtime layout: `src`, `gui`, `cfg`, `Notebook`, and `tests`, with `src/sbemimage.py` as the application entrypoint.
- [x] Audited the current local git state and recorded that work is continuing from a heavily modified local worktree on `master`, not from a clean committed baseline.
- [x] Identified implementation-critical untracked local files that the current source tree already depends on: `src/klab_ui.py`, `src/viewport_polygon_roi.py`, and `gui/klab_spin_arrow_up.svg`.
- [x] Captured the current local worktree themes we are likely to continue today: deferred polygon ROI persistence, grid-settings footprint preservation, single-surface rerun safeguards, startup config fallback behavior, and KLAB UI compaction/readability tuning.

## To Be Continued Today

- [ ] Decide which of the carry-forward issues should be addressed first in today's coding pass.
- [ ] Prefer fixing one operator-visible defect at a time and validating it before broadening scope.
- [ ] Keep an eye on the untracked implementation-critical files before any sync, commit, or branch handoff.

## New Issues Found Today

- Issue ID:
- Title:
- Severity:
- Repro steps:
- Expected:
- Actual:
- Logs:
- Notes:

## Instruction Reminder

Any new notebook created after this one must include:
- the persistent guideline block,
- a carry-forward major changes section,
- and an imported checklist of current tasks.
