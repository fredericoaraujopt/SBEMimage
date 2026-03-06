# SBEMimage Rework Project Document

Last updated: 2026-03-02

## 1) Objective

Rework SBEMimage to improve reliability and performance for large GEMINISEM acquisition projects, while keeping current acquisition capability intact during transition.

## 2) Current Repository Snapshot

- App type: Python + PyQt desktop application for SEM/SBEM acquisition control.
- Main entrypoint: `src/sbemimage.py` (also launched by `SBEMimage.bat`).
- Primary high-complexity modules:
  - `src/Viewport.py` (~3827 lines)
  - `src/MainControls.py` (~3222 lines)
  - `src/Acquisition.py` (~2876 lines)
- Hardware abstraction:
  - SEM implementations in `src/sem/`
  - Microtome implementations in `src/microtome/`
- Config model:
  - Read-only templates in `src/default_cfg/`
  - Runtime/user configs in `cfg/`
- Test suite exists in `tests/` but appears mixed with legacy/auxiliary files.

## 3) Immediate Baseline Status (Local)

- Canonical runtime environment: Conda `sbemimage_env` (Python 3.12).
- Canonical launch command: `conda run -n sbemimage_env python src/sbemimage.py`
- Dependencies installed from `requirements.txt`.
- Initial startup issue found and fixed locally by installing missing package:
  - `ModuleNotFoundError: No module named 'cv2'`
- SBEMimage now starts successfully (GUI loop reached).
- App launched for manual testing with:
  - `python src/sbemimage.py`

## 4) Rework Principles

- Stabilize behavior first, then optimize performance.
- Keep hardware-facing code paths testable via simulation/mock modes.
- Avoid large cross-cutting rewrites without measurable baselines.
- Reduce risk by introducing clear module boundaries around acquisition flow.
- Prioritize semi-standalone modules and incremental modular changes to avoid
  spaghetti-code coupling.
- Require explicit interfaces between modules (UI, acquisition engine,
  hardware adapters, remote control) so changes stay isolated.

## 5) Phase Plan

## Phase A - Baseline and Observability

- Define target workflows for GEMINISEM large acquisitions.
- Capture startup time and key UI/action latencies.
- Standardize logging/telemetry points for acquisition lifecycle and failures.
- Build reproducible smoke checks (startup, config load, simulation acquisition path).

## Phase B - Reliability Hardening

- Review broad `except Exception` paths in critical loops.
- Normalize error handling across acquisition, SEM, and microtome layers.
- Add failure injection tests in simulation mode.
- Improve recovery behavior for known transient faults (frame grab, comm timeout, I/O).

## Phase C - Performance and Throughput

- Profile acquisition loop and image handling pipeline.
- Identify avoidable copies/conversions in tile/overview paths.
- Optimize save/write pipeline and UI-thread interactions.
- Reduce blocking operations in main UI paths where safe.

## Phase D - Architecture Refactor (Incremental)

- Decompose `Viewport`, `MainControls`, and `Acquisition` into smaller units.
- Introduce clearer interfaces between UI orchestration and acquisition engine.
- Isolate hardware adapters behind stricter contracts for easier mocking.
- Keep each refactor step deployable and backward-compatible to reduce risk
  during ongoing acquisition use.

## Modularization Rule (Team Constraint)

- All structural work should move SBEMimage toward semi-standalone modules.
- New functionality should be added behind module interfaces, not by extending
  deep cross-module call chains.
- Refactors should prefer extraction and composition over enlarging existing
  monolithic files.

## Phase E - Release Readiness

- Regression checklist for simulation + hardware modes.
- Operator-oriented test script for large project runs.
- Upgrade/migration notes for configs and workflows.

## 6) Manual Testing Session Log (Start Here)

Use this section while running SBEMimage now.

### Environment

- Date:
- Operator:
- Config used:
- Mode: Simulation / Hardware

### Test Checklist

- Launch application and select configuration
- Open Main Controls and Viewport without errors
- Load/save configuration
- Configure acquisition settings for a large tile set
- Start, pause, resume, stop acquisition (simulation if needed)
- Verify image save locations and metadata outputs
- Exercise autofocus / debris / monitoring settings where applicable
- Confirm behavior after intentional interruption (network/device/log path)

### Issues Found

For each issue:

- ID:
- Title:
- Severity: Critical / High / Medium / Low
- Repro steps:
- Expected result:
- Actual result:
- Logs/files:
- Notes:

### Logged Issues (Current Session)

- ID: 001
- Title: Startup crash after selecting `gemini.ini` (`AttributeError` in `has_fcc`)
- Severity: High
- Repro steps: Launch SBEMimage, acknowledge startup warning, select `gemini.ini`.
- Expected result: Main Controls + Viewport open.
- Actual result: Application closes during startup.
- Logs/files: `log/SBEMimage.log` traceback at `2026-03-02 14:22:08`
- Notes: Root cause was type mismatch in `src/sem/SEM_SmartSEM.py` (`DP_CAPCC_FITTED` returned numeric value). Fixed by handling both string and numeric return types in `has_fcc()`.

- ID: 002
- Title: No dedicated one-step "Start New Project" workflow
- Severity: High
- Repro steps: Attempt to begin a fresh acquisition project from an existing config/session state.
- Expected result: Single guided action to create new project context (new config + new base dir + clean workspace state).
- Actual result: Multi-step manual process (save config as new, change base dir, reset, manually clear/rebuild OVs/grids).
- Logs/files: UI behavior in Main Controls / Viewport settings dialogs.
- Notes: `OV 0` and `Grid 0` are persistent anchors and cannot be deleted, which makes full reset non-obvious for operators.

- ID: 003
- Title: New OVs created by drag are inactive/invisible in workflow
- Severity: Medium-High
- Repro steps: In Viewport, `Ctrl + drag` to create a new OV.
- Expected result: New OV appears as a visible object immediately and is ready for next imaging step.
- Actual result: OV may appear only as label text (e.g., `OV 1 (inactive)`), requiring extra dialog navigation to activate and then image.
- Logs/files: Viewport + OV Settings interaction.
- Notes: Current behavior creates friction and uncertainty during manual setup/navigation.

- ID: 004
- Title: OV acquisition fails with repeated `grab incomplete` (OV 0 and OV 1)
- Severity: High
- Repro steps: Activate OV, select OV in Viewport, click `Refresh OV(s)`.
- Expected result: OV is acquired and displayed.
- Actual result: Stage moves to OV position, then SEM acquisition fails twice with `grab incomplete`.
- Logs/files: Session log entries around `2026-03-02 15:06` to `15:07`.
- Notes: Reproducible for both OV 0 and OV 1 in current Gemini setup; likely in OV image-grab path, not stage movement.

- ID: 005
- Title: OV acquisition succeeds at higher mag (~300x) but fails at very low mag (~46x)
- Severity: High
- Repro steps: Configure OV at low magnification/large FOV, acquire OV; then increase to ~300x and retry.
- Expected result: SBEM handles oversized OV requests robustly (e.g., auto-tile or clear user feedback with recovery path).
- Actual result: Low-mag OV fails with `grab incomplete`; higher mag works.
- Logs/files: Operator report + OV acquisition logs (`grab incomplete`).
- Notes: Current OV path uses single-frame acquisition; stub path is tiled and robust for large areas.

- ID: 006
- Title: Grid draw interaction does not map clearly to dragged target area
- Severity: High
- Repro steps: In Viewport, `Alt + drag` to define a new grid area over desired ROI.
- Expected result: The imaged grid footprint matches the dragged area/location closely.
- Actual result: Resulting imaged area can differ from the dragged rectangle/location, creating setup uncertainty.
- Logs/files: Operator report from manual setup workflow.
- Notes: Current grid draw behavior appears constrained by template-grid tile geometry and coordinate transforms, not direct WYSIWYG area definition.

- ID: 007
- Title: OV and grid/tile imagery are spatially offset (misregistration)
- Severity: Critical
- Repro steps: Acquire OV, then acquire tile(s) from overlaid grid at same ROI.
- Expected result: Tile preview/image aligns with OV background at corresponding location.
- Actual result: Visible offset/mismatch between tile image footprint and OV.
- Logs/files: Manual tests around `2026-03-02 15:32` with successful tile stats but misaligned visualization.
- Notes: High operational risk for targeting accuracy; likely involves stage/coordinate calibration and/or transform consistency between OV and tile acquisition paths.

- ID: 008
- Title: Viewport flicker with overlapping layers (OVs, stub, grids) during movement
- Severity: Medium-High
- Repro steps: Display overlapping OVs/stub/grids and pan/move/reposition in Viewport.
- Expected result: Stable rendering with minimal visual artifacts.
- Actual result: Visible flicker/jitter of overlapping layers while moving.
- Logs/files: Operator observation during manual navigation/setup.
- Notes: Impacts usability and confidence during alignment/targeting.

- ID: 009
- Title: Acquired elements can still be moved (provenance risk)
- Severity: Critical
- Repro steps: Acquire OV/grid/tile, then move corresponding object in Viewport.
- Expected result: Acquired objects are locked (or move requires explicit override) so displayed positions remain true to imaged locations.
- Actual result: Object movement remains possible, risking mismatch between display and real acquired location.
- Logs/files: Operator workflow observation.
- Notes: High risk for interpretation errors and traceability loss.

- ID: 010
- Title: Stage/beam crosshair does not adapt to zoom level
- Severity: Medium
- Repro steps: Change viewport zoom across wide range while observing stage/beam crosshair marker.
- Expected result: Crosshair scales appropriately with zoom for consistent visibility and precision.
- Actual result: Marker size/appearance not ergonomically adapted across zoom levels.
- Logs/files: Operator workflow observation.
- Notes: Reduces navigation precision and visual clarity.

- ID: 011
- Title: High-mag tile acquisition can silently fail (`grab incomplete` / frozen frame) after parameter changes
- Severity: Critical
- Repro steps: Set very small pixel size (e.g., 8 nm), run manual grid acquire.
- Expected result: Reliable tile acquisition or proactive validation warning before run.
- Actual result: Stage moves, tile logs show near-uniform image stats (`M≈255`, `SD≈0`), then SmartSEM `grab incomplete` / frozen frame errors.
- Logs/files: Session log around `2026-03-02 15:46` to `15:49` (e.g., locked mag `27920.0`).
- Notes: Creates operator confusion ("nothing happens") and unsafe trial-and-error behavior.

- ID: 012
- Title: Actual stage displacement is far smaller than commanded tile spacing (duplicate content across grid)
- Severity: Critical
- Repro steps: Acquire a multi-tile grid after setup appears valid.
- Expected result: Each tile captures a distinct adjacent field of view according to grid geometry.
- Actual result: Tiles contain duplicated/near-identical scene content, indicating stage/beam movement is much less than expected despite logs showing moves.
- Logs/files: Operator observation during successful grid run with obvious repeated content.
- Notes: High data-integrity risk; invalidates mosaic geometry and downstream stitching assumptions.

## Product TODO - New Project Flow

- Implement a dedicated `New Project` action (menu + toolbar entry) that runs a guided setup.
- Wizard should at minimum:
  - Create/save a new user configuration file (without altering system config).
  - Require/select a new base directory and validate write access.
  - Reset acquisition counters/status (`slice_counter`, `ΔZ`, interruption state).
  - Clear viewport previews/images (OV images, stub image, tile previews, imported overlays).
  - Offer optional reinitialization of `OV 0` and `Grid 0` to defaults.
  - End with a concise preflight summary and explicit confirmation.
- Add a dry-run option (`Preview changes`) before applying.
- Add tests covering the workflow and rollback behavior on failure.

## Product TODO - OV Workflow UX

- Add an always-visible OV list/queue panel showing:
  - OV ID
  - active/inactive state
  - imaged/not imaged status
  - last acquisition timestamp/result
- Make newly drawn OVs visible immediately in the Viewport after creation.
- Make default behavior configurable:
  - Option A: new OVs default to active
  - Option B: keep inactive default but still render full OV outline clearly
- Add one-click actions in OV list:
  - activate/deactivate
  - acquire selected OV
  - clear OV image
  - delete (for deletable OVs)
- Add explicit visual state cues in Viewport (not just label text) for inactive vs active vs imaged OVs.

## Product TODO - OV Acquisition Reliability

- Add targeted diagnostics when OV acquisition fails:
  - requested frame size
  - reported/actual grabbed frame size
  - bit depth
  - dwell/cycle timing
- Ensure OV acquisition path handles current SEM frame settings consistently.
- Add regression test case for manual `Refresh OV(s)` on ZEISS Gemini workflows.
- Add automatic fallback for oversized OVs:
  - detect when requested OV exceeds reliable single-frame envelope
  - switch to tiled OV acquisition path (stub-like) automatically
  - keep one-click UX for users ("Refresh OV(s)" should still just work)
- Improve user-facing feedback:
  - show why OV failed (e.g., mag/FOV too large for single-frame grab)
  - suggest auto-fix (increase mag or enable auto-tile).

## Product TODO - Grid Placement UX

- Make grid placement WYSIWYG: dragged rectangle should represent final acquisition footprint.
- Show immediate preview of final tile coverage before commit.
- Add optional "fit to dragged ROI" mode that computes rows/cols/overlap from target area.
- Provide post-placement summary: centre, footprint (um), tile count, and expected imaged bounds.
- Add validation warning when coordinate calibration may cause placement mismatch.
- While dragging to create/resize a grid, show live subtile growth so users see
  rows/columns increase in real time to match intended area.
- Make drag interaction area-first: user defines ROI first, SBEM computes tile
  layout to fill that ROI (instead of requiring prior manual grid parameter
  tuning to approximate the ROI).

## Product TODO - OV/Grid Registration Reliability

- Add an explicit OV-grid registration check tool (quick test tile against OV).
- Show computed expected tile footprint over OV before acquisition.
- Detect and warn on likely calibration mismatch at current EHT before imaging.
- Add guided recalibration shortcut from warning dialog.

## Product TODO - Motion Sanity Checks

- Add per-tile motion sanity validation before/after acquisition:
  - compare expected XY delta vs observed image shift
  - raise immediate error if displacement is below threshold.
- Add a "stage displacement verification" quick test mode for new sessions/EHTs.
- Block full-grid acquisition when motion verification fails; require operator acknowledgement/override with explicit warning.

## Product TODO - Direct Viewport Selection & Editing

- Allow direct click selection of OVs and grids in Viewport as first-class
  editable objects.
- Show a clear selected-state highlight and a compact inspector panel for the
  selected object.
- Support immediate settings edits for selected OV/grid without hunting through
  separate dialogs/selectors.
- Provide consistent object workflow despite OV/grid role differences:
  - select
  - inspect status
  - edit key settings
  - trigger acquisition action
- Support double-click on selected OV/grid to open a floating settings panel
  (or dedicated settings window) focused on that object.
- Ensure the panel supports immediate edits of common parameters (active state,
  acquisition interval, frame/pixel size, dwell, overlap, rows/cols, rotation)
  without navigating separate global dialogs.

## Product TODO - Viewport Rendering Stability

- Reduce or eliminate flicker when multiple overlay layers are visible
  (stub + OVs + grids + previews) during pan/drag/reposition operations.
- Add render diagnostics/toggles for debugging: layer redraw timing,
  antialiasing mode, and partial redraw strategy.
- Define target interaction quality metrics (no visible flicker at normal
  operator zoom/pan speed on acquisition workstations).

## Product TODO - Spatial Provenance Locking

- Lock OV/grid/tile transforms after acquisition by default.
- Provide explicit unlock action with warning and audit log entry when moving
  previously acquired elements.
- Add clear visual state badges:
  - `acquired-locked`
  - `editable-not-acquired`
- Ensure exported metadata preserves original acquisition coordinates even if
  display objects are later edited under override.

## Product TODO - Adaptive Crosshair UX

- Scale stage/beam crosshair marker with viewport zoom level.
- Keep crosshair leg thickness and hit visibility readable across full zoom range.
- Add optional user setting for crosshair style/size sensitivity.

## Product TODO - Acquisition Parameter Guardrails

- Add pre-acquisition parameter validation for OV/grid settings:
  - pixel size vs resulting magnification range
  - frame size/dwell combinations likely to produce incomplete/frozen grabs
- Block or warn before acquisition when requested settings are outside reliable envelope.
- Provide one-click auto-correction suggestions (e.g., increase pixel size or adjust frame size/dwell).

## 7) Initial Risk Register

- Monolithic core modules increase regression risk during edits.
- Hardware API variance (SEM + microtome) complicates deterministic testing.
- Some legacy TODOs and broad exception handling can hide root causes.
- Python environment drift (repo targets 3.12 in `environment.yml`, current runtime is 3.13) may affect reproducibility.

## 8) Next Working Steps

- Run your first manual test pass and populate "Issues Found".
- Convert top issues into a prioritized implementation backlog.
- Start with Phase A instrumentation + smoke automation before major refactors.

## 9) Implementation Log (2026-03-02)

Scope note:
- Work completed without launching SBEMimage UI loop for runtime testing and
  without microscope control commands.

### Change set A - acquisition reliability + diagnostics

Files:
- `src/acq_guardrails.py` (new)
- `src/Acquisition.py`
- `src/acq_func.py`

Implemented:
- Added shared guardrail helpers for magnification envelope checks and
  diagnostics payloads.
- Added OV diagnostics logging (requested frame size, SEM frame selector,
  pixel size, magnification estimate, dwell, bit depth).
- Added stage-arrival validation after OV and tile moves.
- Added motion sanity check between consecutive tiles using phase correlation.
- Added guardrail check for grid acquisition with strict-block mode support.
- Added automatic tiled OV fallback in manual OV refresh path when single-frame
  grab fails.

Issues/TODOs addressed:
- 004, 005, 011, 012
- Product TODO: OV Acquisition Reliability
- Product TODO: Motion Sanity Checks
- Product TODO: Acquisition Parameter Guardrails

### Change set B - spatial provenance and registration

Files:
- `src/Grid.py`
- `src/Tile.py`
- `src/Overview.py`
- `src/GridManager.py`
- `src/OverviewManager.py`
- `src/Acquisition.py`

Implemented:
- Added acquired/locked/result/timestamp provenance state for grids and OVs.
- Persisted provenance state in config load/save paths.
- Persisted acquired stage coordinates for tiles.
- Registration export now prefers acquired coordinates when available.
- Fixed tile registration origin calculation bug:
  `tile_position_for_registration` now uses tile width/height instead of grid
  width/height.

Issues/TODOs addressed:
- 007, 009, 012
- Product TODO: OV/Grid Registration Reliability
- Product TODO: Spatial Provenance Locking

### Change set C - viewport UX improvements

Files:
- `src/dialog/viewport/OVQueueDlg.py` (new)
- `src/Viewport.py`

Implemented:
- Added modeless OV queue panel with one-click actions:
  activate/deactivate, acquire selected OV, clear OV image, delete last OV.
- Added context-menu actions for OV queue, OV acquire, OV clear, and OV/grid
  lock/unlock.
- Added direct OV settings open command (`OPEN OV SETTINGS` signal path).
- Added double-click behavior:
  selected grid/OV opens settings; fallback remains zoom.
- Added lock enforcement:
  acquired/locked OVs and grids cannot be dragged until explicitly unlocked.
- Inactive OVs now render visible footprint rectangles (not label-only).
- Added selected-object highlight/inspector overlay.
- Added live grid drag preview text (rows x cols tile growth) and footprint
  preview rectangle.
- Added adaptive stage crosshair scaling by viewport zoom.
- Added render diagnostics toggles (overlay antialias + diagnostics text).
- Added quick geometry registration check action for selected tile/OV context.

Issues/TODOs addressed:
- 003, 006, 008, 009, 010
- Product TODO: OV Workflow UX
- Product TODO: Grid Placement UX
- Product TODO: Direct Viewport Selection & Editing
- Product TODO: Viewport Rendering Stability
- Product TODO: Adaptive Crosshair UX

### Change set D - new project workflow

Files:
- `src/MainControls.py`

Implemented:
- Added `New Project...` action (Configuration menu + dedicated toolbar button).
- Added guided workflow:
  choose new config file, choose base dir, writable-path validation,
  optional OV0/Grid0 reinitialization, dry-run preview confirmation.
- Workflow applies:
  reset counters/interruption state, clear OV/stub/tile previews/imported
  overlays, update selectors, redraw viewport, save config.
- Added `OPEN OV SETTINGS` signal handling in Main Controls.

Issues/TODOs addressed:
- 002
- Product TODO: New Project Flow

### Config defaults updated

Files:
- `src/default_cfg/default.ini`
- `src/config_template.py`

Added defaults for:
- acquisition guardrails (`guardrail_min_mag`, `guardrail_max_mag`,
  `guardrail_strict`)
- OV fallback and defaults (`auto_tile_ov_fallback`,
  `ov_single_frame_min_mag`, `new_ov_default_active`)
- persisted provenance arrays for grids/OVs
- viewport render diagnostics toggles (`render_debug`, `render_antialias`)

Template metadata:
- `CFG_NUMBER_KEYS` updated from `231` to `249`.

### Verification

Commands run:
- `python -m compileall src`
- `PYTHONPATH=src python -c "import Acquisition, Viewport, MainControls, acq_func, acq_guardrails; print('import-ok')"`

Result:
- Compile/import smoke checks passed in the current environment.
