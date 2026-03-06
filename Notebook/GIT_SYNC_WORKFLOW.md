# SBEMimage Git Sync Workflow (Fork + Upstream)

This workflow keeps your customizations isolated while still allowing regular updates from the original SBEMimage project.

## 1) One-time repository setup

### Current roles
- `upstream`: original project (`SBEMimage/SBEMimage`)
- `origin`: your fork (`fredericoaraujopt/SBEMimage`)

### Commands
```bash
git remote rename origin upstream
git remote add origin https://github.com/fredericoaraujopt/SBEMimage.git
git fetch --all --prune
```

## 2) Branching model

- `master`: mirror of upstream default branch
- `feature/<name>`: active customization branches
- `integrate/upstream-YYYY-MM-DD`: temporary integration branch for upstream merge validation

Do not develop directly on `master`.

## 3) First push of local custom work

From your active customization branch:

```bash
git add -A
git commit -m "WIP: local SBEMimage customizations"
git push -u origin feature/guideline-compliance
```

Also push a clean `master` mirror:

```bash
git switch master
git merge --ff-only upstream/master
git push -u origin master
```

## 4) Routine upstream sync (safe pattern)

Recommended command (from repository root):

```powershell
.\Notebook\sync-upstream.ps1 -FeatureBranch feature/guideline-compliance
```

What this script does:
- Verifies `origin` and `upstream` remotes exist.
- Syncs `master` from `upstream/master` with fast-forward only.
- Pushes `master` to your fork (`origin/master`).
- Creates `integrate/upstream-YYYY-MM-DD` from your feature branch.
- Merges `master` into that integration branch.

Useful flags:
- `-SkipIntegrationBranch`: sync/push only `master`.
- `-AllowDirty`: only with `-SkipIntegrationBranch`, allows master-only sync with a dirty working tree.
- `-MasterBranch <name>`: if your default branch is not `master`.
- `-IntegrationPrefix <prefix>`: customize integration branch naming.

Master-only sync example when you are mid-work and not ready to commit:

```powershell
.\Notebook\sync-upstream.ps1 -FeatureBranch feature/guideline-compliance -SkipIntegrationBranch -AllowDirty
```

### Manual fallback: Step A (update local mirror of upstream)
```bash
git fetch upstream
git switch master
git merge --ff-only upstream/master
git push origin master
```

### Manual fallback: Step B (integration checkpoint branch)
```bash
git switch feature/guideline-compliance
git switch -c integrate/upstream-YYYY-MM-DD
git merge master
```

- Resolve conflicts.
- Run tests and manual validation.

If valid:

```bash
git switch feature/guideline-compliance
git merge --no-ff integrate/upstream-YYYY-MM-DD
git push origin feature/guideline-compliance
```

If not valid:

```bash
git switch feature/guideline-compliance
git branch -D integrate/upstream-YYYY-MM-DD
```

## 5) Conflict and compatibility guidance

- Keep custom logic in focused files/modules when possible.
- Prefer additive hooks/wrappers over editing core upstream behavior.
- Use small, frequent upstream integrations instead of rare large merges.
- Keep integration commits separate from feature commits for easier rollback.

## 6) Optional long-term hardening

- Add CI on your fork for smoke tests.
- Maintain a changelog of local custom patches.
- Tag stable internal releases, for example: `custom-v2026.03.05`.

## 7) Recovery safety net

Before difficult merges:

```bash
git branch backup/feature-gc-YYYY-MM-DD feature/guideline-compliance
git push origin backup/feature-gc-YYYY-MM-DD
```

This gives you a guaranteed rollback point.
