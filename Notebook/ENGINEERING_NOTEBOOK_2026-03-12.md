# SBEMimage Engineering Notebook - 2026-03-12

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

## Repository Context Snapshot (2026-03-12)

- Objective: rework SBEMimage for reliability, operator safety, and large-ROI usability on GEMINISEM acquisitions without disrupting core acquisition behavior.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Current focus: checkpoint the active customization branch and prepare a safe merge path from `upstream/dev` into the local customization line.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `ENGINEERING_NOTEBOOK_2026-03-03.md`, `ENGINEERING_NOTEBOOK_2026-03-04.md`, `ENGINEERING_NOTEBOOK_2026-03-05.md`, `ENGINEERING_NOTEBOOK_2026-03-06.md`, `ENGINEERING_NOTEBOOK_2026-03-09.md`, and `ENGINEERING_NOTEBOOK_2026-03-10.md`.

### Implemented change groups

- [x] Acquisition reliability and diagnostics
  - Added acquisition guardrails, overview diagnostics, and stage-arrival sanity checks.
  - Added safer acquisition-loop handling and single-surface rerun safeguards.

- [x] Viewport acquisition control updates
  - `Acquire Grid` from the viewport runs asynchronously.
  - Added viewport pause flow consistency and safer interaction gating while acquisition is active.

- [x] Spatial provenance and registration foundations
  - Added acquired/locked/timestamp state for grids and overviews.
  - Persisted provenance state through config load/save paths and registration export.

- [x] New Project workflow in Main Controls
  - Added guided config/base-directory setup and reset/preview logic.

- [x] Experimental KLAB UI path
  - Added KLAB stylesheet path, startup toggle flow, startup animation, and KLAB-only layout tuning.
  - Fixed KLAB startup defaults and moved away from aggressive adaptive font shrinking.

- [x] Polygon ROI workflow in Viewport
  - Added ROI tools row with predefined shapes, custom polygon drawing, SVG import, and SVG deletion.
  - Implemented polygon-backed grids with deferred materialization and config persistence.

- [x] Large-ROI protection flow
  - Added tile-count guardrails and deferred polygon ROI mode.
  - Added persistence and load-time auto-defer for oversized legacy polygon grids.

- [x] Stub overview workflow rework
  - Added stage-centering assist, modeless dialog behavior, overlap checks, archive persistence, and viewport rendering for archived stubs.
  - Added `src/stub_overview_workflow.py` to keep the stub rework modular.

- [x] Shared imaging-condition presets
  - Added shared imaging-condition storage in `cfg/imaging_conditions/`.
  - Added preset save/apply/manage flows across grid, overview, and stub dialogs.

- [x] Acquisition manager
  - Added grouped overview/grid presentation state and a modeless acquisition-manager dialog.
  - Added group-color propagation, tile activation inspection, and focused automated coverage.

## Latest Known Validation State (Carry-Forward)

- [x] KLAB and native UI modes are selectable at startup via configuration dialog.
- [x] Polygon ROI baseline workflow and deferred large-ROI flow are implemented and documented.
- [x] Shared imaging-condition and acquisition-manager code paths have targeted automated coverage recorded in the previous notebook.
- [ ] The current local tree still contains additional unmerged and only partially runtime-validated changes that need to be preserved before any upstream integration.

## Git History Snapshot (2026-03-12)

- Active branch during this review: `feature/guideline-compliance`
- Current committed `HEAD` before today's checkpoint: `8b1c5ea` (`changes up until 2026-03-09 including`)
- Upstream branch targeted for review: `upstream/dev` at `3754ef9` (`Correction for coordinate transforms in combination of external tool and new metadata`)
- Common ancestor between local branch and `upstream/dev`: `2601d52` (`Add acquisition date to metadata`, 2025-11-14)
- Symmetric difference between local `HEAD` and `upstream/dev`: `4` commits on the local side, `35` commits on the upstream `dev` side

### Local line after the shared ancestor

- `f729367` `Update version`
- `83d431e` `WIP: local SBEMimage customizations and sync workflow doc`
- `84b4b04` `KLAB UI updates: startup animation, default unchecked, and layout refinements`
- `8b1c5ea` `changes up until 2026-03-09 including`

### Upstream `dev` line after the shared ancestor

- Major themes visible in the upstream commit stream:
  - Automated Focus Stigmation Series (AFSS) integration and follow-up fixes
  - Metadata / OME-TIFF handling changes
  - Coordinate-transform and image-position fixes
  - Zeiss-device fixes and SEM support adjustments
  - Config/default-schema changes and small UI/supporting-module updates

## Current Local Working Tree Snapshot (2026-03-12)

- Branch tracking state before today's checkpoint: `feature/guideline-compliance` is ahead of `origin/feature/guideline-compliance` by 1 commit and has a dirty worktree.
- Uncommitted diff against `HEAD`: `18` modified tracked files, `9` untracked source/test files, and one untracked imaging-condition preset JSON under `cfg/imaging_conditions/`.
- High-signal uncommitted themes visible from the current tree:
  - Shared imaging-condition preset infrastructure and dialog wiring
  - Acquisition-manager dialog and grouping logic
  - Stub overview workflow rework and archive handling
  - Additional KLAB UI tuning and documentation updates

### Current merge-risk hotspot files shared by local work and `upstream/dev`

- `src/Acquisition.py`
- `src/Grid.py`
- `src/GridManager.py`
- `src/MainControls.py`
- `src/Viewport.py`
- `src/acq_func.py`
- `src/config_template.py`
- `src/constants.py`
- `src/default_cfg/default.ini`
- `src/sem/SEM_SmartSEM.py`
- `src/utils.py`

These files should be treated as the primary conflict-review surface when integrating `upstream/dev`.

## Sequential Upstream Dev Integration Plan

1. Create and keep an immutable safety point first.
   - Use today's checkpoint commit as the rollback anchor for the exact local state before upstream integration.
   - Optionally create `backup/feature-guideline-compliance-2026-03-12` from that checkpoint before any merge attempt.

2. Keep active feature work isolated from merge experimentation.
   - Do not merge `upstream/dev` directly into the working feature branch first.
   - Create a dedicated integration branch from the checkpoint commit, for example `integrate/upstream-dev-2026-03-12`.

3. Review the upstream `dev` history in manageable batches before merging.
   - Batch A: AFSS/autofocus series commits.
   - Batch B: metadata / OME-TIFF / coordinate-transform commits.
   - Batch C: schema/default/config/device-support commits.
   - For each batch, inspect touched files and note whether the change is additive, conflicting, or obsolete relative to the local customizations.

4. Pre-classify conflicts file by file before running the merge.
   - Compare `2601d52..HEAD` and `2601d52..upstream/dev` for the hotspot files above.
   - Decide in advance where upstream logic must be adopted wholesale, where local behavior must dominate, and where a manual composition is required.

5. Perform the actual merge only on the integration branch.
   - Merge `upstream/dev` into the integration branch.
   - Resolve conflicts beginning with config/schema files, then shared logic modules, then UI/controller files, and finally docs/tests.
   - Preserve local operator-facing features unless an upstream change clearly supersedes them and is validated as compatible.

6. Validate in the same sequence the code is most likely to fail.
   - Run syntax / import checks first.
   - Run targeted tests around acquisition, grid/overview managers, imaging conditions, and the acquisition manager.
   - Launch the UI and execute focused manual smoke tests for startup, viewport, grid settings, overview settings, stub overview, and acquisition-manager flows.

7. Only after the integration branch is stable, merge it back into the customization branch.
   - Keep the upstream-integration commit distinct from later feature work.
   - If the integration branch is unstable, discard only that branch and return to the checkpoint.

## Current Task Checklist (Imported)

- [x] Review notebook history and developer guidelines before planning upstream integration.
- [x] Identify the shared ancestor between the local customization branch and `upstream/dev`.
- [x] Enumerate the local custom commits and the upstream `dev` commits since the fork point.
- [x] Identify hotspot files touched by both histories.
- [x] Record a written integration plan before attempting any merge.
- [x] Create a checkpoint notebook entry for today's repository state.
- [x] Create a checkpoint commit that accompanies this notebook entry and preserves the pre-merge local tree.
- [x] Create a dedicated integration branch from the checkpoint commit before merging `upstream/dev`.
- [x] Review upstream `dev` commits in topical batches and annotate expected conflict points.
- [x] Merge `upstream/dev` on the integration branch only after the pre-merge review is complete.
- [x] Run targeted automated validation before accepting the integration branch.
- [ ] Run focused manual smoke validation before accepting the integration branch.

## Session Change Log (2026-03-12)

Use this section to record work completed today.

- [x] Reviewed `Notebook/guidelines.md`, `Notebook/GIT_SYNC_WORKFLOW.md`, and the recent engineering notebooks to re-establish repository context and notebook conventions.
- [x] Reconfirmed from the notebooks that this repository is a local customization line of SBEMimage, focused on SEM/SBEM acquisition workflows, PyQt UI behavior, polygon/deferred ROI handling, KLAB UI tuning, stub overview workflows, and new acquisition-management features.
- [x] Fetched `origin` and `upstream` so the branch analysis reflects the current remote state on 2026-03-12.
- [x] Confirmed the current integration target is `upstream/dev`, not `upstream/master`.
- [x] Identified `2601d52` as the common ancestor between the local branch and `upstream/dev`.
- [x] Confirmed that the local branch contains four commits after that ancestor while `upstream/dev` contains thirty-five commits after that ancestor.
- [x] Confirmed that the local customization work proper starts after `f729367` and currently consists of the committed local chain plus additional uncommitted work in the tree.
- [x] Identified the highest-risk overlapping files shared by the local line and `upstream/dev`.
- [x] Recorded a sequential merge-preparation plan that keeps the current feature branch protected and uses a dedicated integration branch for the actual merge attempt.
- [x] Created local backup branch `backup/feature-guideline-compliance-2026-03-12` from checkpoint `416242b`.
- [x] Created integration branch `integrate/upstream-dev-2026-03-12` from checkpoint `416242b`.
- [x] Merged `upstream/dev` into the integration branch and reduced the direct conflict set to four files: `src/Acquisition.py`, `src/Viewport.py`, `src/config_template.py`, and `src/constants.py`.
- [x] Resolved the merge by keeping the local async viewport grid-acquisition flow and guardrail/provenance logic while incorporating upstream AFSS support and the path-based config-template handling.
- [x] Recomputed `CFG_NUMBER_KEYS` against the merged `src/default_cfg/default.ini` and updated it to `295` so config validation matches the post-merge template.
- [x] Verification pass completed: `python -m compileall src tests`.
- [x] Verification pass completed: `$env:PYTHONPATH='src;tests'; pytest tests/test_load_config.py tests/test_grid_manager.py tests/test_overview_manager.py tests/test_utils.py tests/test_sem.py tests/test_acquisition_group_manager.py tests/test_imaging_conditions.py -q` with `23 passed`.
- [x] Attempted `pytest tests/test_gui.py -q` as an additional UI smoke gate; it is currently blocked in this environment because the `qtbot` fixture is unavailable, indicating `pytest-qt` is not installed here.
- [x] Fast-forwarded `feature/guideline-compliance` to the validated integration commit `2251c2e` while keeping `integrate/upstream-dev-2026-03-12` and `backup/feature-guideline-compliance-2026-03-12` as preserved branch references.
- [x] Reviewed operator feedback against the first KLAB readability pass and confirmed the remaining problems were layout-distribution issues, not adaptive font shrinking regressions.
- [x] Lowered the fixed KLAB application baseline from `11 pt` to `10 pt` and increased the KLAB Main Controls width floor from `128 px` to `220 px`.
- [x] Rebalanced KLAB Main Controls geometry so `Overviews`, `Tile grids`, and the `Stack acquisition` metrics lane receive more width while `Manual commands` stays compact.
- [x] Reworked the KLAB `Stack acquisition` header so the new `Acquisition manager` button now sits below the base-directory field in Main Controls instead of below the Viewport grid selector.
- [x] Completed the acquisition-manager relocation for both UI modes so the workflow entry point now lives in `Stack acquisition` in both native and KLAB UI instead of in the Viewport controls.
- [x] Reworked the KLAB Viewport display-controls block to use a dedicated left toggle column plus a wider zoom/FOV lane, and added extra KLAB-only vertical space so the controls are no longer stacked on top of one another.
- [x] Updated KLAB top-panel and stack-metrics labels to use wrapping/full-row geometry where needed instead of clipping through neighboring controls.
- [x] Moved `Save current settings as...` below `Image bit depth` in both the overview and tile-grid settings dialogs so the imaging-condition actions follow the imaging-parameter block more intuitively.
- [x] Replaced the ad hoc imaging-preset button placement in the overview and tile-grid settings dialogs with a dedicated `Saved imaging settings` panel.
- [x] Switched the KLAB font family to a narrower modern Windows face (`Bahnschrift`) and reduced the KLAB Main Controls width budget so Main Controls plus Viewport fit more comfortably within a standard Full HD screen.
- [x] Removed the selected-tab font-weight bump in KLAB so switching between `Main controls`, `Focus tool`, `Notes`, and other tabs no longer makes tab text grow enough to clip.
- [x] Moved the `Acquisition manager` control to its own dedicated row in `Stack acquisition` and added extra vertical space so it no longer shares the target/slice row.
- [x] Fixed the Viewport ROI toolbar buttons to explicit widths so they no longer resize dynamically while the mouse moves over the Viewport.
- [x] Prevented the KLAB theme polisher from reprocessing the fixed-metric ROI toolbar controls so the ROI row now follows the same stable sizing behavior as the native UI instead of shifting during hover/mouse movement.
- [x] Switched the KLAB font family from `Bahnschrift` to `Segoe UI Variable Text` while keeping the fixed KLAB baseline at `10 pt`.
- [x] Reworked the Viewport display-controls block in both native and KLAB UI to use a consistent four-row toggle stack with added vertical space, so `Show grid lines`, `Show labels`, `Show stage position`, and `Show axes` no longer crowd one another.
- [x] Changed the shared `H` shortcut so it now hides or restores both grid lines and grid labels together, while keeping the individual checkboxes available for manual control.
- [x] Rebalanced the KLAB `Stack acquisition` metrics lane by nudging the divider left, widening the right-side text section, and giving the long duration/date rows taller geometries so wrapped text is no longer vertically cropped.
- [x] Reworked the KLAB Main Controls geometry helpers to use font metrics and wrapped-text measurement rather than the original fixed `.ui` label heights.
- [x] Made the KLAB `SEM`, `Stage`, `Overviews`, `Tile grids`, and `Stack acquisition` panels recalculate row heights after text updates so the current sans-serif font can use the available panel space cleanly.
- [x] Added a guarded KLAB reflow path that reruns after `show_current_settings()` and `show_stack_acq_estimates()`, plus a KLAB-only stack-panel height extension when wrapped content genuinely needs more vertical room.
- [x] Changed the KLAB stage-position display so the `X` and `Y` coordinates use a dedicated multiline value block instead of competing for one narrow single-line label.
- [x] Added a KLAB-only measured height extension for the `Stage` card so the final `Z` row is no longer forced below the old native panel height.
- [x] Reclaimed width in the KLAB stack-acquisition option rows by slimming the `...` toolbutton column and tightening the inter-column gaps, so labels like `E-mail monitoring` and `"Ask user" mode` keep more usable text width.
- [x] Removed the Viewport panning-specific overlay overrides that had been suppressing labels and forcing hidden grid lines back on during interaction, so the grid/label visibility state now stays consistent while panning.
- [x] Split the Viewport mouse-position status readout into two lines (`Stage` and `SEM`) and resized that label row accordingly so the coordinate text no longer gets truncated into one overpacked single line.
- [x] Replaced the rejected two-line mouse-position readout with a width-aware single-line formatter that compacts `Stage` / `SEM` labels when necessary and exposes the full verbose form on hover.
- [x] Verification pass completed: `python -m py_compile src\MainControls.py src\Viewport.py src\sbemimage.py src\dialog\GridSettingsDlg.py src\dialog\OVSettingsDlg.py`.
- [x] Verification pass completed: `python -m py_compile src\Viewport.py src\MainControls.py src\klab_ui.py src\sbemimage.py`.
- [x] Imported/stub layer cleanup: legacy archived stub images are now backfilled to stub-archive classification on load, so `Show imported` no longer brings old stub archives into the generic imported-image path.
- [x] Viewport layer-order fix: true imported images now render as the background layer, behind archived stubs, active stubs, overviews, and grids.
- [x] Imported-images dialog simplification: removed the `Move up` / `Move down` controls because imported-image ordering is no longer the operator-facing layer-control mechanism.
- [x] Imported-images dialog layout fix: corrected the fixed-button geometry in `gui/modify_images_dlg.ui` so `Import`, `Delete`, `Modify`, and `Close` no longer overlap.
- [x] Verification pass completed: `python -m py_compile src\ImportedImage.py src\Viewport.py src\dialog\viewport\ModifyImagesDlg.py`.

## Verification Guide - Upstream Dev Integration Preparation

Use this checklist before starting the actual `upstream/dev` merge.

1. [x] Confirm the checkpoint commit exists on `feature/guideline-compliance`.
2. [x] Create a backup branch or tag from the checkpoint commit.
3. [x] Create `integrate/upstream-dev-2026-03-12` from the checkpoint commit.
4. [x] Review `git log --reverse --oneline 2601d52..upstream/dev` and group commits into AFSS, metadata/OME, and schema/device batches.
5. [x] Review the hotspot files listed above and note expected local-vs-upstream conflict intent for each file.
6. [x] Merge `upstream/dev` into the integration branch.
7. [x] Resolve config and constants conflicts before UI files so the runtime schema is consistent early.
8. [x] Run targeted tests and compile/import checks.
9. [ ] Launch SBEMimage and complete focused manual smoke tests on the changed workflows.
10. [x] Merge the validated integration branch back into `feature/guideline-compliance` only if the result is stable.

Expected result:

- [x] The repository has a reversible checkpoint before any upstream merge work.
- [x] The eventual `upstream/dev` merge happens on an isolated branch.
- [x] Conflict resolution decisions are made deliberately per hotspot file instead of ad hoc during the merge.
- [x] Upstream improvements are integrated without losing the local customization work.

## Verification Guide - Post-Merge Smoke Test

Use this checklist to manually validate the merged `feature/guideline-compliance` branch after the `upstream/dev` integration.

### A. Startup and baseline regression

- [x] Launch SBEMimage with the normal working configuration.
- [x] Confirm the selected config loads without startup errors.
- [x] Confirm Main Controls opens normally.
- [x] Confirm the Viewport opens normally.
- [x] Confirm the usual custom UI/workflow elements are still present, including polygon ROI tools, stub-overview workflow entry points, imaging-condition actions, and the acquisition-manager entry point.

Expected result:

- [x] The merged build starts normally and the previously customized operator workflows are still accessible.

### B. Autofocus settings dialog and AFSS controls

- [x] Open the autofocus settings dialog from Main Controls.
- [x] Confirm the dialog opens cleanly and reflects the current saved autofocus mode.
- [x] Toggle through `SEM autofocus/autostigmator`, `heuristic autofocus`, `tracking only`, `MAPFoSt`, and the new `AFSS` mode.
- [x] Confirm the relevant parameter groups enable and disable correctly as the selected autofocus mode changes.
- [x] With `AFSS` selected, verify the following controls are visible and editable:
- [x] `interval`
- [x] `offset`
- [x] WD/Stig perturbation sizes
- [x] `rounds`
- [x] `consensus mode`
- [x] `drift corrected`
- [x] `autostig active`
- [x] `max fails`
- [x] `RMSE limit`
- [x] `background mode`
- [x] current/upcoming AFSS mode selectors
- [x] Save the settings, reopen the dialog, and confirm the values persisted.
- [x] If Array mode is active in the current config, confirm AFSS remains appropriately disabled there.

Expected result:

- [x] The autofocus settings dialog supports the new AFSS workflow without breaking the existing autofocus modes.
- [x] AFSS settings persist correctly and the dialog state remains coherent when reopened.

### C. Grid creation and viewport labeling regression

- [x] Create a small standard grid and confirm normal creation, selection, and settings behavior.
- [x] Create a `1 x 1` grid and confirm it behaves correctly.
- [x] In the Viewport, select a grid with autofocus reference tiles.
- [ ] Confirm autofocus reference markers/labels still appear correctly.
- [ ] If AFSS is enabled, confirm the reference-tile labeling remains visible and sensible in the Viewport.

Expected result:

- [x] Upstream single-tile grid handling works and the merged Viewport still presents autofocus reference tiles correctly.

### D. Manual viewport acquisition regression

- [x] Start a manual grid acquisition from the Viewport with autofocus disabled.
- [x] Confirm the asynchronous viewport grid-acquisition path starts normally.
- [x] Confirm logs are created normally.
- [x] Confirm the UI returns to idle cleanly after the run.
- [x] Confirm the Viewport remains responsive and no stale busy/paused state remains afterward.

Expected result:

- [x] The local async viewport-acquisition workflow still works after the merge.

### E. Stack acquisition baseline before AFSS

- [x] Run a short stack acquisition using a previously known-good autofocus mode other than AFSS.
- [x] Confirm acquisition starts, progresses, and finishes or pauses normally.
- [x] Confirm no unexpected autofocus, metadata, or acquisition-state regressions appear in the log.

Expected result:

- [x] The merged branch preserves the pre-existing stack-acquisition baseline before AFSS-specific testing begins.

### F. AFSS acquisition workflow

- [x] Configure AFSS on exactly one grid that contains the autofocus reference tiles.
- [x] Use a short test acquisition with a small slice count and short AFSS interval.
- [x] Start stack acquisition with AFSS enabled.
- [x] Confirm the log announces the planned AFSS activation.
- [x] Confirm acquisition proceeds without freezing or immediate AFSS failure.
- [x] Confirm AFSS completes at least one cycle without leaving the system in an inconsistent state.
- [x] Pause a run while AFSS is active, if practical.
- [x] Confirm WD/Stig values are restored/reset cleanly on pause.
- [x] Restart or resume as appropriate and confirm AFSS state does not remain corrupted.

Expected result:

- [x] AFSS can run in the merged build, logs its activation cleanly, and resets correctly on pause/stop.

### G. Metadata and image-output validation

- [x] Acquire at least one overview image.
- [x] Acquire at least one tile image.
- [x] Inspect the saved output metadata for those files.
- [x] Confirm acquisition date metadata is present.
- [x] Confirm OME-TIFF position metadata looks sensible.
- [x] Confirm Z-position metadata looks sensible where applicable.
- [x] If the workflow depends on external registration/export, confirm the recorded image positions are consistent with the actual acquisition geometry.

Expected result:

- [x] The upstream metadata and coordinate-transform fixes behave correctly in real output files.

### H. Imported-image and external-tool regression

- [x] Import an image through the normal imported-image workflow.
- [x] Confirm the import succeeds and the image appears correctly in the workspace.
- [x] If external-tool or TCP workflows are used in this installation, perform one registration or round-trip integration check.
- [x] Confirm no new coordinate or metadata mismatch is visible in that workflow.

Expected result:

- [x] Imported-image handling still works and external-tool registration behavior benefits from the upstream coordinate/metadata fixes rather than regressing.

### I. Custom workflow regression pass

- [x] Create and edit a polygon ROI.
- [x] Reload a deferred ROI from config and confirm it behaves correctly.
- [x] Run the stub overview workflow and confirm it still works.
- [x] Open, apply, and save shared imaging-condition presets.
- [x] Open the acquisition manager and confirm it still reflects the expected grouping state and controls.
- [x] Reconfirm any local KLAB UI expectations that matter for the active operator workflow.

Expected result:

- [x] The local custom workflows most exposed to merge risk still work on top of the integrated upstream `dev` changes.

### J. Optional automated GUI gate

- [x] If `pytest-qt` is available in the validation environment, run `pytest tests/test_gui.py -q`.
- [x] If it is not available, record that the GUI pytest smoke test remains environment-blocked rather than implementation-blocked.

Expected result:

- [x] The notebook clearly distinguishes between an environment limitation and an actual GUI regression.

### E. KLAB readability without adaptive font shrinking

1. Launch SBEMimage with `Use KLAB UI (experimental)` enabled.
2. Confirm KLAB text now starts from a fixed `10 pt` baseline instead of the previous oversized `11/12 pt` appearance and no longer drops to the old tiny compact-font appearance in dense panels.
3. In Main Controls, inspect the top panels (`SEM`, `Overviews`, `Tile grids`, `Manual commands`) and the Stack acquisition panel.
4. Switch repeatedly between the top tabs (`Main controls`, `Focus tool`, `Notes`, `Array`, `MultiSEM`, `Tests`) and confirm the selected-tab text does not become slightly larger/bolder than the inactive tabs.
5. In the top summary panels, confirm device names, beam settings, overview/grid values, origin/location text, and the `Manual commands` panel title/buttons are visible without clipping into neighboring controls.
6. In `Stack acquisition`, confirm the `Target number...` / `Slice thickness` area no longer collides, the `Acquisition manager` button now has its own dedicated row below that block in both native and KLAB UI, and the right-side metrics (`Electron dose`, `Tile acquisition area`, `Z depth`, `Data volume`, total duration, completion estimate) remain readable without running into one another.
7. Hover any truncated KLAB label in those panels and confirm a tooltip shows the full text/value.
8. Confirm labels such as `E-mail monitoring`, `Disk mirroring`, `Image monitoring`, `Plasma cleaner`, `Show stage position`, and long status/value labels remain readable without tiny fallback text.
9. Open the Viewport and confirm `Show grid lines`, `Show labels`, `Show stage position`, and `Show axes` now sit in a clear left-side KLAB toggle column with no overlap.
10. Confirm the zoom slider, FOV readout, and help button remain readable in the Viewport after the KLAB control reflow.
11. Hover and move around the Viewport and confirm the ROI toolbar buttons (`Rectangle`, `Circle`, `Triangle`, `Draw your own`, imported shapes, `Import`, `Delete SVG`) remain fixed-width instead of resizing dynamically.
12. Confirm the old `Acquisition manager` Viewport button is gone and that the workflow entry point is now the new button in `Stack acquisition` in both UI modes.
13. Open the Overview Settings and Grid Settings dialogs and confirm the new `Saved imaging settings` panel is present and that `Save current settings as...` now sits inside that panel directly below the imaging-parameter block.
14. In those dialogs, confirm the `Saved imaging settings` panel exposes saved-preset selection, `Apply saved settings`, `Manage...`, and `Get current settings from SEM` in a readable order without overlap.
15. Confirm text is not being reduced below the new practical KLAB minimum and that remaining tight spots, if any, are caused by geometry limits rather than adaptive font collapse.
16. Relaunch SBEMimage in KLAB mode and confirm Main Controls and Viewport both open normally without a startup exception.

Expected result:
- KLAB no longer solves overflow by shrinking text to the old hard-to-read compact sizes.
- KLAB now uses a fixed `10 pt` baseline instead of the previous oversized baseline.
- Main Controls uses more KLAB-only width headroom and cleaner per-panel geometry rather than crowding text into the old native coordinates.
- When a KLAB label still exceeds its lane, it is ellided cleanly and exposes the full text on hover instead of overlapping adjacent controls.
- The Viewport display-controls block is readable in KLAB mode without the `Show grid lines` checkbox crowding the row beneath it.
- Main Controls has more width headroom in KLAB mode.
- Layout-managed dialogs prefer width growth or spacing adjustments over font reduction.
- Any remaining overflow should be isolated, visible, and fixable with targeted geometry work rather than hidden behind unreadably small text.
- KLAB startup no longer fails with `Viewport.__init__() got multiple values for argument 'use_klab_ui'`.

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

### F. Imported-image isolation from stub archives

- [ ] Load a configuration that already contains archived stubs from earlier sessions.
- [ ] Enable `Show stub OV` and confirm archived stubs appear in the background stub layer.
- [ ] Disable `Show stub OV`.
- [ ] Enable `Show imported`.
- [ ] Confirm the archived stubs do not appear at all under `Show imported`.
- [ ] Confirm any genuine imported images still appear.
- [ ] Open `Modify images` and confirm the `Move up` / `Move down` controls are no longer present.
- [ ] Confirm the `Import`, `Delete`, `Modify`, and `Close` buttons are all visible and do not overlap.
- [ ] Confirm imported images remain behind stub images, overviews, and grids in the Viewport.

Expected result:
- [ ] Archived stubs are not treated as generic imported images anymore, including in older configs.
- [ ] `Show imported` only affects true imported images.
- [ ] Imported images are always a background layer rather than a user-reordered foreground overlay stack.

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

- [ ] Launch SBEMimage and open Main Controls plus the Viewport.
- [ ] In both native and KLAB UI, confirm the `Acquisition manager` button appears below the Stack acquisition base-directory field instead of below the Viewport grid selector area.
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

### H. Viewport and KLAB follow-up verification checklist

- [ ] Launch SBEMimage in the native/original UI and open the Viewport.
- [ ] Confirm `Show grid lines`, `Show labels`, `Show stage position`, and `Show axes` now appear as four evenly spaced rows in the Viewport controls without overlap.
- [ ] Enable `Show axes` and confirm the Viewport draws the dashed stage x-axis and y-axis reference overlay.
- [ ] Press `H` while grid lines and labels are visible and confirm both overlays hide together.
- [ ] Press `H` again and confirm both overlays return together and both checkbox states stay synchronized.
- [ ] Move the mouse around the Viewport and across the ROI toolbar in the native UI and confirm `Rectangle`, `Circle`, `Triangle`, `Draw your own`, `Import`, and `Delete SVG` stay fixed in width and position.
- [ ] Relaunch with `Use KLAB UI (experimental)` enabled.
- [ ] Confirm the KLAB UI now uses `Segoe UI Variable Text` and looks narrower/cleaner than the previous `Bahnschrift` pass.
- [ ] In KLAB Viewport, confirm the four display toggles keep the same vertical spacing and do not overlap the zoom/FOV controls.
- [ ] Move the mouse around the KLAB Viewport and across the ROI toolbar and confirm the ROI buttons no longer resize or shift dynamically.
- [ ] In KLAB `Stack acquisition`, inspect the right-side metrics panel and confirm `Estimated total duration (imaging / stage moves / cutting):` is fully visible or wraps cleanly without being cropped above or below.
- [ ] Confirm the duration value, completion estimate, current-slice row, and progress bar all remain readable and use the available right-side width without colliding.
- [ ] With grid labels visible, pan the Viewport and confirm grid/overview labels remain visible instead of disappearing during motion.
- [ ] Hide grid lines, pan the Viewport, and confirm grid outlines do not reappear temporarily during panning.
- [ ] Move the mouse around the Viewport and confirm the mouse-position readout stays on one line, switches to a shorter `Stg ... | SEM ...` format when needed, and no longer clips awkwardly.

Expected result:

- [ ] The ROI toolbar is visually stable in both native and KLAB UI.
- [ ] The Viewport display toggles have consistent vertical spacing in both UI modes.
- [ ] `H` acts as a fast hide/show shortcut for both grid lines and grid labels.
- [ ] KLAB uses the new `Segoe UI Variable Text` face without returning to unreadably small adaptive text.
- [ ] The KLAB `Stack acquisition` metrics panel uses more of the available width and no longer vertically clips wrapped text.
- [ ] Grid-line and label visibility remain consistent while panning instead of changing momentarily for responsiveness shortcuts.
- [ ] The Viewport coordinate readout now uses a compact single-line format that fits the available width, with the full text still available on hover.

### I. KLAB font-aware layout verification checklist

- [ ] Launch SBEMimage with `Use KLAB UI (experimental)` enabled.
- [ ] Confirm the KLAB UI still uses the current sans-serif font path and does not fall back to the old tiny adaptive text.
- [ ] In `SEM`, confirm the device name and beam row fit cleanly without vertical clipping.
- [ ] In `Stage`, confirm the device name, `Last confirmed stage position:`, `X: ...`, and `Z: ...` rows all fit within their boxes and use the panel width more naturally.
- [ ] Confirm the KLAB `Stage` panel now shows `X` and `Y` on separate lines so the full coordinates remain visible without truncating the combined `X/Y` row.
- [ ] Confirm the KLAB `Stage` card now grows enough vertically that the `Z: ...` row is fully visible instead of being clipped at the bottom edge.
- [ ] In `Overviews`, confirm `OV size`, `Magnification`, `Dwell time`, `Debris detection area`, and `Location` all fit within the panel, with longer values wrapping cleanly instead of being cut off.
- [ ] In `Tile grids`, confirm `Grid size`, `Tile size`, `Active tiles`, `Pixel size`, `Dwell time`, and `Location of tile 0` use the panel width and do not clip vertically.
- [ ] In `Stack acquisition`, confirm the right-side dose, area/depth/data, duration, completion estimate, current-slice row, and progress bar remain visible after values update.
- [ ] Change the selected overview and selected grid a few times and confirm the KLAB panel geometry updates with the new values instead of keeping stale row heights.
- [ ] Toggle acquisition options that affect stack estimates and confirm the `Stack acquisition` right panel reflows after the values change.
- [ ] In the KLAB stack-acquisition option block, confirm `E-mail monitoring`, `Take overviews`, `Debris detection`, `"Ask user" mode`, and `Use TCP` fit more cleanly before the `...` buttons.
- [ ] Resize Main Controls slightly and confirm the KLAB reflow remains stable and does not enter a resize/flicker loop.

Expected result:

- [ ] KLAB panel geometry is now driven by font metrics and current text content rather than the legacy fixed label heights from `main_window.ui`.
- [ ] Switching to a wider modern sans-serif font no longer causes the top summary panels or stack metrics panel to clip vertically.
- [ ] The KLAB `Stage` and stack-option areas now solve their remaining fit problems through better width/height distribution rather than smaller text.
- [ ] Remaining overflow, if any, should now be isolated to genuine panel-width limits rather than stale one-line bounding boxes.

## New Issues Found Today

- Issue ID: `2026-03-12-01`
- Title: `Modify images` dialog semantics are unclear for archived stubs
- Severity: `Medium`
- Repro steps:
  - Open `Modify images` from the Viewport.
  - Select an entry labeled `Stub archive ...`.
  - Click `Modify`.
- Expected:
  - The UI should make it clear what `Modify` will change for that item, especially if the item is an archived stub rather than a true imported reference image.
- Actual:
  - `Modify` opens the generic imported-image editor and allows changes to centre position, pixel size, rotation, horizontal flip, and transparency for the selected entry.
- Logs:
  - No runtime error; behavior traced in code.
- Notes:
  - The action is wired in `src/dialog/viewport/ModifyImagesDlg.py` via `modify_imported()`.
  - The dialog opened is `src/dialog/viewport/ModifyImageDlg.py`.
  - `ModifyImageDlg.apply_changes()` edits `centre_sx_sy`, `pixel_size`, `rotation`, `flipped`, and `transparency`, then redraws the Viewport.

- Issue ID: `2026-03-12-02`
- Title: Archived stubs are still listed in `Modify images`
- Severity: `Low`
- Repro steps:
  - Acquire multiple stub overviews so older ones are archived.
  - Open `Modify images`.
- Expected:
  - Either only true imported images should appear there, or the dialog should explicitly distinguish imported images from archived stubs and explain why both are present.
- Actual:
  - Archived stubs appear in the same list because the dialog iterates the entire `ImportedImages` collection without filtering by `source_kind`.
- Logs:
  - No runtime error; behavior traced in code.
- Notes:
  - Archived stubs are intentionally stored in `ImportedImages` for persistence/deletion (`src/Viewport.py`, `_vp_archive_previous_stub()`).
  - `ModifyImagesDlg.populate_image_list()` currently lists every `self.imported` entry, including `source_kind = stub_archive_*`.
  - This explains why archived stubs show up under the imported-image management workflow even though they are no longer shown by the `Show imported` viewport toggle.

## Instruction Reminder

Any new notebook created after this one must include:
- the persistent guideline block,
- a carry-forward major changes section,
- and an imported checklist of current tasks.
