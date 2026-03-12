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

8. Every implemented or modified feature must include a step-by-step verification checklist.
   - For every new feature, bug fix, behavior change, or improvement, add a manual test checklist to the notebook.
   - Write it in checkbox format so a user can mark progress step by step while validating the implementation.
   - The checklist must help the user confirm expected behavior and identify likely failure points or regressions.

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

- Branch: `feature/guideline-compliance`
- Latest local commit at `HEAD`: `8b1c5ea` (`changes up until 2026-03-09 including`)
- Commit timing confirmed from git metadata: reflog shows `HEAD@{0}: commit: changes up until 2026-03-09 including`, created on `2026-03-10 13:34:59 +0000`.
- Remote tracking state: local branch is currently ahead of `origin/feature/guideline-compliance` by 1 commit.
- Local state: despite that checkpoint commit, substantial uncommitted source changes still remain in core files, plus important untracked local helper files.

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

- [x] Issue `2026-03-09-01`: code fix implemented in `GridManager.add_new_grid` so newly created active grids start with active tiles; manual validation still required.
- [x] Issue `2026-03-09-02`: code fix implemented in `MainControls.open_ov_dlg` so the Overview Settings dialog opens on the currently selected overview instead of defaulting to `OV 0`; manual validation still required.
- [x] Issue `2026-03-09-03`: code fix implemented in `Viewport` so grid outlines can be shown/hidden with a visible controls-panel toggle and `H`, and the existing `Hide grids` selector state now works; manual validation still required.
- [x] Issue `2026-03-09-04`: code fix implemented in `Viewport` to provide shared copy/paste/duplicate/delete grid actions for both standard and polygon-backed grids; manual validation still required.
- [x] Issue `2026-03-09-06`: code fix implemented across KLAB startup/theme handling so KLAB now runs on a fixed 11pt base font, Main Controls gets more default width headroom, and the KLAB path now reflows crowded fixed-geometry panels with KLAB-only width/label handling instead of relying on font reduction; manual validation still required.

### Fresh validation tasks implied by the current local tree

- [ ] Validate the single-surface rerun / overwrite behavior in `PreStackDlg` and `Acquisition.py`.
- [ ] Validate the new `single_surface_output_exists()` conflict detection against real paused and already-completed single-surface runs.
- [ ] Validate deferred polygon ROI save/load using the new persisted config keys (`roi_*` and polygon shape library keys).
- [ ] Verify that important local helper files (`src/klab_ui.py`, `src/viewport_polygon_roi.py`, `gui/klab_spin_arrow_up.svg`) are staged before any sync or commit workflow.
- [ ] Recheck KLAB readability after the new fixed-geometry reflow pass, especially in Main Controls top summary panels, the Stack acquisition panel, and dense dialogs.

## Session Change Log (2026-03-10)

Use this section to record work completed today.

- [x] Created `ENGINEERING_NOTEBOOK_2026-03-10.md` using the established notebook layout and carry-forward structure.
- [x] Reviewed `Notebook/guidelines.md` and prior engineering notebooks from 2026-03-03, 2026-03-04, 2026-03-05, 2026-03-06, and 2026-03-09 before creating this entry.
- [x] Reviewed the repository structure and reconfirmed the main runtime layout: `src`, `gui`, `cfg`, `Notebook`, and `tests`, with `src/sbemimage.py` as the application entrypoint.
- [x] Audited the current local git state and recorded that work is continuing on `feature/guideline-compliance`, not on `master`, and not from a clean worktree.
- [x] Confirmed from `git log` and `git reflog` that a local checkpoint commit was created today for the work through yesterday: `8b1c5ea` (`changes up until 2026-03-09 including`).
- [x] Identified implementation-critical untracked local files that the current source tree already depends on: `src/klab_ui.py`, `src/viewport_polygon_roi.py`, and `gui/klab_spin_arrow_up.svg`.
- [x] Captured the current local worktree themes we are likely to continue today: deferred polygon ROI persistence, grid-settings footprint preservation, single-surface rerun safeguards, startup config fallback behavior, and KLAB UI compaction/readability tuning.
- [x] Grid creation default-state fix: `src/GridManager.py` now initializes newly created active grids with all tiles active instead of creating an active grid shell with `active_tiles = []`.
- [x] Overview dialog selection fix: `src/MainControls.py` now ignores the boolean payload from Qt button/menu signals and opens `OVSettingsDlg` on the currently selected overview unless an explicit overview index was passed.
- [x] Viewport grid-visibility fix: `src/Viewport.py` now adds a `Show grid lines` toggle in the Viewport controls panel, supports `H` as a quick keyboard toggle, persists the new display state, and correctly honors the pre-existing `Hide grids` selector state during drawing.
- [x] Grid context-menu parity fix: `src/Viewport.py` now uses one shared grid clipboard and shared right-click actions (`Copy`, `Duplicate`, `Delete`, `Paste copied grid here`) for both rectangular grids and polygon-backed grids.
- [x] Issue triage update: removed active issue `2026-03-09-05` from today's backlog after operator confirmation that alignment is now working well and no software change is required.
- [x] KLAB readability fix: `src/sbemimage.py` now fixes KLAB at `11 pt` instead of the earlier shrinking/variable baseline, `src/default_cfg/default.ini` now defaults KLAB to `11 pt` and `128 px` of Main Controls width headroom, and `src/MainControls.py` now enforces a larger minimum KLAB width expansion for Main Controls.
- [x] KLAB theme policy fix: `gui/klab.qss` no longer applies the previous 10.5px / 10px font-shrinking rules for Main Controls and `klabCompact` widgets; compact mode now tightens spacing only.
- [x] KLAB polisher fix: `src/klab_ui.py` now treats overflow by tightening spacing and expanding layout-managed widgets/dialog widths where possible, instead of reducing text size.
- [x] Verification pass: `python -m py_compile src\\klab_ui.py src\\sbemimage.py src\\MainControls.py src\\Viewport.py src\\config_template.py` completed successfully after the KLAB changes.
- [x] Documentation update: `docs/user_interface.md` now lists `H` in the Viewport mouse/key commands table as the shortcut for toggling grid-line visibility.
- [x] KLAB follow-up tuning: `src/Viewport.py` now forces the KLAB-only `Show grid lines` checkbox to use the same row height/vertical spacing rhythm as the existing Viewport toggles, and `src/sbemimage.py` / `src/default_cfg/default.ini` now use `11 pt` as the KLAB default font baseline.
- [x] KLAB Main Controls reflow pass: `src/MainControls.py` now applies a wider KLAB-only Main Controls width floor, reallocates top-row column space, reflows the fixed-geometry `SEM`, `Overviews`, `Tile grids`, `Manual commands`, and `Stack acquisition` panels, and elides overflowed KLAB labels with full tooltips instead of allowing overlap/clipping.
- [x] Verification pass: `python -m py_compile src\\MainControls.py src\\sbemimage.py src\\Viewport.py` completed successfully after the KLAB Main Controls reflow changes.
- [x] KLAB startup regression fix: `src/MainControls.py` no longer passes `self.imaging_condition_store` into `Viewport(...)`; that stale extra positional argument was colliding with the keyword `use_klab_ui` argument and prevented startup with `Viewport.__init__() got multiple values for argument 'use_klab_ui'`.
- [x] KLAB font lock-in: `src/sbemimage.py` now applies a fixed `11 pt` KLAB application font at startup so saved config values or legacy fallbacks can no longer keep KLAB at `12 pt`.
- [x] Stub overview centring assist: `gui/stub_ov_dlg.ui` and `src/dialog/viewport/StubOVDlg.py` now add a `Centre at current stage coordinates` button in the `Acquire Stub Overview` dialog that reads the current microscope stage XY position, writes it into the stub overview centre fields, and warns the user if the stage read fails or returns invalid coordinates.
- [x] Verification pass: `python -m py_compile src\\dialog\\viewport\\StubOVDlg.py` completed successfully and `gui/stub_ov_dlg.ui` parsed successfully with Python's XML parser after the stub overview centring change.
- [x] Viewport grid-pan visibility follow-up: `src/Viewport.py` now falls back to lightweight grid outlines whenever tile previews are temporarily suppressed during panning, drag interactions, or other fast redraw paths, so preview-only grid views no longer disappear mid-interaction.
- [x] Viewport inactive-grid visibility follow-up: inactive rectangular grids now retain a faint dashed footprint during those interaction redraws instead of relying only on labels that are temporarily suppressed.
- [x] Documentation update: `docs/user_interface.md` now notes that preview-only grid views temporarily fall back to outlines during panning/dragging so grids remain visible while preserving redraw responsiveness.
- [x] Stub overview workflow rework: `src/dialog/viewport/StubOVDlg.py` is now modeless instead of application-modal, so the stub dialog no longer hard-locks the viewport while a stub acquisition is running.
- [x] Stub overview acquisition reservation fix: stub acquisition now explicitly sets global acquisition state, restricts conflicting GUI actions through the same `RESTRICT GUI` / `UNRESTRICT GUI` flow used elsewhere, and returns the application to `STATUS IDLE` on success, failure, or abort.
- [x] Stub overview resolution-control fix: `gui/stub_ov_dlg.ui` and `src/dialog/viewport/StubOVDlg.py` now expose direct pixel-size input below magnification and keep magnification / pixel size synchronized in both directions.
- [x] Stub archive persistence: `src/ImportedImage.py`, `src/default_cfg/default.ini`, and `src/config_template.py` now support imported-image `source_kind` metadata so previous completed stub images can persist as tagged archived overlays instead of being overwritten in-place.
- [x] Stub archive workflow helper: added `src/stub_overview_workflow.py` for pure geometry / overlap / archive-label helpers to keep the rework modular and out of the viewport and dialog classes.
- [x] Multi-stub viewport workflow: `src/Viewport.py` now archives the previous active stub as an imported overlay on successful new stub acquisition, renders stub archives under `Show stub OV`, and prevents them from being duplicated under `Show imported`.
- [x] Stub overlap safeguard: starting a new stub overview now checks for overlap against the current active stub and same-mode archived stubs and asks the operator to `Proceed` or `Cancel` before acquisition starts.
- [x] Stub failure-state hardening: `src/acq_func.py` now restores the previous active stub path whenever stub acquisition fails or is aborted, instead of leaving a partial temp-path state behind.
- [x] Stub archive rendering optimization: archived stubs now render through a pyramidal background-image path instead of the generic imported-image transform path, reducing viewport lag after multiple large stub acquisitions.
- [x] Stub layer-order safeguard: archived stubs continue to render in the background stub layer, before overviews and grids, instead of competing with foreground imported overlays.

## Verification Guide - 2026-03-10 Fixes

Use this manual checklist to verify the fixes implemented in this session.

### A. Newly created grids default to active tiles

1. Launch SBEMimage and open the Viewport tab.
2. Create a new standard rectangular grid with the normal `Alt`-drag workflow.
3. Click the new grid once to select it.
4. Visually confirm the grid is immediately acquisition-ready without first needing `Select all tiles`.
5. Right-click the new grid and confirm `Deselect all tiles in GRID n` is available as a meaningful action on the newly created grid.
6. If safe in the current environment, trigger `Acquire Grid GRID n` and confirm the run does not behave like an empty-selection grid.

Expected result:
- A newly created active grid starts with active tiles immediately.
- No extra post-creation activation step is required before acquisition.

### B. Overview Settings opens the currently selected overview

- [x] In Main Controls, go to the `Overviews` panel.
- [x] Use the overview selector to choose an overview other than `OV 0`.
- [x] Click the Overviews settings button in the panel.
- [x] Confirm the Overview Settings dialog opens with the same overview selected in the dialog selector.
- [x] Repeat the same check from the menu entry for Overview Settings.
- [x] In the Viewport, right-click an overview and use `Open settings of OV n`.
- [x] Confirm that explicit overview-targeted opening still works correctly.

Expected result:
- [x] The dialog opens on the currently selected overview from Main Controls.
- [x] Directly targeted overview openings from the Viewport still open the requested OV.

### C. Grid outlines can be hidden and restored quickly

- [x] In the Viewport tab, make sure at least one grid is visible.
- [x] Locate the new `Show grid lines` checkbox in the Viewport controls panel next to the other display toggles.
- [x] Uncheck `Show grid lines`.
- [x] Confirm ordinary grid outlines disappear.
- [x] If a polygon-backed grid is visible, confirm its polygon outline also disappears.
- [x] If tile previews are enabled, confirm the underlying preview imagery remains visible while outlines are hidden.
- [x] Press `H`.
- [ ] Confirm the grid-outline state toggles immediately.
- [x] Use the grid selector dropdown and choose `Hide grids`.
- [x] Confirm grids are actually hidden now, rather than still being drawn as before.

Expected result:
- [x] The checkbox and `H` toggle the same display state.
- [x] `Hide grids` in the selector now truly hides grids.
- [x] Hiding grid lines improves image inspection without requiring permanent selector changes.

### D. Grid right-click parity between rectangular and polygon grids

- [x] Create one standard rectangular grid and one polygon-backed grid.
- [x] Right-click the rectangular grid and note the available grid actions.
- [x] Right-click the polygon-backed grid and compare the same area of the context menu.
- [x] Confirm both now expose the same grid-level clipboard actions: `Copy`, `Duplicate`, `Delete`, and `Paste copied grid here`.
- [x] Select the standard rectangular grid, use `Copy`, then right-click empty viewport space and use `Paste copied grid here`.
- [x] Confirm a new rectangular grid is created with the copied grid geometry/settings.
- [x] Select the polygon-backed grid, use `Copy`, then paste it elsewhere in the viewport.
- [x] Confirm the pasted grid preserves the polygon ROI shape and grid settings.
- [x] Select a grid that is not the last grid index and confirm `Delete` is disabled.
- [x] Select the last grid index, use `Delete`, and confirm the deletion path works with the usual safety confirmation.
- [x] Select a grid and test keyboard parity: `Ctrl+C`, `Ctrl+V`, and `Delete`.

Expected result:
- [x] Standard grids and polygon-backed grids share the same core right-click grid workflow.
- [x] Only the last grid remains deletable, regardless of grid type.
- [x] Copy/paste/duplicate behave at the grid level rather than only for polygon ROI shapes.

### E. KLAB readability without adaptive font shrinking

1. Launch SBEMimage with `Use KLAB UI (experimental)` enabled.
2. Confirm KLAB text now starts from a fixed `11 pt` baseline instead of the previous `12 pt` behavior and no longer drops to the old tiny compact-font appearance in dense panels.
3. In Main Controls, inspect the top panels (`SEM`, `Overviews`, `Tile grids`, `Manual commands`) and the Stack acquisition panel.
4. In the top summary panels, confirm device names, beam settings, overview/grid values, and the `Manual commands` panel title/buttons are visible without clipping into neighboring controls.
5. In `Stack acquisition`, confirm the `Target number...` / `Slice thickness` area no longer collides, and the right-side metrics (`Electron dose`, `Tile acquisition area`, `Z depth`, `Data volume`, total duration, completion estimate) remain readable without running into one another.
6. Hover any truncated KLAB label in those panels and confirm a tooltip shows the full text/value.
7. Confirm labels such as `E-mail monitoring`, `Disk mirroring`, `Image monitoring`, `Plasma cleaner`, `Show stage position`, and long status/value labels remain readable without tiny fallback text.
8. Open the Viewport and confirm the `Show grid lines`, `Show labels`, and `Show stage position` checkboxes now have the same vertical row spacing and no overlap in KLAB mode.
9. Confirm the rest of the Viewport controls remain readable with the revised KLAB font size.
10. Open a few dialogs that previously relied on the compact/shrunk look, especially configuration and settings dialogs.
11. Confirm that where layout-managed dialogs need more width, the dialog expands rather than shrinking the text.
12. Confirm text is not being reduced below the new practical KLAB minimum and that remaining tight spots, if any, are caused by geometry limits rather than adaptive font collapse.
13. Relaunch SBEMimage in KLAB mode and confirm Main Controls and Viewport both open normally without a startup exception.

Expected result:
- KLAB no longer solves overflow by shrinking text to the old hard-to-read compact sizes.
- KLAB now uses a fixed `11 pt` baseline instead of `12 pt`.
- Main Controls uses more KLAB-only width headroom and cleaner per-panel geometry rather than crowding text into the old native coordinates.
- When a KLAB label still exceeds its lane, it is ellided cleanly and exposes the full text on hover instead of overlapping adjacent controls.
- The Viewport `Show grid lines` checkbox no longer crowds or overlaps the row beneath it in KLAB mode.
- Main Controls has more width headroom in KLAB mode.
- Layout-managed dialogs prefer width growth or spacing adjustments over font reduction.
- Any remaining overflow should be isolated, visible, and fixable with targeted geometry work rather than hidden behind unreadably small text.
- KLAB startup no longer fails with `Viewport.__init__() got multiple values for argument 'use_klab_ui'`.

### F. User-interface documentation includes the new `H` shortcut

- [x] Open `docs/user_interface.md`.
- [x] Navigate to the `Mouse and key commands` section.
- [x] In the `Viewport` table, locate the row for the `H` key.
- [x] Confirm the action text states that `H` toggles grid lines between shown and hidden.
- [x] If you compare the documentation against the running application, press `H` in the Viewport and confirm the documented behavior matches the implemented behavior.

Expected result:
- [x] The Viewport command table documents `H` as the grid-line visibility toggle.
- [x] The markdown documentation and the current UI behavior are consistent.

### G. Stub overview centre can be populated from the current stage coordinates

- [x] Move the microscope stage to a known XY position and note the current stage coordinates shown elsewhere in the application or on the microscope side.
- [x] Open the `Acquire Stub Overview` dialog from the Viewport workflow.
- [x] Confirm a new button labeled `Centre at current stage coordinates` is shown directly below the `Centre (X, Y)` inputs.
- [x] Enter temporary placeholder values into the stub overview `X` and `Y` centre fields so the change is obvious.
- [x] Click `Centre at current stage coordinates`.
- [x] Confirm the `X` and `Y` centre fields update to the microscope's current stage XY position, rounded to the dialog's integer micrometre fields.
- [x] If safe in the current environment, start stub overview acquisition and confirm it uses the newly populated centre coordinates.
- [x] While the stub overview acquisition is running, confirm the new centring button is disabled together with the centre coordinate fields.
- [x] If a stage read can be safely made unavailable or forced to fail, confirm the dialog shows a warning instead of writing invalid coordinates into the centre fields.

Expected result:
- [ ] Operators can centre a stub overview at the live stage position without manually copying X/Y values into the dialog.
- [ ] The button reduces coordinate-entry friction but does not bypass stage-read failure visibility.

### G. Preview-only grids stay visible while panning or dragging

1. Launch SBEMimage and open the Viewport tab.
2. Make sure at least one active grid is visible in the workspace.
3. Set the tile preview selector to `Tile previews, no grid(s)`.
4. Pan the viewport with normal left-click drag.
5. Confirm the grid does not disappear during the drag; it may temporarily switch from preview imagery to a lightweight outline.
6. Release the mouse and confirm the normal preview view returns.
7. Repeat the same check with `Tile previews with gaps`.
8. If practical, rotate or drag a grid and confirm the grid remains visible throughout the interaction rather than blanking out.
9. If an inactive rectangular grid is available, pan again and confirm it still has a faint dashed footprint during the interaction instead of disappearing completely.

Expected result:
- Preview-only grid modes no longer blank the grid layer during panning or drag redraws.
- SBEMimage may temporarily substitute outlines for previews during interaction, but the grid footprint stays visible the whole time.
- Once the interaction ends, the normal preview presentation returns.

## To Be Continued Today

- [x] Decide which of the carry-forward issues should be addressed first in today's coding pass.
- [x] Prefer fixing one operator-visible defect at a time and validating it before broadening scope.
- [x] Keep an eye on the untracked implementation-critical files before any sync, commit, or branch handoff.

## Verification Guide - Stub Overview Workflow Rework

### A. Viewport interaction during stub acquisition

- [ ] Open `Acquire Stub Overview`.
- [ ] Start a multi-tile stub acquisition.
- [ ] While acquisition is running, left-drag in the viewport.
- [ ] Confirm the viewport pans normally.
- [ ] Try to move a grid with `Alt`-drag during the run.
- [ ] Confirm editing / moving actions remain blocked.
- [ ] Try to start another acquisition workflow from Main Controls or the Viewport.
- [ ] Confirm it is blocked while stub acquisition is active.

Expected result:
- [ ] Panning still works during stub acquisition.
- [ ] Conflicting acquisition or edit workflows do not start.

### B. Multiple stub coexistence

- [ ] Acquire a first SEM stub.
- [ ] Acquire a second SEM stub at a different position.
- [ ] Confirm the first stub remains visible as an archived overlay when `Show stub OV` is enabled.
- [ ] Confirm the newest stub is still the active/current stub.
- [ ] Save the config, restart SBEMimage, and reload the same config.
- [ ] Confirm both stub regions are still present.

Expected result:
- [ ] Older stubs persist as archived overlays.
- [ ] The latest stub remains the active stub entry used by the normal stub workflow.

### C. Overlap warning

- [ ] Acquire a stub.
- [ ] Start a second stub acquisition whose footprint overlaps the first stub region.
- [ ] Confirm an overlap warning dialog appears.
- [ ] Click `Cancel` and confirm acquisition does not start.
- [ ] Start again and click `Proceed`.
- [ ] Confirm acquisition starts normally.

Expected result:
- [ ] Overlap is detected before acquisition begins.
- [ ] The operator can either cancel safely or proceed explicitly.

### D. Pixel size / magnification synchronization

- [ ] Open `Acquire Stub Overview`.
- [ ] Change magnification and confirm pixel size updates.
- [ ] Change pixel size and confirm magnification display updates.
- [ ] Confirm dimensions and duration labels update in both cases.
- [ ] If LM mode is available, repeat the same check in LM mode and confirm the displayed pixel size reflects the applied hardware value after start.

Expected result:
- [ ] Pixel size and magnification remain synchronized.
- [ ] Dimension estimates remain consistent with the chosen stub acquisition settings.

### E. Archived stub rendering performance and layer order

- [ ] Acquire at least three large stub overviews in sequence so that two or more older stubs are archived.
- [ ] Enable `Show stub OV`.
- [ ] Pan and zoom in the viewport and confirm responsiveness remains close to the normal single-stub case.
- [ ] Confirm archived stubs remain behind overview images and grids rather than drawing over them.
- [ ] If `Show imported` is also enabled, confirm archived stubs are not duplicated in the foreground imported-image layer.
- [ ] Open the imported-images modification dialog and confirm archived stubs appear there as individually deletable `Stub archive ...` entries.

Expected result:
- [ ] Multiple archived stubs do not make the viewport pathologically slow.
- [ ] Archived stubs stay in the background image layer.
- [ ] Archived stubs can still be deleted individually through the imported-images workflow.

## Session Log - Shared Imaging-Condition Presets

- Added a shared imaging-condition preset store in `cfg/imaging_conditions/` with one JSON file per preset and atomic writes.
- Added shared preset UI and controller wiring to `Grid Settings`, `Overview Setup`, and `Acquire Stub Overview`.
- Added a modal `Manage Imaging Conditions` dialog for edit, duplicate, and delete operations.
- Expanded the stub overview dialog with frame-size and dwell-time controls so the same portable imaging core can be saved and reapplied there too.
- Changed the stub overview dialog to keep imaging-condition edits in widget state until `Acquire`, instead of mutating the stored stub overview immediately while the dialog is open.
- Fixed `OverviewManager.save_to_cfg()` to persist stub dwell-time selector keys (`stub_ov_dwell_time_selector` / `stub_ov_lm_dwell_time_selector`) so stub imaging settings round-trip correctly.
- Added focused automated coverage in `tests/test_imaging_conditions.py` for store CRUD, widget-only apply behavior, and stub selector persistence.

### F. Shared imaging-condition presets across grid, overview, and stub dialogs

- [ ] Open `Grid Settings` for an existing grid.
- [ ] Click `Save current settings as...`, enter a preset name, and confirm the preset appears in `Saved imaging condition`.
- [ ] Change the grid frame size, pixel size, and dwell time to different values without clicking `Save settings for GRID ...`.
- [ ] Reapply the saved preset with `Apply saved settings`.
- [ ] Confirm the dialog widgets return to the saved imaging values.
- [ ] Confirm the underlying grid only changes after clicking `Save settings for GRID ...`.
- [ ] Open `Overview Setup`, select an overview, and repeat the same save/apply check there.
- [ ] Confirm overview widgets update immediately but the overview model only commits after `Save settings for OV ...`.
- [ ] Open `Acquire Stub Overview`.
- [ ] Confirm new `Frame size (px)` and `Dwell time (us)` controls are present in the acquisition-parameter block.
- [ ] Save a stub imaging preset and reapply it.
- [ ] Confirm the stub dialog widgets update immediately but the stored stub overview is not committed until `Acquire`.
- [ ] If LM mode is available, switch to LM mode and confirm `Get current settings from SEM` becomes disabled while saved presets remain usable.
- [ ] Click `Manage...` from any of the three dialogs.
- [ ] Edit one preset value, duplicate another preset, and delete a third preset.
- [ ] Confirm all open preset dropdowns refresh cleanly after closing the manager dialog.
- [ ] Save the config, restart SBEMimage, and confirm the same saved imaging presets are still available.

Expected result:
- [ ] Grid, overview, and stub dialogs share one consistent imaging-condition preset workflow.
- [ ] Applying a preset changes widgets immediately but only commits to the underlying acquisition model at the existing save/acquire point for that dialog.
- [ ] Presets remain globally available for the local installation from `cfg/imaging_conditions/`.
- [ ] Stub frame-size and dwell-time selector settings persist correctly across save/restart.

## Session Log - Acquisition Manager

- Added `src/AcquisitionGroupManager.py` as a dedicated UI/grouping layer for acquisition presentation state. It stores group hierarchy, group colours, grid/overview assignments, expanded-state persistence, summary helpers, and effective colour resolution without changing acquisition order.
- Extended the config schema with a new `[acquisition_manager]` section in `src/default_cfg/default.ini` and corresponding template counts in `src/config_template.py`.
- Added persisted keys:
  - `group_nodes`
  - `grid_group_ids`
  - `ov_group_ids`
- Wired `MainControls` and `Viewport` to instantiate, refresh, and save the new acquisition-group manager alongside the existing overview/grid managers.
- Added a new `Acquisition manager` button to the Viewport controls panel and replaced the old viewport context-menu entry `Open OV queue panel` with `Open acquisition manager`.
- Added `src/dialog/viewport/AcquisitionManagerDlg.py` as a modeless grouped tree/inspector dialog and `src/dialog/viewport/TileActivationMap.py` as a lightweight tile-activation widget for grid inspection.
- Added shared Viewport helpers so the dialog can reuse the current delete / clear / lock / acquire semantics for overviews and grids instead of introducing a second behavior path.
- Group colour propagation is now visual-only: grouped grids use the group colour in the Viewport and Main Controls selector icons, but raw grid colour is still preserved and special temporary colour `13` still wins when present.
- Grouped overviews keep the existing blue OV styling and now display a small group-colour accent in the Viewport.
- `GridSettingsDlg` now accepts optional `acq_groups` context and disables manual colour selection when a grid is currently group-managed.
- Added focused automated coverage in `tests/test_acquisition_group_manager.py` for config round-tripping, inventory sync, dissolve-group behavior, effective colour precedence, summary counting, and a lightweight dialog smoke path.
- Verification commands completed:
  - `python -m py_compile src\AcquisitionGroupManager.py src\dialog\viewport\TileActivationMap.py src\dialog\viewport\AcquisitionManagerDlg.py src\dialog\GridSettingsDlg.py src\Viewport.py src\MainControls.py`
  - `$env:PYTHONPATH='src;tests'; pytest tests/test_load_config.py tests/test_acquisition_group_manager.py -q`
  - `$env:PYTHONPATH='src;tests'; pytest tests/test_grid_manager.py tests/test_overview_manager.py tests/test_load_config.py -q`

### G. Acquisition Manager verification checklist

- [ ] Launch SBEMimage and open the Viewport.
- [ ] Confirm a new `Acquisition manager` button appears below the Viewport grid selector area.
- [ ] Click `Acquisition manager` and confirm the dialog opens modelessly without blocking the rest of the UI.
- [ ] Confirm the left tree shows any existing groups plus the fixed `Ungrouped overviews` and `Ungrouped grids` buckets.
- [ ] Create a new top-level group and confirm it receives a visible colour chip in the tree.
- [ ] Create a subgroup under that group and confirm it appears nested below the parent.
- [ ] Drag at least one overview and one grid into the new group or subgroup.
- [ ] Confirm grouped grids adopt the group colour in the Viewport and in the Main Controls grid selector icons.
- [ ] Confirm grouped overviews remain blue in the Viewport but show the new group-colour accent marker.
- [ ] Toggle an overview inactive from the tree and confirm the active state updates immediately without changing acquisition order.
- [ ] Toggle a grid inactive from the tree and confirm stack estimates / active counts update as usual.
- [ ] Select a group row, toggle its checkbox, and confirm the state cascades to descendant overviews and grids.
- [ ] Select a grouped grid in the dialog and confirm the right-side inspector shows group path, acquisition status, frame size, pixel size, dwell time, interval data, and active tile count.
- [ ] Use the tile activation map to disable one tile and confirm the tile becomes inactive in the underlying grid state and in the Viewport.
- [ ] Use `Select all tiles` and `Deselect all tiles` from the grid inspector and confirm they follow the existing prompt/behavior path.
- [ ] Use `Open settings` from a grouped grid and confirm the Grid Settings dialog opens normally.
- [ ] In Grid Settings for a grouped grid, confirm the colour selector is disabled and indicates that the visible colour is group-managed.
- [ ] Use `Clear image` on an overview and `Clear previews` on a grid from the acquisition manager and confirm the existing clear semantics still apply.
- [ ] Use `Lock` / `Unlock` from the acquisition manager on a previously acquired overview or grid and confirm the same warnings/rules still apply.
- [ ] Try deleting `OV 0` from the acquisition manager and confirm the existing protection message is preserved.
- [ ] Try deleting a non-last overview or non-last grid and confirm the existing deletion-order safeguards are preserved.
- [ ] Start an acquisition, leave the acquisition manager open, and confirm the dialog becomes read-only while remaining visible.
- [ ] While acquisition is running, confirm tree drag/drop, active toggles, tile editing, and destructive actions are disabled.
- [ ] After acquisition stops, confirm the dialog becomes editable again.
- [ ] Save the configuration, restart SBEMimage, reopen the acquisition manager, and confirm the group hierarchy, assignments, colours, and expansion state persist.

Expected result:
- [ ] The acquisition manager provides one central UI for grouping and reviewing overviews and grids without altering the existing acquisition execution order.
- [ ] Active/inactive state changes made in the acquisition manager are reflected everywhere the existing acquisition workflow already reads them.
- [ ] Group colours propagate consistently to grouped grids and overview accents without overwriting stored manual grid colours.
- [ ] The dialog is safe to keep open during acquisition because mutating controls are disabled while the system is busy.

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
