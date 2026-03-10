# SBEMimage Engineering Notebook - 2026-03-06

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

## Repository Context Snapshot (2026-03-06)

- Objective: rework SBEMimage for reliability and performance on large GEMINISEM acquisitions without interrupting current acquisition capability.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Rework constraint: prioritize stability and regression safety before further optimization/refactor.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `PROJECT_REWORK_PLAN.md`, `ENGINEERING_NOTEBOOK_2026-03-04.md`, and `ENGINEERING_NOTEBOOK_2026-03-05.md`.

### Implemented change groups

- [x] Acquisition reliability and diagnostics
  - Added `src/acq_guardrails.py`.
  - Added OV diagnostics and guardrail checks.
  - Added stage-arrival validation and motion sanity checks.
  - Added grid acquisition reliability hotfixes in `src/Acquisition.py` (loop/error-state gating).

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
  - Added startup Config dialog option (`klab gui`) with lightweight animation when enabled.
  - Set default KLAB startup state to unchecked (`use_klab_ui = False` by default).

- [x] Global UI change (native + KLAB)
  - Removed the top toolbar row containing the `Create New Project...` icon action in Main Controls.

### Latest known validation state (carry-forward)

- [x] Manual grid acquisition from viewport supports pause control without freezing the viewport.
- [x] KLAB and native UI modes are selectable at startup via configuration dialog.
- [x] Config persistence validation rerun completed for save/restart, guardrail keys, OV fallback/default keys, viewport render keys, and OV/grid provenance persistence.
- [x] Startup dialog validation completed: default fallback is unchecked, config-driven auto-check works, and the bird animation only runs when `klab gui` is enabled.

## Current Task Checklist (Imported)

### Pending validation checklist (carry-forward)

- [x] Save config and restart app.
- [x] Verify guardrail keys persist: `guardrail_min_mag`, `guardrail_max_mag`, `guardrail_strict`.
- [x] Verify OV fallback/default keys persist: `auto_tile_ov_fallback`, `ov_single_frame_min_mag`, `new_ov_default_active`.
- [x] Verify viewport render keys persist: `render_debug`, `render_antialias`.
- [x] Verify OV/grid lock + acquired provenance state persists.
- [x] Verify startup default for `klab gui` is unchecked when `use_klab_ui = False`.
- [x] Verify `klab gui` auto-check behavior when selected config has `use_klab_ui = True`.
- [x] Verify startup bird animation only runs when `klab gui` is checked and does not affect load responsiveness.

### File-Backed Checks (confirmed in `cfg/checklist.ini`)

- [x] Confirmed `[acq]` guardrail keys persisted: `guardrail_min_mag = 60`, `guardrail_max_mag = 25000`, `guardrail_strict = False`.
- [x] Confirmed `[overviews]` OV fallback/default keys persisted: `auto_tile_ov_fallback = True`, `ov_single_frame_min_mag = 80`, `new_ov_default_active = True`.
- [x] Confirmed `[viewport]` render keys persisted after save/restart: `render_debug = True`, `render_antialias = True`.
- [x] Confirmed `[grids]` provenance persistence keys present after save/restart: `grid_locked`, `grid_acquired`, `grid_last_acq_ts`, `grid_last_acq_result`, `grid_acquired_origin_sx_sy`.
- [x] Confirmed `[overviews]` provenance persistence keys present after save/restart: `ov_locked`, `ov_acquired`, `ov_last_acq_ts`, `ov_last_acq_result`, `ov_acquired_centre_sx_sy`.

## Session Change Log (2026-03-06)

Use this section to record work completed today.

- [x] Created `ENGINEERING_NOTEBOOK_2026-03-06.md` using the established notebook layout and imported carry-forward guidelines, major changes, and current checklist items.
- [x] Polygon ROI feature: added a new ROI tools row at the top of the Viewport controls with `Rectangle`, `Circle`, `Triangle`, `Draw your own`, and `Import`.
- [x] Polygon ROI feature: predefined tools are one-click placement tools that size shapes relative to the current visible field of view rather than using a fixed global size.
- [x] Polygon ROI feature: custom polygon drawing now supports left-click vertex placement and right-click polygon closure.
- [x] Polygon ROI feature: imported SVG polygon/path shapes can be added to the Viewport toolbar and are persisted in config save/load.
- [x] Polygon ROI feature: polygon-backed grids are implemented as normal rectangular grids with auto-derived rows/columns and active-tile masking inside the polygon perimeter.
- [x] Polygon ROI feature: polygon-backed grids use auto-derived rows/columns in Grid Settings; the auto-popup behavior was later removed because it disrupted viewport interaction.
- [x] Polygon ROI feature: predefined shapes expose resize handles; custom/imported polygons expose vertex handles for editing.
- [x] Polygon ROI feature: added ROI shape context actions for copy, paste, duplicate, and delete (delete remains limited to the most recently created grid to avoid unsafe grid-index reordering in the current SBEMimage architecture).
- [x] Polygon ROI startup fix: corrected `Viewport` initialization order so polygon toolbar state exists before the toolbar is constructed during application startup.
- [x] Polygon ROI draw-preview fix: corrected custom polygon preview drawing to use `QPointF` instead of raw NumPy float coordinates, and hardened `vp_draw()` with a `try/finally` painter shutdown so a draw exception does not leave the `QPainter` active.
- [x] Polygon ROI interaction adjustment: in `Draw your own`, the right-click close action now also contributes the final vertex before the polygon is closed, so a sequence like left-left-right produces a triangle as expected.
- [x] Polygon ROI interaction fix: clicking a polygon handle now starts vertex/corner dragging even when that polygon was not already selected, and clicking inside polygon-only masked space now selects the polygon grid.
- [x] Polygon ROI UX fix: removed the automatic `Grid Settings` popup on polygon creation so shape placement does not interrupt viewport interaction.
- [x] Polygon ROI interaction follow-up: plain left-click on a polygon-backed grid now selects the polygon without falling through into viewport panning, and handle hit-testing now uses the same viewport transform as the visible overlay with a larger hit target.
- [x] Polygon ROI SVG import fix: imported SVG shapes now preserve their physical document dimensions on placement by parsing SVG viewport units and converting them into SBEMimage micrometre coordinates instead of using viewport-relative default sizing.
- [x] Polygon ROI toolbar layout tweak: moved the `Import` action to the far right side of the ROI toolbar so it is visually separated from the shape buttons.
- [x] Polygon ROI handle usability tweak: increased the invisible drag hit radius around handles for the currently selected polygon so vertex/corner dragging is easier to trigger without accidental panning.
- [x] Polygon ROI SVG management: added a dedicated `Delete SVG` toolbar action that removes the currently selected imported SVG shape from the ROI toolbar and from config persistence on the next save.
- [x] Large polygon ROI guardrail: polygon creation now estimates tile count before materialization and warns when a polygon would create a very large grid; extremely large ROIs are blocked from immediate full-grid materialization.
- [x] Deferred polygon ROI mode: oversized polygon ROIs can now be created as lightweight deferred placeholders that preserve the ROI perimeter without allocating the full tile grid until the user explicitly materializes it later.
- [x] Deferred polygon ROI persistence: deferred/materialized state and estimated rows/columns/tile count are now saved in config and restored on reload; oversized legacy polygon configs are auto-deferred on load to protect startup responsiveness.
- [x] Oversized polygon crash fix: polygon selection overlays now use ROI bounds rather than tile-corner access, preventing the `IndexError` that occurred when selecting/deleting malformed or oversized polygon grids.
- [x] Grid Settings integration: saving settings for polygon ROIs now offers a `Keep Deferred` versus `Materialize Grid` decision path instead of always expanding the polygon into a full grid.
- [x] Main Controls status update: deferred polygon ROIs now show an estimated grid size summary instead of a misleading placeholder `1 × 1` size.
- [x] Validation update: completed the persistence pass for save/restart, config-backed guardrail and OV fallback/default keys, viewport render toggles, and OV/grid lock-acquired provenance state using `cfg/checklist.ini`.
- [x] Startup dialog fix: corrected missing-`status.dat` fallback so the startup config selection now defaults to `Default Configuration` instead of an arbitrary first `.ini`, which previously caused `klab gui` to appear checked when `checklist.ini` was first in the unsorted list.
- [x] Startup dialog verification: confirmed in an offscreen `ConfigDlg` check that missing-`status.dat` fallback selects `Default Configuration` with `klab gui` unchecked, selecting `checklist.ini` auto-checks it, and the bird animation label/timer only activate when KLAB is enabled.
- [x] Viewport overlay fix: moved the render diagnostics overlay to the top-right of the viewport canvas so it no longer collides visually with the bottom `Controls` panel.

## Verification Guide - Polygon ROI Workflow

### Verified Checklist (implementation-backed)

- [x] Item 1: the ROI toolbar row appears above the existing Viewport controls.
- [x] Item 2: `Rectangle` creates a new polygon-backed grid at a viewport-relative default size, and Grid Settings does not open automatically.
- [x] Item 3: opening Grid Settings manually for a polygon-backed grid disables `Rows` and `Columns` while leaving tile size, overlap, pixel size, dwell time, and rotation editable.
- [x] Item 4: saving polygon-backed grid changes after tile-size or pixel-size edits preserves the polygon perimeter and refreshes the active-tile mask/fill.
- [x] Item 5: `Circle` and `Triangle` polygon-backed grids derive their active tiles from polygon-rectangle intersection rather than the full rectangular carrier area.
- [x] Item 6: `Draw your own` supports left-click vertex placement plus right-click closure, and polygon creation no longer triggers an automatic Grid Settings popup.
- [x] Item 7: plain left-click inside a polygon-backed grid, including masked interior space, selects the polygon grid.
- [x] Item 8: dragging a predefined polygon corner handle resizes the polygon and refreshes the filled tile pattern.
- [x] Item 9: dragging a custom/imported polygon vertex handle updates the polygon geometry and refreshes the filled tile pattern.
- [x] Item 10: polygon-backed grid context menu actions support `Copy ROI shape`, `Duplicate ROI shape`, and `Paste ROI shape here`.
- [x] Item 11: save/restart persistence wiring exists for imported SVG toolbar entries and polygon-backed grid perimeter/mask reload.
- [x] Item 12: imported SVG placement preserves explicit physical SVG document dimensions rather than using viewport-relative default sizing.
- [x] Item 13: `Delete SVG` removes the selected imported SVG shape from the ROI toolbar/config persistence path while leaving already-created polygon grids intact.

1. In the Viewport tab, confirm the new ROI row appears above the existing Viewport controls.
2. Click `Rectangle`, then click once in the viewport. Confirm:
   - a new grid appears,
   - the shape size is proportional to the visible field of view,
   - Grid Settings does not open automatically.
3. Open Grid Settings manually for the new polygon grid and confirm `Rows` and `Columns` are disabled but tile size, overlap, pixel size, dwell time, and rotation remain editable.
4. Change tile size or pixel size and save. Confirm the polygon perimeter stays in place while the active tile fill updates inside it.
5. Repeat with `Circle` and `Triangle`. Confirm the grid fill follows the polygon interior rather than the full rectangular carrier area.
6. Click `Draw your own`, left-click several vertices, then right-click to close. Confirm a new polygon-backed grid is created without a settings popup interrupting the viewport.
7. Click once inside a polygon-backed grid, including masked space where no active tile exists. Confirm the polygon becomes selected.
8. Drag a corner handle on a predefined polygon-backed grid. Confirm the polygon resizes and the filled tile pattern updates.
9. Drag an individual vertex handle on a custom or imported polygon-backed grid. Confirm the polygon and filled tile pattern update.
10. Right-click a polygon-backed grid and test `Copy ROI shape`, `Duplicate ROI shape`, and `Paste ROI shape here`.
11. Save the config, restart SBEMimage, and confirm:
   - imported SVG shapes are still present in the toolbar,
   - polygon-backed grids reload with the correct perimeter and tile activation mask.
12. Import an SVG with explicit physical dimensions, place it in the viewport, and confirm the resulting polygon size in SBEMimage matches the SVG document size rather than the current viewport zoom level.
13. Select an imported SVG shape in the ROI toolbar, click `Delete SVG`, save the config, restart SBEMimage, and confirm the deleted SVG no longer appears in the ROI toolbar while any already-created polygon grids remain intact.
14. Create or import a very large polygon ROI and confirm the guardrail dialog appears with a deferred option before full-grid creation.
15. Choose `Create Deferred ROI` for a very large polygon and confirm:
   - the viewport remains responsive,
   - the polygon outline appears without a full tile fill,
   - selection and deletion of that ROI still work.
16. Open Grid Settings for a deferred polygon ROI, change tile parameters, and confirm the save flow offers `Keep Deferred` versus `Materialize Grid`.
17. Save a deferred ROI, restart SBEMimage, and confirm it reloads as deferred instead of rebuilding the full giant grid at startup.

## To Be Continued Tomorrow

- [ ] Re-check the full large-ROI workflow end-to-end with a real wafer-scale polygon.
- [ ] Confirm that oversized legacy polygon configs auto-defer correctly on startup and do not freeze the GUI.
- [ ] Confirm that deferred large ROIs can still be selected, edited, and deleted without viewport errors.
- [ ] Confirm that `Keep Deferred` versus `Materialize Grid` in Grid Settings behaves predictably and does not unexpectedly expand the ROI.
- [ ] Confirm that acquisition estimates and Main Controls labels remain sensible for deferred polygon ROIs.
- [ ] Decide whether the current large-ROI thresholds (`5,000` warning / `20,000` hard limit) feel right in practice or need adjustment.
- [ ] If behavior is still unclear, document exact repro cases and logs before making further changes.

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
