# Experiments and validation

## Questions the first studies answer

Each study declares its population, observation window, baseline, treatment, outcomes, and assumptions before running. The first studies estimate effects within the model. They do not establish causal effects on real Toronto residents.

| Study | Primary outcome | Important secondary outcomes |
| --- | --- | --- |
| Municipal store siting and subsidy | Fixed-basket cost and household access | Fiscal cost, stockouts, household spending, displacement, store viability |
| Rescue and processing capacity | Usable food delivered per unit of operating cost | Spoilage, purchased-input share, rejected food, transport and storage burden |
| School meal expansion | Meals consumed and household basket shortfall | Uptake, household substitution, cost per served meal, kitchen constraints |
| Shared purchasing | Total delivered cost at equal served demand | Waste, hub overhead, reliability, supplier and transport capacity |
| Drone corridors | Total cost per completed order at equal service standards | Door-to-collection time, failures, exclusions, utilization, energy proxy |

Set a minimum practically meaningful difference in the relevant units with the analyst before finalizing replication counts. A statistically precise effect of a few seconds may have no operational value.

## Baseline and scenario design

Freeze source snapshots, the synthetic population, product catalog, schedules, behavior coefficients, and external shocks. The baseline represents verified active service where known. Unknown rollout receives separately labeled conservative and announced-capacity variants.

The [scenario catalog](../planning/scenarios.json) defines planning labels, not runnable scenario files. Single-policy scenarios use the baseline plus one intervention. The mature-policy screening study crosses four binary switches, giving 16 combinations. The school switch includes expansion with a declared procurement mode. A separate nested contrast changes procurement alone, preventing its effect from being confused with extra meals.

Begin with 30 matched seed blocks. Sixteen combinations produce 480 runs, rather than 480 independent populations. If a run takes the proposed maximum 10 minutes, sequential compute time is approximately 80 hours before analysis or live provider latency. Parallelize isolated runs. Most should use rule-based choices.

For a two-policy interaction, calculate:

```text
interaction = outcome(A and B) - outcome(A only)
              - outcome(B only) + outcome(baseline)
```

A combined program can save less than the sum of separate programs because the same household or food lot benefits twice in naive accounting. Shared ledgers and explicit participation prevent that double count.

Run a second, dated rollout study with dependency delays, capacity ramps, and budget exhaustion. Simulate at least one full school-year cycle where seasonality matters. Do not annualize a favorable 30-day demo without winter, holidays, school closures, and supply variation.

## Randomness and LLM comparisons

Use matched seeds and random streams keyed by actor, time, and purpose. Preserve shocks across treatments even when one policy creates extra events. Report paired differences, not unrelated run averages.

A single pair of runs provides a difference only. Replicated experiment sets estimate Monte Carlo uncertainty. Parameter uncertainty requires additional samples over unknown prices, yields, uptake, time sensitivity, and correlations. Model-form uncertainty requires alternate rules, such as different substitution or supplier-response models.

Separate three agent treatments: utility rules, frozen LLM receipts for replay of one run, and live LLM choice experiments. A receipt from one policy is not automatically feasible under another. Rebuild legal offers and record fresh choices for a new live treatment. Use paired household panels and matched external shocks without claiming matched model randomness.

Report LLM selection rates by group, fallback rates, refusal reasons, latency, tokens, cost, and behavioral distributions. Separate choices outside the predeclared four-household barrier subset from dispatched requests that timed out. Test whether budget exhaustion disproportionately removes decisions from a particular group or late simulation days. Live-model experiments need their own sensitivity analysis and a stated provider configuration.

## Sensitivity ranges to establish

| Parameter family | Required sensitivity |
| --- | --- |
| Municipal stores | Subsidy, overhead, supplier discount, uptake, locations, delayed opening, incumbent response |
| Processing | Eligible rescue share, purchased input, yield, shifts, cold storage, demand, transport delay |
| School meals | Participation, attendance, substitution, menu costs, readiness, calendar |
| Procurement | Discount curve, minimum order, storage cost, deliveries, supplier failure |
| Drones | No approval, conditional route approval, payload, handling, downtime, utilization, failures, ground fallback |
| Households | Income-rent correlation, time constraints, price response, habit, knowledge, dietary fit |
| Human response | Proxy weights, persistence, recovery, trust update, narrative grounding |

Choose ranges from evidence where possible. Label exploratory ranges. Include null and adverse cases. A policy does not pass because one selected parameter set makes it look good.

## Calibration and external validity

Calibrate to compatible observed aggregates such as basket expenditure, store choice shares, travel, school uptake, delivery reliability, and facility output. Keep a held-out period or geography. Avoid tuning both baseline behavior and treatment effects to the same post-policy observations.

Predeclare tolerances after examining data quality. Proposed starting goals are major population-control totals within 5% and selected expenditure or uptake holdouts within 10%, subject to sampling uncertainty and domain review. These are provisional targets, not achieved validation or universal scientific standards.

Record fit by subgroup and distribution, not only the mean. A correct average can hide excessive deprivation among households with mobility or time constraints. Report unsupported correlations and unidentified coefficients explicitly.

Use an ODD-style model description to document purpose, entities, process ordering, initialization, inputs, and submodels. ODD is a model-description protocol, not a validation certificate. [ODD update](https://www.jasss.org/23/2/7.html).

## Literal economic fixture

Implement a tiny fixture before adding a neighbourhood. Its expected values are specified independently of the code.

Opening state: household H has 1,000 cents, municipality M has 500 cents, retailer R and processor P have zero cents. R owns 1,000 grams of eligible produce as opening stock.

1. M transfers a 200-cent subsidy to R.
2. H pays R 400 cents for 600 grams.
3. H consumes 200 grams.
4. R transfers its remaining 400 grams to P and pays a 100-cent processing fee.
5. P produces 300 edible grams and records 100 grams of process loss.

Expected final cash is H 600, M 300, R 500, P 100, totaling 1,500 cents. Expected food is H 400 grams, P 300 grams, consumption 200 grams, loss 100 grams, totaling 1,000 grams. All reservations are released. Every cent and gram has a recorded source and destination.

Follow this with competing purchases, cancellation, expired food, a delayed van, a school absence, and a failed drone handoff. Assert literal expected outcomes. Do not write tests that merely restate the implementation's formulas.

## Required implementation gates

These are future acceptance gates. The planning-package checker does not execute them.

| Gate | Evidence required |
| --- | --- |
| Conservation | Fixture and every transition balance to zero cents and grams, with no negative available resources |
| Reservation safety | Two shoppers cannot settle the same stock. Cancellation releases cash and food exactly once. |
| Complete replay | All authoritative changes reconstruct between checkpoints, including consumption and cancellations |
| Recovery | Crash at transaction boundaries and uncertain provider dispatch, restart, and duplicate commands without double settlement or unbounded charge |
| Renderer independence | Headless and visible runs with frozen decisions have identical economic hashes |
| Clock correctness | Expiry, arrival, same-time events, positive service duration, and Toronto daylight-saving cases follow declared ordering |
| Grounded agents | Invalid options, invented facts, refusals, late replies, and exhausted budgets produce recorded fallbacks |
| 3D traceability | Every visible purchase, processing batch, queue admission, and delivery opens its causal event |
| Service quality | Stream gap, reconnect, slow client, incompatible schema, and partial export behave as specified |
| Data quality | Mixed units, invalid geography, stale resources, missing vintages, and duplicate IDs cannot enter a validated scenario silently |
| Model validity | Held-out fit, subgroup diagnostics, sensitivity results, and independent domain review are documented |

Use a documented reference machine and scenario for performance gates. Measure simulation time, rendering frame time, memory, provider latency, and projection latency separately. See the proposed limits in [architecture](architecture.md).

## Learn from real implementation

When a program launches, gather dated baseline and follow-up records. Measure prices and quantities, actual participation, service times, total costs, waste, and unmet demand. Collect real attitudes separately through an appropriate survey or interview design.

Where a phased rollout and comparison group permit it, plan a matched difference-in-differences or other credible quasi-experimental design with an independent researcher. Check pre-trends, selection, spillovers, seasonality, and concurrent policy changes. Do not label a before-and-after average as causal without those conditions.

Use observations to test the simulator's mechanisms and predictions. Publish disagreements, including cases where cheaper food fails to reach the intended household. Updating the model creates a new version, leaving prior forecasts and assumptions inspectable.

## Result package

Each completed study exports a manifest, input hashes, scenario parameters, policy timeline, code and runtime versions, seeds, decisions, event log, ledgers, food flows, subgroup outcomes, uncertainty intervals, costs, failure counts, and completion marker.

The report begins with the actual question, modeled population, baseline, and result. It distinguishes observed inputs, model estimates, and generated narrative. Include limits and adverse outcomes beside benefits. A video of happy residents is not validation.
