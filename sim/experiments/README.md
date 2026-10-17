# Replicated experiments

This package is the weeks 14–16 experiment runner. It expands matched seeds and policy cells, calls a `RunExecutor` once per isolated world, and reports paired differences, two-policy interactions, sensitivity spreads, subgroup rows, and limitations.

`sim/core` implements `RunExecutor`. This package does not settle ledgers, write SQLite, call a provider, or render a scene. The behaviour package owns offers and rule choices. Person 2 owns persistence and export of the report.

## Designs

| Design | Cells |
| --- | --- |
| `screening` | 16 mature-policy combinations of groceries, processing, school, and drones |
| `paired` | Baseline and one treatment |
| `interaction` | Baseline, A, B, and A with B |
| `explicit` | Caller-named cells, including the baseline id |

`planning_screening_spec` uses seeds 1 through 30 and rule choices with the gateway disabled. Sixteen cells times 30 seeds is 480 runs. A shorter test run records that the planning default is 30 blocks.

Shocks are drawn with `sha256-unit-v1` from the seed, actor, day, and purpose. The policy is not part of the key. The executor must echo `shock_digest`. A mismatch fails that replication.

The interaction for one seed is `outcome(A and B) - outcome(A) - outcome(B) + outcome(baseline)`.

Paired differences are treatment minus baseline on the same seed. The Monte Carlo interval is simulation variation across seeds. It is not parameter uncertainty and it is not a Toronto confidence interval. Sensitivity is one family at a time and always has a null level and an adverse level. Those ranges are illustrative.

Subgroup rows cover income band, household size, area, mobility, and school eligibility. Households are unweighted. A household whose burden outcome is higher than that household's baseline is listed even when the average falls.

The report starts with the question, modeled population, baseline, and result. Every report includes the limitations in `limitations.py`. `complete` is true only when every replication completed. The rendered text omits the completion marker otherwise.

## Gateway

A rule study cannot set `gateway_enabled`. If an executor reports a provider dispatch while the gateway is disabled, the replication fails with `gateway_dispatch_while_disabled`.

The 16-cell screen is a hypothetical mature-policy comparison. A dated rollout, with approvals and capacity ramps, is a different explicit study. A 30-day window is not a school year.

## Tests

From the repository root:

```bash
python -m pytest sim/behavior/tests sim/experiments/tests
```

The runner tests repeat a study and compare the reports, check the 480-request expansion, and run one paired study through the real rule policy with the gateway disabled.

## Integration assumptions

1. Core's executor runs one seed and one cell in an isolated world and returns district outcomes in the declared units. It does not rescale households.
2. The executor applies `enabled_policies`, `parameter_overrides`, and `shocks`, then echoes `shock_digest`. Weather and income draws come from those shocks rather than from a second unseeded generator.
3. `economic_hash` is computed by core over economic state. This package copies it onto the report and does not hash ledgers itself.
4. Household metrics, when returned, identify income band, size, area, mobility, and school eligibility. Missing household rows leave the subgroup section empty. They do not become zeros.
5. Rule and frozen studies keep the gateway disabled. A live study that sets `gateway_enabled` false must still return `llm_dispatch_count = 0`.
6. Screening, sensitivity, and rollout answers stay in separate studies. This runner will not annualize a 30-day result into a school year.
7. Person 2 can persist `render_report` output and the report dataclass. Partial runs stay unmarked so downstream code can reject them.
8. Behaviour and experiment assumptions that the gateway and the kernel share are listed in [the behaviour README](../behavior/README.md).
