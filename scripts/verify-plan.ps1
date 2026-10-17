param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$artifactRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$checkFailures = [System.Collections.Generic.List[string]]::new()
$checkCount = 0

function Test-Condition {
    param([bool]$Condition, [string]$Message)
    $script:checkCount += 1
    if (-not $Condition) { $script:checkFailures.Add($Message) }
}

$requiredFiles = @(
    'README.md', 'PLAN.md', 'NEXT_STEPS.md', 'docs/architecture.md', 'docs/simulation.md',
    'docs/policies-and-evidence.md', 'docs/data-plan.md',
    'docs/experiments-and-validation.md', 'docs/delivery.md',
    'docs/architecture-decision.md', 'docs/integration.md', 'planning/sources.json',
    'planning/context-snapshot.json', 'planning/scenarios.json',
    'planning/decisions.tsv', 'planning/review.md'
)
foreach ($relativeFile in $requiredFiles) {
    Test-Condition (Test-Path -LiteralPath (Join-Path $artifactRoot $relativeFile) -PathType Leaf) "Missing $relativeFile"
}
if ($checkFailures.Count -gt 0) { throw ($checkFailures -join [Environment]::NewLine) }

$sourceRegister = Get-Content -LiteralPath (Join-Path $artifactRoot 'planning/sources.json') -Raw | ConvertFrom-Json
$contextData = Get-Content -LiteralPath (Join-Path $artifactRoot 'planning/context-snapshot.json') -Raw | ConvertFrom-Json
$scenarioCatalog = Get-Content -LiteralPath (Join-Path $artifactRoot 'planning/scenarios.json') -Raw | ConvertFrom-Json
$cutoffDate = [datetime]::ParseExact($sourceRegister.cutoff, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture)
$sourceIds = @($sourceRegister.sources | ForEach-Object { $_.id })
Test-Condition (($sourceIds | Sort-Object -Unique).Count -eq $sourceIds.Count) 'Duplicate source IDs'
Test-Condition ($contextData.cutoff -eq $sourceRegister.cutoff) 'Context cutoff differs'
Test-Condition ($scenarioCatalog.cutoff -eq $sourceRegister.cutoff) 'Scenario cutoff differs'

foreach ($sourceRecord in $sourceRegister.sources) {
    $parsedUri = $null
    $validUri = [uri]::TryCreate($sourceRecord.url, [UriKind]::Absolute, [ref]$parsedUri)
    Test-Condition ($validUri -and $parsedUri.Scheme -eq 'https') "Invalid source URL: $($sourceRecord.id)"
    Test-Condition (-not [string]::IsNullOrWhiteSpace($sourceRecord.supports)) "Source lacks supported claim: $($sourceRecord.id)"
    if ($null -ne $sourceRecord.published_at) {
        $publishedDate = [datetime]::ParseExact($sourceRecord.published_at, 'yyyy-MM-dd', [cultureinfo]::InvariantCulture)
        Test-Condition ($publishedDate -le $cutoffDate) "Post-cutoff source: $($sourceRecord.id)"
    }
    Test-Condition ($sourceRecord.checked_on -eq $sourceRegister.cutoff) "Unchecked source date: $($sourceRecord.id)"
}

foreach ($contextValue in $contextData.values) {
    Test-Condition ($sourceIds -contains $contextValue.source_id) "Unknown context source: $($contextValue.id)"
    Test-Condition (-not [string]::IsNullOrWhiteSpace($contextValue.unit)) "Missing unit: $($contextValue.id)"
    Test-Condition (-not [string]::IsNullOrWhiteSpace($contextValue.geography)) "Missing geography: $($contextValue.id)"
    Test-Condition (-not [string]::IsNullOrWhiteSpace($contextValue.reference_period)) "Missing reference period: $($contextValue.id)"
    Test-Condition (-not [string]::IsNullOrWhiteSpace($contextValue.restriction)) "Missing limitation: $($contextValue.id)"
    Test-Condition ($contextValue.eligible_for_calibration -eq $false) "Planning observation incorrectly marked calibrated: $($contextValue.id)"
    if ($null -ne $contextValue.released_on) {
        Test-Condition ([datetime]$contextValue.released_on -le $cutoffDate) "Post-cutoff observation: $($contextValue.id)"
    }
}

$solutionIds = @($scenarioCatalog.solutions | ForEach-Object { $_.id })
Test-Condition ($scenarioCatalog.schema_version -eq 2) 'Expected current scope catalog schema'
Test-Condition ($scenarioCatalog.kind -eq 'planning_catalog_not_executable') 'Catalog must not claim to be executable'
Test-Condition (($solutionIds | Sort-Object) -join ',' -eq 'groceries,processing,school') 'Core solution coverage differs'
foreach ($solutionRecord in $scenarioCatalog.solutions) {
    foreach ($referenceId in $solutionRecord.source_ids) {
        Test-Condition ($sourceIds -contains $referenceId) "Unknown policy source: $referenceId"
    }
    Test-Condition ($solutionRecord.depends_on.Count -gt 0) "No rollout dependencies: $($solutionRecord.id)"
}
$enablerIds = @($scenarioCatalog.delivery_enablers | ForEach-Object { $_.id })
Test-Condition (($enablerIds -join ',') -eq 'drone_delivery') 'Delivery enabler classification differs'
foreach ($enablerRecord in $scenarioCatalog.delivery_enablers) {
    foreach ($referenceId in $enablerRecord.source_ids) {
        Test-Condition ($sourceIds -contains $referenceId) "Unknown delivery-enabler source: $referenceId"
    }
}
foreach ($scenarioRecord in $scenarioCatalog.scenarios) {
    foreach ($enabledSolution in $scenarioRecord.enabled_solutions) {
        Test-Condition ($solutionIds -contains $enabledSolution) "Unknown scenario solution: $enabledSolution"
    }
    foreach ($enabledEnabler in $scenarioRecord.enabled_enablers) {
        Test-Condition ($enablerIds -contains $enabledEnabler) "Unknown scenario enabler: $enabledEnabler"
    }
}
$baselineScenario = $scenarioCatalog.scenarios | Where-Object id -eq 'baseline'
Test-Condition ($baselineScenario.mode -eq 'observed_service_with_explicit_unknowns') 'Legacy economic baseline contract changed'
Test-Condition (@($baselineScenario.enabled).Count -eq 0) 'Baseline fixture must keep its empty legacy enabled list'
$legacyGroceryScenario = $scenarioCatalog.scenarios | Where-Object id -eq 'groceries_only'
Test-Condition ($legacyGroceryScenario.mode -eq 'hypothetical_policy') 'Legacy grocery fixture alias changed'
Test-Condition ($legacyGroceryScenario.status -eq 'legacy_fixture_alias') 'Legacy grocery alias must be labeled'
$scope = $scenarioCatalog.product_scope
Test-Condition ($scope.primary_environment -eq 'toronto_3d') 'Toronto 3D must be the primary environment'
Test-Condition ($scope.primary_agents -eq 'resident_pedestrians') 'Resident pedestrians must be the primary agents'
Test-Condition ($scope.school_day_is_product_frame -eq $false) 'School day must not define the product frame'
Test-Condition ($scope.active_simulation_extent -eq 'selected_areas') 'Active simulation extent must be explicit'
$schoolSolution = $scenarioCatalog.solutions | Where-Object id -eq 'school'
Test-Condition ($schoolSolution.service_definition -eq 'open') 'Unlimited-lunch service definition must remain open'
$droneScenario = $scenarioCatalog.scenarios | Where-Object id -eq 'drone_delivery_comparison'
Test-Condition ($droneScenario.mode -eq 'hypothetical_route_with_no_approval_branch') 'Drone scenario needs hypothetical status and no-approval branch'
Test-Condition ($scenarioCatalog.agent_modeling.pedestrian_call_limits -eq 'to_be_set_after_active_area_and_decision_frequency_are_measured') 'Pedestrian model-call limits must remain unpriced until measured'
$legacy = $scenarioCatalog.legacy_prototype
Test-Condition ($legacy.status -eq 'existing_economic_vertical_slice') 'Existing prototype must be identified as a legacy economic slice'
Test-Condition ($legacy.old_screening_design.status -eq 'superseded') 'Old factorial screen must be marked superseded'
Test-Condition ($legacy.old_budget_status -eq 'superseded') 'Old budget must be marked superseded'

$markdownFiles = @((Get-Item -LiteralPath (Join-Path $artifactRoot 'README.md')), (Get-Item -LiteralPath (Join-Path $artifactRoot 'PLAN.md')), (Get-Item -LiteralPath (Join-Path $artifactRoot 'NEXT_STEPS.md')))
$markdownFiles += @(Get-ChildItem -LiteralPath (Join-Path $artifactRoot 'docs') -Filter '*.md' -File)
$markdownFiles += @(Get-ChildItem -LiteralPath (Join-Path $artifactRoot 'planning') -Filter '*.md' -File)
$totalWords = 0
foreach ($markdownFile in $markdownFiles) {
    $markdownText = [System.IO.File]::ReadAllText($markdownFile.FullName)
    $totalWords += [regex]::Matches($markdownText, '\S+').Count
    Test-Condition ($markdownText.StartsWith('# ')) "Missing document title: $($markdownFile.Name)"
    Test-Condition (-not [regex]::IsMatch($markdownText, '(?m)[ \t]+$')) "Trailing whitespace: $($markdownFile.Name)"
    foreach ($linkMatch in [regex]::Matches($markdownText, '\[[^\]]+\]\(([^)\s]+)\)')) {
        $linkTarget = $linkMatch.Groups[1].Value
        if ($linkTarget -match '^(https?://|mailto:|#)') { continue }
        $localTarget = [uri]::UnescapeDataString(($linkTarget -split '#', 2)[0])
        $resolvedLink = [System.IO.Path]::GetFullPath((Join-Path $markdownFile.DirectoryName $localTarget))
        Test-Condition ($resolvedLink.StartsWith($artifactRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) "Link leaves package: $linkTarget"
        Test-Condition (Test-Path -LiteralPath $resolvedLink) "Broken local link in $($markdownFile.Name): $linkTarget"
    }
}

$trail = @(Get-Content -LiteralPath (Join-Path $artifactRoot 'planning/decisions.tsv'))
Test-Condition ($trail[0] -eq "ts`tphase`tdecision`twhy`tevidence`tresult") 'Decision log header mismatch'
foreach ($trailRow in ($trail | Select-Object -Skip 1)) {
    $trailCells = $trailRow -split "`t"
    Test-Condition ($trailCells.Count -eq 6) 'Decision row must have six cells'
    if ($trailCells.Count -eq 6) {
        Test-Condition (Test-Path -LiteralPath (Join-Path $artifactRoot $trailCells[4])) "Unresolved decision evidence: $($trailCells[4])"
    }
}

if ($checkFailures.Count -gt 0) {
    $checkFailures | ForEach-Object { Write-Output "FAIL: $_" }
    exit 1
}
Write-Output "PASS: $checkCount planning-package checks"
Write-Output "Documents: $($markdownFiles.Count); approximate words: $totalWords; sources: $($sourceIds.Count); context values: $($contextData.values.Count)"
Write-Output 'Scope: local links, manifest integrity, evidence metadata, solution and enabler coverage, product scope, legacy supersession, and decision pointers.'
Write-Output 'Not checked: remote URL liveness, actual dataset ingestion, simulator behavior, benchmark performance, calibration, or real policy outcomes.'
