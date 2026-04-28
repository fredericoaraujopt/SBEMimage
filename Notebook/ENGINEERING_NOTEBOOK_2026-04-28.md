# SBEMimage Engineering Notebook - 2026-04-28

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

## Repository Context Snapshot (2026-04-28)

- Objective: continue operator-facing workflow fixes in the local SBEMimage customization branch without destabilizing the merged upstream/dev baseline.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Active branch: `feature/guideline-compliance`.
- Current focus: autofocus/acquisition setup clarity and acquisition-manager group-creation UX.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `ENGINEERING_NOTEBOOK_2026-03-03.md` through `ENGINEERING_NOTEBOOK_2026-03-13.md`.

### Implemented change groups

- [x] Acquisition reliability and diagnostics
  - Added acquisition guardrails, overview diagnostics, and safer acquisition-loop handling.

- [x] Viewport acquisition control updates
  - Added asynchronous viewport grid acquisition and pause-flow consistency.

- [x] Spatial provenance and registration foundations
  - Added acquired/locked/timestamp state for grids and overviews and persisted it through config save/load.

- [x] Experimental KLAB UI path
  - Added KLAB startup toggle, theme path, geometry tuning, and readability improvements.

- [x] Polygon ROI workflow in Viewport
  - Added ROI tools, SVG import/delete, polygon-backed grids, and deferred large-ROI handling.

- [x] Stub overview workflow rework
  - Added modeless stub dialog behavior, overlap checks, archived stub persistence, and optimized archived-stub background rendering.

- [x] Imported-image / stub layering cleanup
  - True imported images render as the background layer.
  - Archived stubs are no longer shown by the `Show imported` toggle.

- [x] Acquisition manager workflow expansion
  - Added multi-selection, bulk actions, persistent filters/presets, status icons, and batch imaging-settings propagation.

## Current Task Checklist (Imported)

- [ ] Explain how SBEMimage autofocus works during acquisition and provide an operator-focused setup guide for automated focusing.
- [ ] Diagnose why `New group` in the Acquisition Manager appears to do nothing.
- [ ] Fix the `New group` UX so creation remains visible when `Only current group` is enabled.

## Session Change Log (2026-04-28)

- [x] Reviewed `Notebook/guidelines.md` and the March engineering notebooks before making changes.
- [x] Traced autofocus/acquisition behavior through `src/Autofocus.py`, `src/Acquisition.py`, `src/dialog/AutofocusSettingsDlg.py`, and `src/MainControls.py`.
- [x] Traced Acquisition Manager `New group` behavior through `src/dialog/viewport/AcquisitionManagerDlg.py` and identified two UX defects: new empty groups were hidden even with `All items`, and `Only current group` could also immediately hide a newly created top-level group.
- [x] Patched Acquisition Manager group creation so empty groups remain visible by default and a newly created top-level group remains visible when `Only current group` is enabled by focusing the filtered view on the new group.
- [x] Changed autofocus scheduling so `slice 0` is included in the normal autofocus/autostig cadence instead of being implicitly skipped.
- [x] Strengthened rectangular grid ROI persistence so user-drawn grid footprints stay anchored to the original drag-defined outline when imaging geometry changes.
- [x] Added a one-time first-created-grid workflow that automatically opens Grid Settings after the first user-created grid in a session.

## Verification Guide - Acquisition Manager New Group Visibility

### A. Create top-level group with no filter

- [ ] Open the Acquisition Manager.
- [ ] Ensure `Only current group` is unchecked.
- [ ] Click `New group`.
- [ ] Confirm a new top-level group appears immediately and becomes selected.

Expected result:
- [ ] The new group is visible immediately in the tree.
- [ ] Empty groups are shown in the tree even before any rows are assigned.

### B. Create top-level group with `Only current group` enabled

- [ ] Open the Acquisition Manager.
- [ ] Select any existing group, overview, or grid inside a group.
- [ ] Enable `Only current group`.
- [ ] Click `New group`.
- [ ] Confirm the tree switches to the newly created group instead of appearing unchanged.

Expected result:
- [ ] The new group is created and remains visible even with `Only current group` enabled.
- [ ] The button no longer looks like a no-op.

## Verification Guide - Autofocus On Slice 0

### A. Per-tile autofocus on first acquired surface

- [ ] Enable `Autofocus` in Main Controls.
- [ ] Open `Autofocus settings`.
- [ ] Select method `MAPFoSt` or `SEM autofocus`.
- [ ] Set autofocus interval to `1`.
- [ ] If desired, set autostig delay to `0`.
- [ ] Select tracking mode `Track all active tiles`.
- [ ] Ensure the target grid has active tiles.
- [ ] Start an acquisition while `slice_counter` is `0`.
- [ ] Watch the log and SEM behavior during the first grid acquisition.

Expected result:
- [ ] Autofocus is allowed to run on `slice 0`.
- [ ] If all active tiles are autofocus-reference tiles, autofocus runs before each tile on the first acquired surface.
- [ ] If autostig delay is `0`, autostig is also eligible on `slice 0`.

## Verification Guide - Rectangular Grid ROI Stability

### A. Keep the same ROI while changing imaging geometry

- [ ] Open SBEMimage and draw a new rectangular grid around a recognizable feature.
- [ ] Note the visible outer outline of the grid in the Viewport.
- [ ] Open Grid Settings for that grid.
- [ ] Change `pixel size`.
- [ ] Save settings.
- [ ] Confirm the grid repopulates but the outer outline stays over the same feature.
- [ ] Re-open Grid Settings and change `tile size`.
- [ ] Save settings.
- [ ] Confirm the outer outline still stays fixed.
- [ ] Repeat with a change to `overlap` and `row shift`.

Expected result:
- [ ] Imaging geometry changes alter how the ROI is sampled, not where the ROI is placed.
- [ ] The visible rectangular outline does not drift away from the feature that was originally enclosed.

### B. First created grid opens Grid Settings automatically

- [ ] Launch SBEMimage fresh.
- [ ] Draw the first new grid of the session in the Viewport.
- [ ] Confirm Grid Settings opens automatically for that new grid.
- [ ] Close the dialog and draw a second new grid.
- [ ] Confirm Grid Settings does not auto-open again for the second grid.

Expected result:
- [ ] The first created grid in the session immediately opens Grid Settings.
- [ ] Subsequent created grids follow the normal, non-intrusive workflow.

## Instruction Reminder

Any new notebook created after this one must include:
- the persistent guideline block,
- a carry-forward major changes section,
- and an imported checklist of current tasks.
