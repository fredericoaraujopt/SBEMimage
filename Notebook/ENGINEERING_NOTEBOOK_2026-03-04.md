# SBEMimage Engineering Notebook - 2026-03-04

## Summary

Date: 2026-03-04  
Author: Codex (diagnosis pass)

Purpose:
- Continue from `PROJECT_REWORK_PLAN.md`.
- Diagnose what has already been implemented in the local working tree.
- Provide a systematic operator checklist to validate each implemented change.
- Identify remaining TODOs before further code edits.

Scope of this notebook entry:
- No new feature implementation in this pass.
- Repository review + git history review + implementation status mapping.

Today at a glance (quick summary):
- Completed: diagnosis of implemented rework, environment/import smoke checks, and checklist execution logging through Sections A-H.
- Confirmed working today: New Project flow (A), OV queue core flow (B, with UX caveats), OV reliability checks (C), grid placement behavior (D placement only), visual registration check (E), provenance locking (G), direct selection/editing (H).
- Not working / unstable today: grid acquisition reliability and acquisition-state integrity (Section F-related behavior observed during grid runs).
- Not run yet: Section J (config persistence).
- Main blocker for next session: tile acquisition path can move stage but fail to capture while still marking/keeping tiles as acquired.

Repository snapshot:
- Branch: `master`
- Latest committed baseline: `f729367` (`Update version`)
- Local state: significant uncommitted rework changes present in core files.

Current local modified/untracked files (implementation currently in working tree):
- Modified: `src/Acquisition.py`, `src/Grid.py`, `src/GridManager.py`, `src/MainControls.py`, `src/Overview.py`, `src/OverviewManager.py`, `src/Tile.py`, `src/Viewport.py`, `src/acq_func.py`, `src/config_template.py`, `src/default_cfg/default.ini`, `src/sem/SEM_SmartSEM.py`
- New: `src/acq_guardrails.py`, `src/dialog/viewport/OVQueueDlg.py`, `PROJECT_REWORK_PLAN.md`

## Diagnosis

### 1) Lay of the land (current architecture)

Primary app entry and orchestration:
- `src/sbemimage.py` starts Main Controls + Viewport.
- `src/MainControls.py` is the top-level control window and action router.
- `src/Viewport.py` is the main interaction surface for OVs/grids/stage context actions.
- `src/Acquisition.py` handles acquisition flow and hardware-facing imaging loops.

Data/model layers relevant to this rework:
- Grid model/state: `src/Grid.py`, `src/Tile.py`, `src/GridManager.py`
- Overview model/state: `src/Overview.py`, `src/OverviewManager.py`
- Manual OV operations: `src/acq_func.py`
- New shared guardrail helpers: `src/acq_guardrails.py`
- Config defaults/template compatibility: `src/default_cfg/default.ini`, `src/config_template.py`

Git history context:
- Recent committed history mostly contains upstream maintenance and UI changes.
- The rework described in `PROJECT_REWORK_PLAN.md` is currently represented as local uncommitted changes (not yet in committed history).

### 2) Implemented vs pending status (mapped to TODO groups)

Status key:
- Implemented = code exists and wired in local tree.
- Partial = code exists for core behavior, but acceptance/UX/testing goals not fully complete.
- Pending = not yet found in code.

#### New Project Flow
Status: Implemented (local, uncommitted)

Evidence:
- New action + toolbar wiring in `MainControls.py` (`actionNewProject`).
- Guided flow implemented in `open_new_project_dlg`:
  - new config naming
  - base dir selection + writable check
  - optional OV0/Grid0 reinit
  - dry-run preview confirmation
  - reset/clear/save workflow

Notes:
- Functional behavior appears implemented; needs runtime validation.

#### OV Workflow UX
Status: Implemented (core), Partial (full UX polish)

Evidence:
- New OV queue dialog in `src/dialog/viewport/OVQueueDlg.py`.
- Queue open/wiring in `Viewport.py` (`vp_open_ov_queue_panel`).
- One-click queue actions: activate/deactivate, acquire selected, clear image, delete last.
- Inactive OV visibility improved (footprint drawn, not label-only).
- Double-click opens settings for selected OV/grid.

Notes:
- Requires operator validation for discoverability and expected behavior under overlap.

#### OV Acquisition Reliability
Status: Partial

Implemented:
- OV diagnostics logging.
- Stage arrival checks.
- Manual OV tiled fallback path (`acq_func.py`) with `auto_tile_ov_fallback`.

Pending/partial aspects:
- User-facing error guidance is still basic (limited auto-fix guidance messaging).
- No explicit regression tests for ZEISS Gemini manual refresh path found.

#### Grid Placement UX
Status: Partial

Implemented:
- Area-first sizing helper in `GridManager.estimate_grid_layout_for_drag`.
- Draw-grid uses estimated rows/cols from dragged ROI.
- Live drag preview text + footprint overlay in Viewport.

Pending/partial aspects:
- Post-placement summary dialog is not clearly present.
- "Fit-to-ROI mode" appears implicit/default rather than explicit toggle.

#### OV/Grid Registration Reliability
Status: Partial

Implemented:
- Quick registration geometry check action in Viewport (`vp_registration_check`).
- Registration coordinate handling improved using acquired coordinates where present.
- Critical fix: tile registration origin now uses tile dimensions (not grid dimensions).

Pending/partial aspects:
- No guided recalibration shortcut from warning dialog found.
- Predicted tile footprint overlay over OV before acquisition is limited to quick-check messaging and existing overlays.

#### Motion Sanity Checks
Status: Partial

Implemented:
- Per-tile expected-vs-observed shift sanity check (`Acquisition._motion_sanity_check`).
- Stage arrival validation for OV and tile moves.

Pending/partial aspects:
- No dedicated "stage displacement verification quick test mode" found.
- No explicit operator override/acknowledgement flow after motion fail (currently pause/interruption behavior).

#### Direct Viewport Selection & Editing
Status: Implemented (core), Partial (panel UX)

Implemented:
- Direct object selection behavior present.
- Selection highlight + compact inspector overlay added.
- Double-click opens settings for selected OV/grid.

Pending/partial aspects:
- Dedicated floating settings panel is approximated via existing dialogs rather than a new focused floating editor.

#### Viewport Rendering Stability
Status: Partial

Implemented:
- Render diagnostics toggles (`render_debug`, `render_antialias`).
- Overlay diagnostics text and antialias toggles.

Pending/partial aspects:
- No strong evidence of deeper partial-redraw/flicker-elimination redesign.
- Needs real pan/zoom stress validation on target workstation.

#### Spatial Provenance Locking
Status: Implemented (core), Partial (full metadata/audit UX)

Implemented:
- Grid/OV lock + acquired state persisted in model/config.
- Movement blocked for locked objects until explicit unlock.
- Unlock actions show warning and log message.
- Acquired position fields added for registration export path.

Pending/partial aspects:
- Visual badges are partially represented via overlay/status text, not full dedicated badge system.
- Full metadata export audit scope beyond registration fields should be validated.

#### Adaptive Crosshair UX
Status: Implemented

Evidence:
- Stage indicator scaling and pen width now adapt to viewport zoom.

#### Acquisition Parameter Guardrails
Status: Partial

Implemented:
- Guardrail helper module and grid-level checks.
- Strict mode option (`guardrail_strict`) to block acquisition.

Pending/partial aspects:
- OV guardrails mostly handled via fallback behavior rather than full preflight UI warnings.
- One-click auto-correction suggestions in UI not clearly present.

### 3) Systematic test checklist (operator runbook)

Run this as a checklist, one item at a time. Mark Pass/Fail and capture logs/screenshots for any fail.

Pre-test setup:
- [ ] Confirm environment: `conda run -n sbemimage_env python -V`
- [ ] Optional static smoke: `python -m compileall src`
- [ ] Optional import smoke: `PYTHONPATH=src python -c "import Acquisition, Viewport, MainControls, acq_func, acq_guardrails; print('import-ok')"`
- [ ] Launch app with intended config (Gemini hardware settings as used in prior session).

A. New Project workflow:
- [ ] Open `Configuration -> New Project...`.
- [ ] Verify prompts appear in this order: new config name -> base directory -> optional OV0/Grid0 reinit -> preview changes confirmation.
- [ ] Confirm preview text includes reset + clear actions.
- [ ] Apply and verify:
  - slice counter reset to 0
  - interrupted state reset
  - tile previews cleared
  - OV images + stub images cleared
  - imported overlays cleared
- [ ] Reopen app (optional) and verify settings persisted to new config.

B. OV queue / OV UX:
- [ ] Open OV queue panel from viewport context menu.
- [ ] Drag-create a new OV and confirm it appears immediately as a visible footprint.
- [ ] In queue, toggle active/inactive and confirm viewport updates.
- [ ] In queue, `Acquire Selected` triggers OV acquisition path.
- [ ] In queue, `Clear Image` clears OV display image and status updates.
- [ ] Delete constraints test:
  - OV0 delete blocked
  - only highest index OV deletable

C. OV acquisition reliability:
- [ ] Acquire OV at normal settings; verify success and timestamp/result update.
- [ ] Reproduce low-mag large-FOV OV case; verify fallback behavior attempts tiled acquisition.
- [ ] If acquisition fails, verify logs contain diagnostics fields (frame size, mag estimate, dwell, bit depth context).

D. Grid placement WYSIWYG:
- [ ] Alt-drag new grid ROI and verify live rows/cols growth text during drag.
- [ ] Confirm resulting grid footprint approximates dragged ROI.
- [ ] Repeat with different pixel sizes and overlaps; record mismatch if any.

E. Registration checks:
- [ ] Right-click selected tile and run registration check action.
- [ ] Verify footprint message reports expected OV pixel bounds.
- [ ] Acquire OV + tile and visually confirm alignment.
- [ ] Check metadata path consistency after acquisition (tile/OV registration coordinates).

F. Motion sanity behavior:
- [ ] Acquire multi-tile grid where stage movement should be obvious.
- [ ] Confirm no false-positive pauses in normal run.
- [ ] Attempt known problematic setup (if safe) and verify motion sanity failure triggers pause/interruption.

G. Provenance locking:
- [ ] Acquire OV/grid, then attempt drag move.
- [ ] Confirm movement blocked while locked.
- [ ] Use explicit unlock action; verify warning dialog appears.
- [ ] After unlock, confirm move allowed and event is logged.

H. Direct selection/editing:
- [ ] Single-click select OV/grid and confirm highlight/inspector visible.
- [ ] Double-click selected OV/grid and confirm corresponding settings dialog opens.
- [ ] Right-click selected OV/grid and verify contextual actions are intuitive.

I. Rendering/crosshair UX:
- [ ] With overlapping layers (stub + OVs + grids), pan/drag and assess flicker.
- [ ] Toggle render diagnostics and antialias from context menu; verify overlay updates.
- [ ] Zoom across wide range and confirm stage crosshair remains visible and proportionate.

J. Config persistence:
- [ ] Save config and restart app.
- [ ] Confirm persisted keys survive restart:
  - guardrails (`guardrail_min_mag`, `guardrail_max_mag`, `guardrail_strict`)
  - OV fallback/defaults (`auto_tile_ov_fallback`, `ov_single_frame_min_mag`, `new_ov_default_active`)
  - viewport render toggles (`render_debug`, `render_antialias`)
  - grid/OV lock + acquired state fields

Failure logging template for each failed test item:
- Test ID:
- Exact steps:
- Expected:
- Actual:
- Log excerpt timestamp:
- Screenshot/video path:
- Suspected module/file:

### 4) Checklist execution results (2026-03-04)

Executed items requested for this pass:

- [x] Confirm environment: `conda run -n sbemimage_env python -V` and code page check
  - Output: `Python 3.12.12`
  - Output: `Active code page: 437`
  - Result: Python version PASS; code page expected `65001` but observed `437` (recorded mismatch).

- [x] Optional static smoke: `conda run -n sbemimage_env python -m compileall src`
  - Result: PASS (compile completed)
  - Note: existing `SyntaxWarning` in `src/sem/SEM_SharkSEM.py` invalid escape sequence (`'\\.'`) was reported; non-blocking for this smoke test.

- [x] Optional import smoke:
  - Command equivalent run in PowerShell:
    - `$env:PYTHONPATH='src'; conda run -n sbemimage_env python -c \"import Acquisition, Viewport, MainControls, acq_func, acq_guardrails; print('import-ok')\"`
  - Output: `import-ok`
  - Result: PASS

- [x] Launch app with intended config baseline command:
  - Command: `conda run -n sbemimage_env python src/sbemimage.py`
  - Result: launch process chain detected (`cmd.exe` + `python.exe`) = PASS for startup
  - Note: Gemini configuration selection is interactive in startup dialog and must be confirmed manually by operator.

Additional operator-reported results:

- [x] New Project workflow (Section A checklist) completed end-to-end
  - Result: all checklist items worked in current manual run.
  - Usability note: current setup/review prompts feel clunky and somewhat confusing.
  - Example confusing review items: `slice counter reset to 0`, `interrupted state reset`, and similar state-reset wording are not very intuitive for operators.
  - Follow-up recommendation: simplify wording in the preview/confirmation step and group reset items into clearer user-facing categories.

- [x] OV queue / OV UX (Section B checklist) - operator run results
  - [x] Open OV queue panel from viewport context menu: works.
  - [x] Drag-create new OV and immediate visible footprint: works.
    - Follow-up issue: new OV footprint dimensions do not match the square that was drawn.
  - [x] Toggle active/inactive in queue and viewport update: works.
    - Follow-up issue: changing dimensions does not dynamically update dimensions in viewport (operator-observed).
  - [x] `Acquire Selected` in queue triggers OV acquisition path: works.
  - [x] `Clear Image` clears OV display image and status updates: works.
  - [x] Delete constraints (`OV0` delete blocked): works.

Additional OV settings behavior note:
- In the overview settings popup, changing `OV size (px)` does not appear to affect OV footprint in viewport.
- Changing magnification does change OV footprint in viewport.
- Diagnostic interpretation: OV viewport footprint may still be primarily controlled by magnification/pixel size linkage, while direct size-parameter changes are not being applied/redrawn as expected.

- [x] OV acquisition reliability (Section C checklist) - operator run results
  - [x] Acquire OV at normal settings; verify success and timestamp/result update: works.
  - [x] Reproduce low-mag large-FOV OV case; verify fallback behavior attempts tiled acquisition: works.
  - [x] If acquisition fails, verify logs contain diagnostics fields (frame size, mag estimate, dwell, bit depth context): works.

- [x] Grid placement WYSIWYG (Section D checklist) - operator run results
  - [x] Alt-drag new grid ROI and verify live rows/cols growth text during drag: works.
  - [x] Confirm resulting grid footprint approximates dragged ROI: works.
  - [x] Repeat with different pixel sizes and overlaps; record mismatch if any: works in current run.
  - Correction (latest operator update): grid acquisition is not working reliably after placement.
  - Observed behavior: stage moves to the expected tile position, but image capture does not complete/does not occur.
  - Status update: treat grid placement as PASS, but grid acquisition path as FAIL until fixed.

- [x] Registration checks (Section E checklist) - operator run results
  - [x] Visual OV/tile alignment confirmed by operator in current run.
  - Note: Section E appears functionally fine at this stage.
  - Caution: perform deeper metadata/coordinate consistency validation in a future pass.

- [ ] Motion sanity behavior (Section F checklist) - operator run results
  - [x] Stage movement is obvious during multi-tile grid attempts.
  - [ ] Image acquisition is not reliably completed in this scenario.
  - [ ] Acquisition state tracking appears inconsistent: system reports tiles as already acquired even when image is not actually obtained.
  - Evidence:
    - `2026-03-04 16:52:29 | CTRL  : Tile GRID 3.2 already acquired. Skipping.`
    - `2026-03-04 17:06:08 | CTRL  : Tile GRID 2.0 already acquired. Skipping.`
  - Additional note: this persists even after using reset tile previews in grid settings.
  - Status update: Section F is currently FAIL and needs root-cause analysis in acquisition-state handling.

- [x] Provenance locking (Section G checklist) - operator run results
  - [x] Works in current run.

- [x] Direct selection/editing (Section H checklist) - operator run results
  - [x] Works in current run.

## Next TODOs

Priority P0 (must stabilize next):
- Add explicit operator override flow for motion sanity failures (acknowledge + continue / abort).
- Add dedicated stage displacement verification quick test mode (session preflight).
- Strengthen OV failure user guidance with direct actionable fixes in dialog text.
- Fix tile acquired-state integrity: do not mark/retain tiles as acquired when capture is incomplete; ensure reset actions clear all gating state used by acquisition skip logic.

Priority P1 (high UX impact):
- Add explicit post-placement summary after grid draw commit (centre, footprint, tile count).
- Add clearer provenance badges in viewport (not only inspector text).
- Improve viewport flicker behavior beyond diagnostics toggles (measure and reduce redraw churn).

Priority P2 (quality/completeness):
- Add regression tests for new project flow and manual OV refresh/fallback paths.
- Add targeted tests for persistence compatibility of newly added config keys.
- Expand docs/user guide with the new workflow and troubleshooting steps.

Recommended next working sequence:
- 1) Run checklist above and collect evidence.
- 2) Convert any failures to concrete issues with reproduction data.
- 3) Only then implement corrective patches in small, reviewable batches.

## TO BE CONTINUED

### 1) Troubleshooting grid acquisition

Current issue snapshot:
- Stage motion is observed and appears directionally correct.
- In failing runs, image capture does not complete/does not occur.
- System can still report tiles as already acquired and skip them on re-run.
- This persists even after reset tile previews from grid settings.

Known evidence to reuse:
- `2026-03-04 16:52:29 | CTRL  : Tile GRID 3.2 already acquired. Skipping.`
- `2026-03-04 17:06:08 | CTRL  : Tile GRID 2.0 already acquired. Skipping.`

Tomorrow-first troubleshooting focus:
- Verify where acquired-state is set in tile/grid acquisition flow.
- Verify reset tile previews clears every state used by skip logic (preview, acquired flag, metadata markers, persistence fields).
- Confirm failure path on incomplete grab does not set acquired/locked states.
- Add temporary high-signal logging around state transitions: before grab, after grab success, after grab failure, before skip decision.

### 2) Checklist J section (not executed yet)

Pending test set:
- Save config and restart app.
- Verify persisted keys survive restart:
  - guardrails (`guardrail_min_mag`, `guardrail_max_mag`, `guardrail_strict`)
  - OV fallback/defaults (`auto_tile_ov_fallback`, `ov_single_frame_min_mag`, `new_ov_default_active`)
  - viewport render toggles (`render_debug`, `render_antialias`)
  - grid/OV lock + acquired state fields

Pass criteria:
- Each key retains expected value after full restart.
- No silent fallback to defaults for newly introduced keys.
- No config migration warnings/errors in logs.

### 3) Follow-up tasks from checklist notes

Follow-up from A:
- Simplify new-project preview wording and group reset actions into clearer operator categories.

Follow-up from B:
- Fix mismatch between dragged OV rectangle and resulting footprint dimensions.
- Make viewport footprint update dynamically when OV dimensions/settings change.
- Clarify relationship between `OV size (px)` and on-viewport OV footprint scaling.

Follow-up from D/F:
- Separate statuses in docs and UI: grid placement success is independent from grid acquisition success.
- Fix acquisition-state integrity so failed/incomplete grabs cannot be treated as acquired.
- Ensure reset controls clear all state that participates in skip decisions.

Follow-up from E:
- Run deeper metadata/coordinate consistency verification (not only visual alignment).

Follow-up from I:
- Complete rendering/crosshair stress checks (overlap flicker + diagnostic toggles + zoom behavior) and record outcomes.
