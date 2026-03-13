# SBEMimage Engineering Notebook - 2026-03-13

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

## Repository Context Snapshot (2026-03-13)

- Objective: continue operator-facing UX fixes in the local SBEMimage customization branch without destabilizing the merged upstream/dev baseline.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Active branch: `feature/guideline-compliance`.
- Current focus: viewport selection usability, default grid activation on manual creation, and overview/grid UX consistency.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `ENGINEERING_NOTEBOOK_2026-03-03.md`, `ENGINEERING_NOTEBOOK_2026-03-04.md`, `ENGINEERING_NOTEBOOK_2026-03-05.md`, `ENGINEERING_NOTEBOOK_2026-03-06.md`, `ENGINEERING_NOTEBOOK_2026-03-09.md`, `ENGINEERING_NOTEBOOK_2026-03-10.md`, and `ENGINEERING_NOTEBOOK_2026-03-12.md`.

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
  - True imported images now render as the background layer.
  - Archived stubs are no longer shown by the `Show imported` toggle.
  - Imported-image dialog no longer exposes manual move-up/move-down layering controls.

- [x] Upstream/dev integration checkpoint
  - The local customization branch has already been merged forward onto the reviewed `upstream/dev` line and validated with targeted automated checks.

## Latest Known Validation State (Carry-Forward)

- [x] KLAB and native UI modes are selectable at startup.
- [x] Polygon ROI and deferred large-ROI workflows are implemented.
- [x] Stub archive rendering is optimized relative to the old imported-image path.
- [x] Imported images now render behind stubs, overviews, and grids.
- [ ] Viewport selection UX for inactive grids/overviews still needs improvement.
- [ ] Overview right-click UX still lags behind grid right-click UX.

## Current Task Checklist (Imported)

- [ ] Make inactive grids and overviews easier to select in the Viewport by increasing the practical click target around labels and borders.
- [ ] Ensure `Alt`-drag grid creation yields active grids by default regardless of template-grid active state.
- [ ] Make overview right-click UX more consistent with grids by adding copy / paste / duplicate / delete actions.
- [ ] Validate the new overview clipboard behavior against existing delete-order protections.

## Session Change Log (2026-03-13)

Use this section to record work completed today.

- [x] Created `ENGINEERING_NOTEBOOK_2026-03-13.md` using the established notebook structure and persistent guideline block.
- [x] Reviewed the recent notebooks and current merged branch state before starting today's viewport UX fixes.
- [x] Confirmed that `GridManager.add_new_grid()` already supports active-by-default initialization, but `draw_grid()` was still inheriting the template grid's active flag and could create inactive grids through `Alt`-drag.
- [x] Traced inactive grid and overview selection to tight label-only / border-only hit zones in `src/Viewport.py`.
- [x] Added larger practical selection targets around inactive grid and overview labels and borders in the Viewport hit-testing path.
- [x] Changed manual `Alt`-drag grid creation to force newly drawn grids active by default.
- [x] Added overview clipboard actions (`Copy`, `Duplicate`, `Delete`, `Paste copied OV here`) to the viewport right-click menu, while preserving the existing OV deletion-order protections.
- [x] Traced persistent KLAB dialog text clipping to fixed-size settings dialogs that call `setFixedSize(self.size())` before any KLAB-specific width adjustment can occur.
- [x] Extended the existing KLAB-only dialog-width hook to the remaining Main Controls settings dialogs (`Acq`, `Debris`, `Autofocus`, `Microtome`, `Stage Calibration`) so their width can expand before they are locked.
- [x] Reviewed the acquisition manager implementation in `src/dialog/viewport/AcquisitionManagerDlg.py` and confirmed it was still restricted to single-row selection with no row-level context menu.
- [x] Switched the acquisition manager tree to extended selection so Shift-click and Ctrl-click behave like Windows multi-row selection.
- [x] Added acquisition-manager right-click actions for groups, overviews, and grids, including `Open settings`, `Copy`, `Duplicate`, `Delete`, and imaging-settings batch actions where applicable.
- [x] Added a separate acquisition-manager imaging-settings clipboard so copied grid or overview imaging settings can be applied to multiple selected rows or to a selected group subtree.
- [x] Reverted the KLAB-only settings-dialog width expansion after operator feedback; the fixed-dialog width hook was removed from the settings dialogs and the temporary helper code was cleaned back out.
- [x] Added acquisition-manager bulk row actions for selected rows and grouped selections: enable, disable, lock, and unlock.
- [x] Added an acquisition-manager filter bar with persistent workflow presets (`All items`, `Active review`, `Locked review`, `Failure triage`, `Current group focus`) and persistent filter toggles for active / locked / failed / current-group views.
- [x] Added explicit acquisition-manager row-status icons for active, locked, acquired, failed, and deferred states.
- [x] Added a dedicated batch imaging-settings dialog for acquisition-manager selected rows and group/subgroup trees with per-field apply checkboxes so only changed fields are propagated.
- [x] Wired group and multi-row acquisition-manager context menus to the new batch settings flow instead of the old imaging-settings clipboard path.
- [x] Fixed an acquisition-manager recursion bug triggered by `Only current group`; the tree refresh path now keeps its refresh guard active through selection restoration and no longer re-syncs group inventory repeatedly while filtering rows.

## Verification Guide - Viewport Selection and Overview UX

### A. Inactive grid and overview selection

- [ ] Launch SBEMimage and open the Viewport.
- [ ] Create at least one grid and set it inactive.
- [ ] Create or select at least one overview and set it inactive.
- [ ] Try selecting the inactive grid by clicking near its outline.
- [ ] Try selecting the inactive grid by clicking near its label.
- [ ] Try selecting the inactive overview by clicking near its outline.
- [ ] Try selecting the inactive overview by clicking near its label.

Expected result:
- [ ] Inactive grids are easier to select without requiring a pixel-perfect click on the label.
- [ ] Inactive overviews are easier to select without requiring a pixel-perfect click on the label.

### B. Alt-drag grid creation defaults to active

- [ ] In the Viewport, use `Alt` + drag to create a new rectangular grid.
- [ ] Select the new grid.
- [ ] Confirm the grid is active immediately after creation.
- [ ] Confirm the grid has active tiles immediately after creation.
- [ ] If safe, right-click and confirm acquisition-related actions behave as expected for an active grid.

Expected result:
- [ ] Newly drawn grids are active by default even if the template/current grid was inactive.

### C. Overview right-click parity

- [ ] Right-click on an overview in the Viewport.
- [ ] Confirm the menu now exposes overview clipboard actions.
- [ ] Use `Copy OV` and then `Paste copied OV here` elsewhere in the Viewport.
- [ ] Confirm a new overview is created at the requested location with copied acquisition settings.
- [ ] Use `Duplicate OV` and confirm an offset duplicate is created.
- [ ] Try deleting `OV 0` and confirm the existing protection remains in place.
- [ ] Try deleting a non-last overview and confirm the existing deletion-order protection remains in place.
- [ ] Delete the highest OV index and confirm deletion succeeds.

Expected result:
- [ ] Overviews now support the same core clipboard-style right-click workflow as grids.
- [ ] Existing overview deletion protections are preserved.

### D. KLAB settings dialog width

- [ ] Obsolete after same-day revert. Do not validate this section unless the KLAB dialog-width experiment is reintroduced.
- [ ] Launch SBEMimage with `klab gui` enabled.
- [ ] Open the `SEM` settings dialog from Main Controls and inspect long labels / grouped text.
- [ ] Open the `Grid Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `OV Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `Acquisition Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `Autofocus Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `Debris Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `Microtome Settings` dialog and inspect long labels / grouped text.
- [ ] Open the `Stage Calibration` dialog and inspect long labels / grouped text.
- [ ] Restart SBEMimage without `klab gui` enabled and spot-check the same dialogs.

Expected result:
- [ ] In KLAB mode, these fixed-size settings dialogs are visibly wider and long labels no longer crop.
- [ ] Native UI dialog dimensions remain unchanged.

### E. Acquisition manager multi-selection and batch actions

- [ ] Open the Acquisition Manager from Main Controls.
- [ ] Shift-click adjacent rows in the tree and confirm a contiguous multi-selection is created.
- [ ] Ctrl-click non-adjacent rows and confirm disjoint multi-selection is created.
- [ ] Drag a multi-selection of grids or overviews onto a group and confirm all selected rows move together.
- [ ] Right-click a selected grid row and confirm the context menu exposes `Open settings`, `Copy grid`, `Duplicate grid`, `Delete grid`, and imaging-settings actions.
- [ ] Right-click a selected overview row and confirm the context menu exposes `Open settings`, `Copy OV`, `Duplicate OV`, `Delete OV`, and imaging-settings actions.
- [ ] Copy imaging settings from one grid row, then apply them to multiple selected grid rows.
- [ ] Copy imaging settings from one overview row, then apply them to multiple selected overview rows.
- [ ] Copy grid imaging settings, right-click a group or subgroup, and apply the copied settings to that group subtree.
- [ ] Copy overview imaging settings, right-click a group or subgroup, and apply the copied settings to that group subtree.

Expected result:
- [ ] Shift-click and Ctrl-click behave like standard Windows multi-selection.
- [ ] Multi-row drag-to-group assignment works with the same grouped acquisition model.
- [ ] Batch imaging-settings application works for selected rows and for group subtrees without changing acquisition order.

### F. Acquisition manager filters, presets, status icons, and bulk actions

- [ ] Open the Acquisition Manager and confirm the new filter bar is visible.
- [ ] Switch between workflow presets (`All items`, `Active review`, `Locked review`, `Failure triage`, `Current group focus`) and confirm the tree updates accordingly.
- [ ] Close and reopen SBEMimage, reopen the Acquisition Manager, and confirm the last-used workflow preset and filter toggles persist.
- [ ] Select multiple overview and/or grid rows, right-click, and confirm `Enable selected rows` / `Disable selected rows` work across the selected set.
- [ ] Select multiple overview and/or grid rows, right-click, and confirm `Lock selected rows` / `Unlock selected rows` work across the selected set.
- [ ] Select one or more grids with different status conditions and confirm the status column shows explicit status icons for active, locked, acquired, failed, and deferred where applicable.
- [ ] Select one or more overviews with different status conditions and confirm the status column reflects their state appropriately.
- [ ] Select multiple grids of the same type and open `Batch grid settings for selected rows...`.
- [ ] In the batch settings dialog, change only one or two checked fields and confirm unchecked fields stay unchanged after applying.
- [ ] Right-click a group or subgroup containing grids and apply `Batch grid settings for this group...`.
- [ ] Right-click a group or subgroup containing overviews and apply `Batch overview settings for this group...`.

Expected result:
- [ ] Bulk active/lock actions operate on the selected rows without changing acquisition order.
- [ ] Workflow presets and filters make it easy to focus on active, locked, failed, or current-group subsets.
- [ ] Status icons provide explicit at-a-glance state for each acquisition row.
- [ ] Batch settings propagation applies only the checked fields and works for both selected rows and group/subgroup trees.

### G. Acquisition manager current-group filter stability

- [ ] Open the Acquisition Manager with at least one group containing overviews or grids.
- [ ] Enable `Only current group`.
- [ ] Click between different rows inside and outside the active group.
- [ ] Toggle other filters on and off while `Only current group` remains enabled.
- [ ] Confirm the tree refreshes without repeated exception dialogs.
- [ ] Confirm the selection and inspector update normally after each click.

Expected result:
- [ ] `Only current group` no longer triggers recursion or repeated exception dialogs.
- [ ] The filtered tree remains responsive while switching selection.

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
