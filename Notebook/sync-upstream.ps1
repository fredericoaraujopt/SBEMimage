param(
    [string]$MasterBranch = "master",
    [string]$FeatureBranch = "",
    [string]$IntegrationPrefix = "integrate/upstream",
    [switch]$SkipIntegrationBranch,
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host ">> git $($Arguments -join ' ')"
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Arguments -join ' ')"
    }
}

function Get-TrimmedGitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($Arguments -join ' ')"
    }
    return ($output | Out-String).Trim()
}

function Test-BranchExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BranchName
    )

    & git show-ref --verify --quiet "refs/heads/$BranchName"
    $existsLocal = ($LASTEXITCODE -eq 0)

    & git show-ref --verify --quiet "refs/remotes/origin/$BranchName"
    $existsRemote = ($LASTEXITCODE -eq 0)

    return ($existsLocal -or $existsRemote)
}

# Run from repo root regardless of the caller's current directory.
$repoRoot = Get-TrimmedGitOutput -Arguments @("rev-parse", "--show-toplevel")
Set-Location $repoRoot

# Safety check:
# - Integration mode always requires a clean working tree.
# - Master-only sync can run dirty only with -AllowDirty.
$dirtyState = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Could not read git status."
}
$hasDirtyState = -not [string]::IsNullOrWhiteSpace(($dirtyState | Out-String))
if ($hasDirtyState) {
    if (-not $SkipIntegrationBranch) {
        throw "Working tree is not clean. Integration mode requires commit/stash first."
    }
    if (-not $AllowDirty) {
        throw "Working tree is not clean. Commit/stash changes first, or rerun with -AllowDirty."
    }
}

$remotes = (& git remote)
if ($LASTEXITCODE -ne 0) {
    throw "Could not read git remotes."
}
if ($remotes -notcontains "origin") {
    throw "Remote 'origin' is missing."
}
if ($remotes -notcontains "upstream") {
    throw "Remote 'upstream' is missing."
}

if ([string]::IsNullOrWhiteSpace($FeatureBranch)) {
    $FeatureBranch = Get-TrimmedGitOutput -Arguments @("branch", "--show-current")
}
if ([string]::IsNullOrWhiteSpace($FeatureBranch)) {
    throw "Could not determine current branch. Provide -FeatureBranch explicitly."
}
if ($FeatureBranch -eq $MasterBranch -and -not $SkipIntegrationBranch) {
    throw "Feature branch resolves to '$MasterBranch'. Use -FeatureBranch to set a customization branch."
}

Write-Host "Syncing '$MasterBranch' from upstream and pushing to origin..."
Invoke-Git -Arguments @("fetch", "upstream")
$currentBranch = Get-TrimmedGitOutput -Arguments @("branch", "--show-current")
if ($currentBranch -eq $MasterBranch) {
    Invoke-Git -Arguments @("merge", "--ff-only", "upstream/$MasterBranch")
}
else {
    Invoke-Git -Arguments @("fetch", "upstream", "$MasterBranch`:$MasterBranch")
}
Invoke-Git -Arguments @("push", "origin", $MasterBranch)

if ($SkipIntegrationBranch) {
    Write-Host "Done. Master sync complete."
    exit 0
}

Write-Host "Creating integration branch for '$FeatureBranch'..."
Invoke-Git -Arguments @("switch", $FeatureBranch)

$dateSuffix = Get-Date -Format "yyyy-MM-dd"
$baseIntegrationBranch = "$IntegrationPrefix-$dateSuffix"
$integrationBranch = $baseIntegrationBranch
$counter = 1

while (Test-BranchExists -BranchName $integrationBranch) {
    $integrationBranch = "$baseIntegrationBranch-$counter"
    $counter++
}

Invoke-Git -Arguments @("switch", "-c", $integrationBranch)
Invoke-Git -Arguments @("merge", $MasterBranch)

Write-Host ""
Write-Host "Integration branch ready: $integrationBranch"
Write-Host "Next: resolve conflicts (if any), run tests, then merge back into ${FeatureBranch}:"
Write-Host "  git switch $FeatureBranch"
Write-Host "  git merge --no-ff $integrationBranch"
Write-Host "  git push origin $FeatureBranch"
