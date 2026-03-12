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
- [ ] Create a dedicated integration branch from the checkpoint commit before merging `upstream/dev`.
- [ ] Review upstream `dev` commits in topical batches and annotate expected conflict points.
- [ ] Merge `upstream/dev` on the integration branch only after the pre-merge review is complete.
- [ ] Run targeted automated and manual validation before accepting the integration branch.

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

## Verification Guide - Upstream Dev Integration Preparation

Use this checklist before starting the actual `upstream/dev` merge.

1. [ ] Confirm the checkpoint commit exists on `feature/guideline-compliance`.
2. [ ] Create a backup branch or tag from the checkpoint commit.
3. [ ] Create `integrate/upstream-dev-2026-03-12` from the checkpoint commit.
4. [ ] Review `git log --reverse --oneline 2601d52..upstream/dev` and group commits into AFSS, metadata/OME, and schema/device batches.
5. [ ] Review the hotspot files listed above and note expected local-vs-upstream conflict intent for each file.
6. [ ] Merge `upstream/dev` into the integration branch.
7. [ ] Resolve config and constants conflicts before UI files so the runtime schema is consistent early.
8. [ ] Run targeted tests and compile/import checks.
9. [ ] Launch SBEMimage and complete focused manual smoke tests on the changed workflows.
10. [ ] Merge the validated integration branch back into `feature/guideline-compliance` only if the result is stable.

Expected result:

- [ ] The repository has a reversible checkpoint before any upstream merge work.
- [ ] The eventual `upstream/dev` merge happens on an isolated branch.
- [ ] Conflict resolution decisions are made deliberately per hotspot file instead of ad hoc during the merge.
- [ ] Upstream improvements are integrated without losing the local customization work.

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
