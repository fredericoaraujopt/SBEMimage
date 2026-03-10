# SBEMimage Engineering Notebook - 2026-03-09

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

## Repository Context Snapshot (2026-03-09)

- Objective: rework SBEMimage for reliability, operator safety, and large-ROI usability on GEMINISEM acquisitions without disrupting core acquisition behavior.
- Environment baseline: Conda `sbemimage_env` (Python 3.12).
- Launch baseline: `conda run -n sbemimage_env python src/sbemimage.py`.
- Rework constraint: prioritize stability, reversibility, and regression safety before deeper refactors.
- Current carry-forward focus: validate the new polygon ROI and large-ROI deferred-materialization flow before extending it further.

## Major Changes Implemented (Carry-Forward Summary)

Imported from `ENGINEERING_NOTEBOOK_2026-03-03.md`, `ENGINEERING_NOTEBOOK_2026-03-04.md`, `ENGINEERING_NOTEBOOK_2026-03-05.md`, and `ENGINEERING_NOTEBOOK_2026-03-06.md`.

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

### Latest known validation state (carry-forward)

- [x] Manual grid acquisition from viewport supports pause control without freezing the viewport.
- [x] KLAB and native UI modes are selectable at startup via configuration dialog.
- [x] Config persistence validation completed for guardrail keys, OV fallback/default keys, viewport render keys, and OV/grid provenance persistence.
- [x] Startup dialog validation completed: default fallback is unchecked, config-driven auto-check works, and the bird animation only runs when `klab gui` is enabled.
- [x] Polygon ROI baseline workflow is implemented and basic interaction/persistence wiring exists.
- [x] Large-ROI deferred workflow still needs real operator validation on wafer-scale ROIs before being considered stable.

## Current Task Checklist (Imported)

### Pending validation checklist (carry-forward)

- [x] Re-check the full large-ROI workflow end-to-end with a real wafer-scale polygon.
- [x] Confirm that oversized legacy polygon configs auto-defer correctly on startup and do not freeze the GUI.
- [x] Confirm that deferred large ROIs can still be selected, edited, and deleted without viewport errors.
- [x] Confirm that `Keep Deferred` versus `Materialize Grid` in Grid Settings behaves predictably and does not unexpectedly expand the ROI.
- [x] Confirm that acquisition estimates and Main Controls labels remain sensible for deferred polygon ROIs.
- [x] Decide whether the current large-ROI thresholds (`5,000` warning / `20,000` hard limit) feel right in practice or need adjustment.
- [x] If behavior is still unclear, document exact repro cases and logs before making further changes.

### File-Backed Checks (carry-forward references)

- [x] `Notebook/guidelines.md` exists and remains the developer-reference baseline for repository conventions.
- [x] Previous notebook carry-forward sections were reviewed before creating this file.
- [x] Reconfirm deferred polygon ROI persistence in a saved runtime config after the next live validation pass.

## Session Change Log (2026-03-09)

Use this section to record work completed today.

- [x] Created `ENGINEERING_NOTEBOOK_2026-03-09.md` using the established notebook layout and carry-forward structure.
- [x] Reviewed `Notebook/guidelines.md` and prior engineering notebooks from 2026-03-03 through 2026-03-06 before creating this entry.
- [x] Imported the active large-ROI follow-up checklist so today can continue from the deferred polygon ROI validation work without losing context.
- [x] Deferred polygon ROI move fix: `Alt`-drag now falls back to polygon-body hit-testing, so deferred ROIs can be repositioned directly from the polygon outline instead of requiring label-based selection.
- [x] Large deferred ROI UX fix: plain left-click on the interior of a large deferred polygon no longer selects it, so normal viewport drag keeps panning; selection for these ROIs now remains explicit via edge/handle, right-click, `Alt`-click/drag, or selector-based paths.
- [x] Deferred polygon edit fix: resizing or vertex-editing a deferred polygon ROI now updates its perimeter and estimated layout while keeping it deferred, instead of triggering immediate full grid materialization during the drag interaction.
- [x] Large deferred ROI move/draw fix: `Alt`-drag over the interior of a large deferred polygon no longer counts as a move hit target, so the normal `Alt`-drag grid-draw gesture works again unless the operator starts from an explicit polygon target.
- [x] Viewport selection-state hardening: stale selected grid/tile indices are now cleared before redraw, preventing crashes when a just-deleted grid is still referenced during the next viewport paint cycle.
- [x] Large rectangular grid guardrail: ordinary `Alt`-drag rectangular grid creation now uses the same 5k/20k thresholds as polygon ROI creation, offering `Create Deferred ROI` versus `Create Full Grid` at warning scale and blocking immediate full-grid creation above the hard limit.
- [x] Deferred ROI viewport visibility fix: deferred polygon overlays are now considered visible based on the real ROI bounding box instead of the placeholder `1 x 1` tile footprint, so polygon borders remain visible when zoomed in on an edge far from the placeholder tile origin.
- [x] Fixed-footprint grid UX change: changing tile size, pixel size, overlap, or row shift now preserves the stored grid footprint (`sw_sh`) for ordinary rectangular grids as well as polygon-backed grids, so sampling density changes without the ROI growing or drifting.
- [x] Polygon overlap-aware activation change: polygon-backed grids now activate tiles based on unique assigned coverage inside the polygon, so border tiles that only intersect already-overlapped polygon area are excluded from acquisition.
- [x] KLAB spinbox contrast tweak: up/down step controls in numeric entry fields now use dark button surfaces with high-contrast arrow glyphs, so increment/decrement toggles remain visible against the light cell background.
- [x] KLAB disabled-state pass: controls that cannot be selected now render with muted text, flatter backgrounds, and reduced emphasis across buttons, toggles, tabs, menu items, and entry widgets so unavailable actions read more like the native UI.
- [x] KLAB global metrics pass: reduced the theme’s size-affecting padding/radius defaults and added a KLAB-only widget polisher that compacts only overflowing controls at runtime, so clipped text is handled across windows and dialogs without changing native UI behavior or widening panels one by one.

## Verification Guide - Large ROI Deferred Workflow

Use this checklist before making further large-ROI code changes.

1. Launch SBEMimage with the config that contains the large polygon ROI.
2. Confirm startup remains responsive and the app does not attempt to materialize the full ROI into tens of thousands of tiles immediately.
3. Select the deferred polygon ROI and confirm it can still be highlighted, edited, or deleted without viewport errors.
4. [x] Open Grid Settings for the deferred ROI and confirm the save path offers `Keep Deferred` versus `Materialize Grid`.
5. Save the config, restart SBEMimage, and confirm the large ROI reloads in deferred form.
6. Check Main Controls and the viewport label text to confirm the reported estimated size/count values are understandable to the operator.
7. If any of the above behaves unexpectedly, record the exact config used, ROI size, expected tile count, error text, and repro steps in the issue section below.

## To Be Continued Today

- [x] Validate the large-ROI deferred flow on a real wafer-scale polygon before extending polygon ROI functionality further.
- [x] Decide whether the current guardrail thresholds are operationally sensible or need adjustment after real-use testing.
- [x] If the current implementation is confusing in practice, capture exact UX pain points before redesigning the workflow.

## New Issues Found Today

- Issue ID: 2026-03-09-01
- Title: Newly created grids default to inactive tiles
- Severity: Medium
- Repro steps: Create a new rectangular grid from the viewport and inspect its tile activation state immediately after creation.
- Expected: New grids should default to all tiles active so the new ROI is immediately ready for acquisition unless the operator explicitly disables tiles.
- Actual: New grids are being created with tiles inactive by default, adding avoidable setup friction and increasing the chance of "nothing acquires" confusion.
- Logs: No dedicated error log expected; this is a workflow/default-state defect.
- Notes: Operator request is explicit that default behavior should be active tiles, not inactive tiles.

- Issue ID: 2026-03-09-02
- Title: Overview settings dialog always opens on Overview 0 instead of the currently selected overview
- Severity: Medium
- Repro steps: In the Overviews panel, select any overview other than Overview 0, then click the settings toggle/button to open the overview setup dialog.
- Expected: The overview setup dialog should open focused on the overview currently selected in the Overviews panel, matching the behavior already used in the grids panel.
- Actual: The dialog always defaults to Overview 0 regardless of the current overview selection.
- Logs: No dedicated error log expected; this is a UI state/selection propagation defect.
- Notes: This creates inconsistency between grid and overview workflows and slows down repeated overview edits.

- Issue ID: 2026-03-09-03
- Title: Grid outlines are always visible and obstruct image inspection
- Severity: Medium
- Repro steps: Zoom into an acquired region in the viewport and inspect sample features while grid overlays are present.
- Expected: Operators should be able to quickly hide and restore grid lines while inspecting image content, ideally with both a keyboard shortcut such as `H` and a visible UI toggle in the controls panel.
- Actual: Grid outlines remain always on, making close visual inspection of image content harder because the overlay blocks or distracts from the underlying feature of interest.
- Logs: No dedicated error log expected; this is a viewport UX issue.
- Notes: Requested implementation direction is a fast hide/show control plus a discoverable button in the controls UI.

- Issue ID: 2026-03-09-04
- Title: Right-click grid interactions are inconsistent between polygon grids and standard grids
- Severity: Medium
- Repro steps: Right-click a polygon-backed grid and compare the context menu and interaction affordances against a standard grid created with the regular `Alt`-drag workflow.
- Expected: Both polygon-backed grids and ordinary grids should be treated uniformly as grids for UI and acquisition purposes, including copy, paste, delete, settings access, and general right-click behavior.
- Actual: Polygon grids and standard grids currently expose different interaction capabilities, and common grid operations such as copy/paste/delete are not consistently available across both grid types.
- Logs: No dedicated error log expected; this is a UI/UX consistency issue.
- Notes: Most important requirement is parity: same right-click options, same settings affordances, same acquisition-pipeline treatment wherever possible.

- Issue ID: 2026-03-09-05
- Title: Feature alignment is inconsistent across imaging modalities and across separate grids
- Severity: High
- Repro steps: Image the same physical feature using different modality levels such as image stub, overview, and grid, or image the same feature using two separate grids, then compare the reported feature position between the resulting images.
- Expected: The same physical feature should register to the same location across image stub, overview, and grid acquisitions, and two separate grids imaging the same feature should agree on that feature location.
- Actual: Intra-modality alignment is acceptable, but alignment drifts between modalities, and separate grids can also disagree on the location of the same feature.
- Logs: No dedicated error log expected; this appears to be a registration/coordinate consistency defect rather than a surfaced runtime error.
- Notes: Operator report explicitly states that image stub-to-OV, OV-to-grid, and grid-to-grid agreement are all affected, so this should be treated as a broader cross-modality coordinate alignment problem rather than a single display-layer issue.

- Issue ID: 2026-03-09-06
- Title: KLAB GUI adaptive font shrinking hurts readability and exposes layout sizing problems
- Severity: Medium
- Repro steps: Use the KLAB GUI in panels where labels or values are longer than their available cell width and observe how the interface reduces font size to fit the content.
- Expected: UI text should remain readable with a practical minimum font size of 12, and the layout should expand cell widths or otherwise accommodate longer text so content remains visible without shrinking below that threshold.
- Actual: The UI is adaptively shrinking font size to fit tight cells, which improves fit in some places but makes the interface harder to read; where text still does not fit, parts of the content remain clipped or invisible.
- Logs: No dedicated error log expected; this is a GUI layout/readability defect.
- Notes: Requested direction is to preserve larger text in KLAB mode and solve overflow by adjusting control widths, cell sizing, or related layout constraints instead of relying on aggressive font-size reduction.

## Instruction Reminder

Any new notebook created after this one must include:
- the persistent guideline block,
- a carry-forward major changes section,
- and an imported checklist of current tasks.
