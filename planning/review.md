# Review record

## Architecture comparison

Two independent architecture candidates were read in full. A separate read-only judge scored both 10 of 10 against the five planning criteria and recommended Python authority for the research workflow. The parent independently selected the same base. Original candidate drafts remained in isolated session scratch directories, outside this repository.

The final design incorporates custody separate from ownership, second-level timing, complete replay, committed-boundary forks, fixed LLM panel selection, pupil-school assignments, and explicit rounding. The rationale is in [the architecture decision](../docs/architecture-decision.md).

## Final package review

A separate read-only reviewer read the actual README, main plan, seven specification documents, three JSON manifests, decision trail, and checker. It also spot-checked Council, Second Harvest, CPI, and Toronto CMA labor claims against primary sources.

The first review returned ISSUES:

1. The grocery formula could count spoiled inventory's acquisition cost twice and mixed procurement cash flow with operating expense.
2. The main schedule described a two-week demonstrator followed by 16 weeks, while the budget included it within 16 weeks.
3. The LLM deadline did not fully specify which requests received concurrent slots and how queue exclusions were recorded.

The parent corrected the money specification to separate cash funding and inventory-based operating results, recognized acquisition cost once, clarified the inclusive 16-week schedule, and defined a predeclared four-request barrier subset with distinct rule-selection reasons. The manifest and checker now verify the selected barrier contract.

The reviewer reread those revisions and reran the checker. Its second result was PASS, with all three findings resolved and 317 planning-package checks passing. No remaining consequential issues were identified in the revisions.

## Checker verification

The parent also ran the checker against an isolated scratch copy with deliberately corrupted source IDs, policy coverage, and labor totals. It reported the expected failures and exited with code 1. The actual destination package passed. No corrupted fixture was written into this repository.

After adding the review document to link checking, the first run caught its link to the not-yet-created verification report. Capturing the report created that artifact, and the next run passed. The final report below contains the successful result.

The final [verification output](verification.txt) records the package check. This is verification of the plan and its manifests. The future simulator, its benchmark targets, and its real-world validity remain unimplemented and untested.

## Attention

Actual operating costs, uptake, yields, school rollout, behavioral calibration, route permissions, and measured software performance remain open. The plan names how to acquire or test them. These are implementation and research dependencies, not hidden claims of completed work.
