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
    'README.md', 'PLAN.md', 'docs/architecture.md', 'docs/simulation.md',
    'docs/policies-and-evidence.md', 'docs/data-plan.md',
    'docs/experiments-and-validation.md', 'docs/delivery.md',
    'docs/architecture-decision.md', 'planning/sources.json',
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

$policyIds = @($scenarioCatalog.interventions | ForEach-Object { $_.id })
Test-Condition (($policyIds | Sort-Object) -join ',' -eq 'drones,groceries,processing,school') 'Required policy coverage differs'
foreach ($policyRecord in $scenarioCatalog.interventions) {
    foreach ($referenceId in $policyRecord.source_ids) {
        Test-Condition ($sourceIds -contains $referenceId) "Unknown policy source: $referenceId"
    }
    Test-Condition ($policyRecord.depends_on.Count -gt 0) "No rollout dependencies: $($policyRecord.id)"
}
foreach ($scenarioRecord in $scenarioCatalog.scenarios) {
    foreach ($enabledPolicy in $scenarioRecord.enabled) {
        Test-Condition ($policyIds -contains $enabledPolicy) "Unknown scenario policy: $enabledPolicy"
    }
}
$droneScenario = $scenarioCatalog.scenarios | Where-Object id -eq 'drones_only'
Test-Condition ($droneScenario.mode -eq 'hypothetical_route_with_no_approval_branch') 'Drone scenario needs hypothetical status and no-approval branch'
$screening = $scenarioCatalog.screening
Test-Condition ($screening.cells -eq [math]::Pow(2, $screening.binary_switches)) 'Factorial cell count mismatch'
Test-Condition ($screening.total_runs -eq $screening.cells * $screening.paired_seed_blocks) 'Experiment run count mismatch'

$limits = $scenarioCatalog.llm_limits
Test-Condition ($limits.max_attempts -eq $limits.focal_households * $limits.days * $limits.choices_per_household_day) 'LLM attempt arithmetic mismatch'
Test-Condition ($limits.max_input_tokens -eq $limits.max_attempts * $limits.max_input_tokens_per_attempt) 'Input token arithmetic mismatch'
Test-Condition ($limits.max_output_tokens -eq $limits.max_attempts * $limits.max_output_tokens_per_attempt) 'Output token arithmetic mismatch'
Test-Condition ($limits.automatic_retries -eq 0) 'Automatic retries violate chosen dispatch contract'
Test-Condition ($limits.max_live_requests_per_barrier -le $limits.concurrency) 'Barrier subset exceeds concurrent slots'
Test-Condition ($limits.deadline_scope -eq 'entire_decision_barrier') 'Deadline scope differs from the selected contract'
Test-Condition ($limits.barrier_selection -eq 'predeclared_stratified_schedule') 'Live barrier subset must be predeclared'
Test-Condition ($limits.run_budget_cad -eq 30) 'Run ceiling differs from documented default'

$budget = $scenarioCatalog.budget
$calculatedLabor = 0
foreach ($roleRecord in $budget.roles) { $calculatedLabor += $roleRecord.hours * $roleRecord.rate_cad }
Test-Condition ($budget.labor_cad -eq $calculatedLabor) 'Labor arithmetic mismatch'
Test-Condition ($budget.contingency_cad -eq $calculatedLabor * $budget.contingency_fraction) 'Contingency arithmetic mismatch'
Test-Condition ($budget.labor_with_contingency_cad -eq $calculatedLabor + $budget.contingency_cad) 'Contingency total mismatch'
Test-Condition ($budget.operating_allowance_cad -eq ($budget.hosting_monthly_cad + $budget.llm_monthly_cad) * $budget.allowance_months) 'Operating allowance mismatch'
Test-Condition ($budget.total_example_cad -eq $budget.labor_with_contingency_cad + $budget.operating_allowance_cad) 'Total budget mismatch'
Test-Condition ($budget.rates_are_hypothetical -eq $true) 'Budget must identify hypothetical rates'

$markdownFiles = @((Get-Item -LiteralPath (Join-Path $artifactRoot 'README.md')), (Get-Item -LiteralPath (Join-Path $artifactRoot 'PLAN.md')))
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
Write-Output 'Scope: local links, manifest integrity, evidence metadata, scenario coverage, token limits, budget arithmetic, and decision pointers.'
Write-Output 'Not checked: remote URL liveness, actual dataset ingestion, simulator behavior, benchmark performance, calibration, or real policy outcomes.'
