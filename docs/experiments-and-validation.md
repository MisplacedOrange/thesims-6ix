# Experiments and validation

## Study sequence

Each study declares its world snapshot, active area, synthetic population, time horizon, baseline, intervention, agent policy, outcomes, and assumptions before it runs. Results estimate behavior within this model; they do not establish causal effects on Toronto residents.

The validation order follows the product scope:

| Stage | Question | Evidence required |
| --- | --- | --- |
| Toronto world | Does the 3D scene align with source geography and licenses? | Stable feature IDs, CRS checks, visual alignment samples, source manifest |
| Pedestrians | Can agents traverse valid routes and make replayable choices? | Route feasibility, movement replay, access and mobility diagnostics |
| Rollout planner | Can the planner propose a feasible staged buildout from evidence? | Structured proposal, source trace, deterministic validator result, review record |
| Outcomes | What changes in the model when a validated stage activates? | Matched baseline and treatment, economic ledger, reach, travel, and modeled response |

Do not begin with an arbitrary run count. Set a minimum practically meaningful difference in each outcome with the analyst, then choose replication counts using measured runtime and variance.

## Baseline and rollout design

Freeze source snapshots, world package, synthetic population, schedules, product catalog, agent-policy versions, and external shocks. The baseline represents verified active service where known. Unknown capacity remains explicit and can be represented with separate conservative and announced-capacity cases.

The [scenario catalog](../planning/scenarios.json) is a planning registry, not an executable scenario file. Its three core solutions are municipal groceries, food rescue and processing, and expanded school meals. Meituan-style drone delivery is an optional logistics scenario, not a fourth core solution. Confirm the exact intervention boundaries before a study treats them as settled.

A rollout study compares the same world, population, seed, and external shocks under baseline and an approved plan. The plan has dependencies, stage windows, capacity ramps, and delay or stop conditions. Include no-launch, delayed, reduced-capacity, and budget-exhaustion cases. If two solutions are tested together, measure their interaction explicitly:

```text
interaction = outcome(A and B) - outcome(A only)
              - outcome(B only) + outcome(baseline)
```

Do not infer a citywide impact from a single active area. Report modeled geography and population coverage. Expand the study area only after geographic and behavioral validation.

The simulation horizon should follow the question. Pedestrian schedules and service days unfold at daily scale; infrastructure rollout can span multiple years. A school-year cycle may matter for a school-service experiment, but one school day is neither the default product clock nor sufficient evidence of annual performance.

## Pedestrian and model-policy comparison

Start with deterministic movement and transparent rules. Compare those policies with small-model and bounded LLM choices only on the same frozen observations and legal option sets. Fix the resident panel before each study; camera view and model response speed must not select participants. Replays use recorded choices and make no model calls.

Keep separate metrics for:

- route completion, time, distance, waiting, and accessibility constraints;
- pedestrian activity and destination choice;
- household purchases and food/service access;
- public and operator costs, capacity, and rollout delay;
- model-call selection, fallback, refusal, latency, token use, and cost.

Set a new model-call panel, concurrency, deadline, and budget after active-area population and decision frequency are measured. The earlier household prototype's 40-person panel, 30-day horizon, four-request barrier, and CAD 30 ceiling are legacy planning assumptions, not approved pedestrian-agent settings.

Matched seeds reduce simulation noise but do not remove uncertainty about prices, route quality, participation, or model structure. Vary those parameters separately. Report paired differences, parameter sensitivity, model-policy variation, and failures as distinct results.

## Outcomes and response labels

Keep economic quantities in their stated units: household spending in cents, public spending in cents, food mass in grams, capacity and reach in declared units, and travel in seconds or metres. Report both average and distributional results by area, income group, and mobility profile where the synthetic population supports them.

Behavior, modeled response, and explanation are separate records. A proxy such as perceived access, trust, or satisfaction must identify its equation, version, inputs, and causal event IDs. It is not measured sentiment, clinical stress, or actual Toronto opinion. Generated dialogue is not survey data. If real sentiment is needed, define a consented and separately governed collection plan and keep it in a separate evidence stream.

## Sensitivity and calibration

| Parameter family | Required sensitivity |
| --- | --- |
| World and routes | CRS and transform, missing links, barriers, crossing assumptions, speeds, accessibility |
| Pedestrian agents | Schedule, destination choice, route knowledge, time constraints, habits, mobility needs |
| Municipal groceries | Subsidy, overhead, supplier prices, uptake, location, delayed opening, incumbent response |
| Rescue and processing | Eligible supply, purchased input, yield, shifts, cold storage, demand, transport delay |
| School meals | Participation, attendance, substitution, menus, readiness, calendar, definition of “unlimited” |
| Rollout | Stage delay, capital and operating cost, prerequisites, budget exhaustion, stop conditions |
| Modeled response | Proxy weights, persistence, recovery, trust update, perceived-access rule |

Use observed evidence where compatible. Otherwise label ranges exploratory and include null and adverse cases. A policy does not pass because one favorable parameter set makes it look effective.

Calibrate to compatible observed aggregates such as route counts, travel time, store access, basket expenditure, school uptake, delivery reliability, or facility output. Hold out a period or geography. Do not tune the baseline and claimed treatment effect to the same post-policy observations. Report fit by subgroup and distribution, not only the mean.

Record model purpose, entities, process ordering, initialization, inputs, and submodels in an ODD-style description. ODD is a model-description protocol, not a validation certificate. [ODD update](https://www.jasss.org/23/2/7.html).

## Implementation gates

These are future acceptance gates. The planning-package checker does not execute them.

| Gate | Evidence required |
| --- | --- |
| Toronto alignment | Scene features, pedestrian links, destinations, and candidate rollout sites share verified transforms and traceable source IDs |
| Replay | The same world package and recorded inputs reproduce resident positions, intents, economic events, and hashes in visible and headless modes |
| Economic conservation | Every transition balances money and food; invalid and concurrent transactions cannot spend the same resources twice |
| Pedestrian feasibility | Agents do not traverse blocked or unsupported paths; infeasible destinations are surfaced and handled deterministically |
| Agent grounding | Invalid intents, invented facts, refusals, late replies, and exhausted budgets produce recorded fallbacks |
| Planner feasibility | Bad source references, site constraints, units, budget, dependencies, and capacity are rejected before a plan can be approved |
| Staged activation | A site or capacity change appears only after the required funding and prerequisites commit |
| 3D traceability | A selected purchase, service, route, or infrastructure stage opens its causal events and source data |
| Data quality | Mixed units, invalid geography, stale resources, missing vintages, and duplicate IDs cannot enter a validated scenario silently |
| Modeled response | Every proxy is labeled modeled and can be inspected separately from behavior and observed survey evidence |
| Operational recovery | Disconnect, process failure, duplicate command, partial export, and unsupported replay version behave as specified |

Measure movement, rendering, API/event-stream transport, Python economics, model-provider latency, and archive performance separately on declared hardware. Set numeric limits after the first world slice and the active-area scale are known. Do not treat a planning target as a measured result.

## Learning from real implementation

When a program launches, gather dated baseline and follow-up records for actual prices, quantities, participation, service time, costs, waste, and unmet demand. Collect actual attitudes separately through an appropriate survey or interview design.

Where phased rollout and a comparison group permit it, plan a matched difference-in-differences or other credible quasi-experimental design with an independent researcher. Check pre-trends, selection, spillovers, seasonality, and concurrent policy changes. Do not label a before-and-after average as causal without those conditions.

Use observations to test the simulator's mechanisms and predictions. Publish disagreements, including cases where a lower-cost service fails to reach its intended residents. Updating the model creates a new version and leaves prior runs reproducible.

## Result package

Each completed study exports the world-package and source hashes, active area, scenario and rollout versions, population definition, code and runtime versions, seeds, pedestrian decisions, service command receipts, event log, ledgers, subgroup outcomes, uncertainty intervals, modeled-response labels, costs, failure counts, and completion marker.

The report begins with the actual question, modeled population, baseline, and result. It distinguishes observed inputs, estimates, assumptions, and generated narrative. Include limitations and adverse outcomes beside benefits. A video of residents moving through the city is not validation.
