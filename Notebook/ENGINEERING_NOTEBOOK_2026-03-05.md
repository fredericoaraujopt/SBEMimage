# SBEMimage Engineering Notebook - 2026-03-05

## Persistent Notebook Guidelines (Carry Forward)

These guidelines must be copied into every new notebook file so human contributors and LLM agents have consistent operating instructions.

1. Repository context must always be stated first.
   - SBEMimage is a Python + PyQt desktop application for SEM/SBEM acquisition control.
   - Main entrypoint: `src/sbemimage.py` (also launched by `SBEMimage.bat`).
   - Core high-impact modules: `src/Viewport.py`, `src/MainControls.py`, `src/Acquisition.py`.
   - Hardware adapters live in `src/sem/` and `src/microtome/`.
   - Config model: templates in `src/default_cfg/`, runtime configs in `cfg/`.
   - Acquaintance step: read `guidelines.md` in the repository root before making changes.

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

## Repository Context Snapshot (2026-03-05)

- Objective: rework SBEMimage for reliability and performance on large GEMINISEM acquisitions without interrupting current acquisition capability.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Rework constraint: prioritize stability and regression safety before further optimization/refactor.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `PROJECT_REWORK_PLAN.md` (Implementation Log 2026-03-02) and `ENGINEERING_NOTEBOOK_2026-03-04.md`.

### Implemented change groups

- [x] Acquisition reliability and diagnostics
  - Added `src/acq_guardrails.py`.
  - Added OV diagnostics and guardrail checks.
  - Added stage-arrival validation and motion sanity checks.
  - Added automatic tiled OV fallback for manual OV refresh path.

- [x] Spatial provenance and registration foundations
  - Added acquired/locked/timestamp state for grids and OVs.
  - Persisted provenance state through config load/save paths.
  - Registration export now prefers acquired coordinates when available.
  - Fixed tile registration origin calculation bug.

- [x] Viewport UX and interaction updates
  - Added OV queue panel (`src/dialog/viewport/OVQueueDlg.py`) with one-click actions.
  - Added direct OV/grid selection improvements and double-click settings open.
  - Added lock enforcement for acquired objects.
  - Added live grid drag preview and adaptive crosshair scaling.
  - Added render diagnostics toggles.

- [x] New Project workflow in Main Controls
  - Added `New Project...` action (menu + toolbar).
  - Added guided flow: new config, base dir validation, optional OV0/Grid0 reset, dry-run preview.
  - Added state reset and viewport cleanup during project initialization.

- [x] Config template/default updates
  - Added new keys for guardrails, OV fallback/default behavior, provenance persistence, and viewport render diagnostics.

### Latest validation state from 2026-03-04

- [x] Working in operator run: New Project flow, OV queue core flow, OV reliability checks, grid placement interaction, provenance locking, direct selection/editing.
- [ ] Unstable / failing: grid acquisition reliability and acquired-state integrity during failed/incomplete capture paths.
- [ ] Not yet completed: persistence verification checklist section (save/restart and verify new keys/state).



### Pending validation checklist (carry-forward)

- [ ] Save config and restart app.
- [ ] Verify guardrail keys persist: `guardrail_min_mag`, `guardrail_max_mag`, `guardrail_strict`.
- [ ] Verify OV fallback/default keys persist: `auto_tile_ov_fallback`, `ov_single_frame_min_mag`, `new_ov_default_active`.
- [ ] Verify viewport render keys persist: `render_debug`, `render_antialias`.
- [ ] Verify OV/grid lock + acquired provenance state persists.

## Session Change Log (2026-03-05)

Use this section to record work completed today.

- [x] Grid acquisition hotfix: fixed malformed grid-loop condition in `Acquisition.py` (`self.error_state == Error.none,` -> `self.error_state == Error.none`) that could allow acquisition logic to run in invalid states.
- [x] Grid acquisition hotfix: gated tile retry while-loop on `self.error_state == Error.none` and `self.pause_state != 1` so the stage does not continue moving when acquisition is already in an error/pause state.
- [x] Grid acquisition hotfix: motion sanity check now skips very large expected shifts (`expected_shift_px > 0.75 * min image dimension`) where phase-correlation is unreliable, preventing false `Error.stage_xy` pauses.
- [x] Viewport control update: `Acquire Grid` from right-click now runs asynchronously (threaded), so the viewport remains responsive during manual grid acquisition.
- [x] Viewport control update: added right-click action `Pause acquisition...` on grids; this routes to the Main Controls pause flow (`Pause now` / `Pause after slice`).
- [x] Pause consistency update: for viewport manual grid runs, `Pause after slice` is mapped to immediate pause (tile-boundary) to match single-grid semantics.
- [x] UI experiment: added global teal/card theme stylesheet (`gui/teal_experiment.qss`) with updated font stack and controls palette inspired by the reference interface.
- [x] UI experiment wiring: app startup now loads the teal theme by default via `[sys] use_teal_experiment_gui = True` (can be disabled per session config).
- [x] UI experiment refinement: rebuilt the theme to avoid text clipping by keeping native font-size/layout metrics (no global size overrides), while preserving the teal/card palette direction.
- [x] UI experiment toggle: setting `[sys] use_teal_experiment_gui = False` now cleanly bypasses the experimental stylesheet and restores native rendering.
- [x] UI experiment density tuning: introduced `teal_experiment_font_pt` (clamped 8-11, default 9) and reduced widget padding in the experimental theme to reduce oversized text and crowded control rendering.
- [x] KLAB UI branding/toggle update: startup Config dialog now includes `Use KLAB UI (experimental)` selector so users can choose native vs stylized UI at launch.
- [x] KLAB readability/spacing fixes: dark-surface text forced to white; compact `QToolButton` style fixed hidden `...` toggles and row crowding in Stack acquisition options.
- [x] KLAB overflow fix: `Last confirmed stage position` label in Main Controls (`Microtome/Stage`) now wraps and has adjusted geometry to prevent clipping.
- [x] KLAB typography fit pass: reduced in-panel text sizing for Main Controls content (`mainControls` group boxes) to prevent clipping in fixed-size control rows.
- [x] KLAB dropdown affordance pass: restyled `QComboBox` with a dedicated right-side dropdown section and explicit down-arrow marker so dropdowns are clearly distinct from toggle/tool buttons.
- [x] KLAB dropdown icon refinement: replaced filled triangle marker with a downward chevron icon (native-like `>` rotated down), loaded via absolute `file:///` URL at runtime to keep icon rendering stable across launch directories.
- [x] KLAB dropdown simplification: reverted custom icon injection and restored standard Qt/native dropdown arrow rendering for simpler, more familiar UI behavior.
- [x] KLAB panel readability tuning: increased Main Controls in-panel text from `10px` to `11px` after operator feedback that `10px` was too small.
- [x] KLAB geometry tuning: added KLAB-only Main Controls width expansion (`klab_main_controls_extra_width`, default `48px`) applied at runtime, so native UI layout remains unchanged.
- [x] KLAB panel distribution fix: Main Controls top-row columns are now assigned equal stretch factors in KLAB mode so additional width is shared evenly across SEM/Overviews/Tile grids/Manual commands panels.
- [x] KLAB dropdown indicator fix: added a simple downward triangle marker to `QComboBox::down-arrow` via QSS borders (no custom icon assets), improving dropdown recognizability.
- [x] KLAB stack panel spacing pass: widened checkbox text lanes and re-aligned `...` toolbuttons in Stack acquisition options so labels like `E-mail monitoring` and related options fit.
- [x] KLAB Tile grids selector sizing: grid/overview selector combo boxes now expand to available panel width with right-docked settings buttons, preventing clipped entries like `Grid 0`.
- [x] KLAB manual commands alignment: manual command buttons are now horizontally centered within their panel.
- [x] KLAB viewport control spacing: `Show stage position` checkbox was widened and FOV controls shifted to avoid clipping in the Viewport control bar.
- [x] KLAB dropdown native-style pass: removed custom down-arrow drawing; dropdown arrows now rely on the standard Qt/native indicator with a subtle drop-down section styling.
- [x] KLAB dropdown rollback-to-native pass: removed KLAB-specific `QComboBox::drop-down` overrides to restore standard Qt/native dropdown rendering and avoid selector/settings-button visual collisions.
- [x] KLAB main-controls selector safety pass: selector/button geometry logic now guarantees a fixed inter-widget gap and prevents overlap even when panel widths are constrained.
- [x] KLAB viewport controls strategy pass: viewport bottom control frames now use dynamic width allocation for selectors/labels/buttons so entries like `All grids` and `Show stage position` remain readable at larger UI font sizes.
- [x] KLAB context-menu UX parity: disabled right-click menu actions now render with reduced contrast (`QMenu::item:disabled`) to match native discoverability cues.
- [x] KLAB stack-left spacing increment: moved stack divider slightly right when width allows and expanded left option lanes (`E-mail monitoring`, etc.) for additional readability.
- [x] KLAB Tile-grid selector increment: reduced selector icon-label padding (`'   '` -> `' '`) in KLAB mode and tightened selector/button docking margins to give `Grid n` more visible text room.
- [x] KLAB dropdown style refresh: adopted a modernized combo-field style (hover/focus/border refinements) while keeping native arrow rendering to avoid old-fashioned look and prior custom-arrow artifacts.
- [x] KLAB stack-left spacing increment (2): increased left option-lane width further (`min 142px`) and pushed left `...` buttons rightward to fully display labels such as `E-mail monitoring`.
- [x] KLAB Tile-grid selector increment (2): further tightened selector/button margins, reduced settings-button width, and reduced grid color-icon footprint (`14x8`) to maximize visible `Grid n` text.
- [x] KLAB dropdown cue increment: added a tiny down-triangle marker via QSS (`QComboBox::down-arrow`) sized to fit compact combo-box heights.
- [x] Global UI change (native + KLAB): removed the top toolbar row containing the `Create New Project...` icon action from Main Controls.
- [x] KLAB stack panel re-balance: shifted stack divider to allocate more width to both left-side option columns (including disk/image monitoring) and reflowed right-side acquisition info widgets into a narrower footprint.
- [x] KLAB dropdown-square fix: replaced border-drawn pseudo-triangle with a tiny SVG down-arrow asset (`gui/klab_dropdown_arrow_down.svg`) to avoid square rendering artifacts.
- [x] KLAB stack panel balance pass (3): updated divider sizing to preserve a larger right info area (dynamic target ~39% with min 285px) while still expanding left options; reduced left-column text-to-`...` spacing to eliminate overlap with right-column checkbox indicators.
- [x] KLAB stack panel balance pass (4): fixed divider at a modest right shift (`x=350`) and restored native-like right-side spacing by applying native X/width geometry offsets relative to divider shift.
- [x] KLAB stack options alignment pass: unified text-to-`...` spacing rule across left and right columns (`-4px` gap basis), matching right-column spacing behavior and preventing cross-column overlap.
- [x] KLAB stack options spacing pass (5): increased right-column text-to-`...` gap to a native-like wider separation (`16px`) and adjusted right-column `...` placement to prevent label crowding (`Disk mirroring`, `Image monitoring`, etc.).
- [x] KLAB stack options spacing pass (6): constrained left-column `...` button X by right-column text origin with an explicit inter-column safety gap (`16px`) so left `...` controls cannot collide with right-column labels.
- [x] KLAB startup animation: added a lightweight, non-blocking animated label in the configuration dialog (next to the `KLAB style` checkbox) that runs only when KLAB is enabled and stops immediately when disabled.

## Verification Guide - Grid Stops After Stage Move

Use this quick check to validate the hotfix in a real run:

1. In Main Controls, reset grid acquisition/skip state for the affected grid.
2. Start acquisition on the grid that previously stopped after 1-2 tiles.
3. Confirm logs continue with repeated `SEM: Acquiring tile at ...` entries after each stage move.
4. Confirm there is no immediate stop with `Motion sanity check failed` on large row/column transitions.
5. If a real hardware/image error occurs (`grab incomplete`, `frozen frame`, XY move error), confirm the stack pauses normally and does not silently continue.
6. After completion or pause, verify newly acquired tiles were saved and only successfully acquired tiles are marked acquired.

Expected result:
- Normal tile progression should continue beyond previously failing transitions.
- Stage motion should not occur without a subsequent image acquisition when acquisition is already paused/error-state.

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
