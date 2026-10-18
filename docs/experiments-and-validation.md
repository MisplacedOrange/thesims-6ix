# Experiments and validation

## Study sequence

Each study declares its source snapshot, active area, synthetic population, time horizon, baseline, intervention, deterministic organization rules, outcomes, and assumptions before it runs. Results describe behavior within this model; they do not establish causal effects on Toronto residents.

The active study scope follows the [focused roadmap](../NEXT_STEPS.md): complete the Council flow, bound the relevant organization decisions, preserve actual stakeholder evidence separately, and validate a persistent scenario. Pedestrian or LLM policy comparisons, rendering benchmarks, and unrelated interventions are deferred unless the selected proposal requires them.

The validation order follows the product scope:

| Stage | Question | Evidence required |
| --- | --- | --- |
| Council flow | Can a reviewer trace the proposal through impact mapping, scope, typed plan, decision, run, and replay? | Exact revision identity, source and unknown labels, affected groups and resource owners, human decision record, stored paired traces |
| Organization decisions | Are relevant business, supplier, and public-operator responses bounded and resource-consistent? | Actor authority, evidence state, explicit limits, committed stock/cash/capacity events, sensitivity cases for unsupported parameters |
| Stakeholder evidence | Are actual consultation and partner records represented independently from synthetic behavior? | Source, date, geography, method, reach, consent limits, disagreements, and missing groups remain visible |
| Persistent simulation | Can the selected proposal's rollout and repeated daily operation continue and recover? | Checkpoint/resume, event continuity, branch provenance, deterministic replay across the declared horizon |
| Proposal outcomes | What changes for households, organizations, and public accounts under the matched scenario? | Proposal-defined measures, reconciled ledgers, group denominators, implementation delays, uncertainty and evidence limits |

Do not begin with an arbitrary run count. Set a minimum practically meaningful difference in each outcome with the analyst, then choose replication counts using measured runtime and variance.

Planner rollout study design, scenario matching, and sensitivity factors are in the [agent planner plan](agent-planner-plan.md).

## Organization and stakeholder response

Start with explicit deterministic rules for organization operations and keep household movement as the bounded existing baseline. Do not add a model-policy comparison to the active work. For each selected proposal, compare a fixed baseline with only the supported organization decisions and record all choices as events. Use scenario ranges when evidence cannot determine a response.

Keep separate metrics for:

- organization actions and constraints: orders accepted, delivery timing, stock, operating hours, capacity, and reasons for limits;
- business activity: units sold, receipts, procurement, stockouts, and separately supported operating costs;
- household outcomes: purchases, service access, travel and waiting, and modeled unmet food need;
- public outcomes: authorized funding, transfers, outlays, implementation milestones, and delay;
- stakeholder evidence: groups reached, views or issues recorded, missing groups, and evidence provenance.

Matched seeds reduce simulation noise but do not remove uncertainty about prices, supply, capacity, participation, or model structure. Vary those parameters separately. Report paired differences, sensitivity ranges, evidence gaps, and failures as distinct results.

## Outcomes and response labels

Keep economic quantities in their stated units: household spending in cents, public spending in cents, food mass in grams, capacity and reach in declared units, and travel in seconds or metres. Report both average and distributional results by area, income group, and mobility profile where the synthetic population supports them.

Behavior, modeled response, and explanation are separate records. A proxy such as perceived access, trust, or satisfaction must identify its equation, version, inputs, and causal event IDs. It is not measured sentiment, clinical stress, or actual Toronto opinion. Generated dialogue is not survey data. If real sentiment is needed, define a consented and separately governed collection plan and keep it in a separate evidence stream.

## Sensitivity and calibration

For the active pilot, include only parameter families that affect its proposal and outcomes. The remaining rows below are a reference inventory; they do not require expanding the current model to cover every service type.

| Parameter family | Required sensitivity |
| --- | --- |
| World and routes | CRS and transform, missing links, barriers, crossing assumptions, speeds, accessibility |
| Pedestrian agents | Schedule, destination choice, route knowledge, time constraints, habits, mobility needs |
| Municipal groceries | Subsidy, overhead, supplier prices, uptake, location, delayed opening, incumbent response |
| Rescue and processing | Eligible supply, purchased input, yield, shifts, cold storage, demand, transport delay |
| School meals | Participation, attendance, substitution, menus, readiness, calendar, definition of “unlimited” |
| Modeled response | Proxy weights, persistence, recovery, trust update, perceived-access rule |

Use observed evidence where compatible. Otherwise label ranges exploratory and include null and adverse cases. A policy does not pass because one favorable parameter set makes it look effective.

Calibrate to compatible observed aggregates such as route counts, travel time, store access, basket expenditure, school uptake, delivery reliability, or facility output. Hold out a period or geography. Do not tune the baseline and claimed treatment effect to the same post-policy observations. Report fit by subgroup and distribution, not only the mean.

Record model purpose, entities, process ordering, initialization, inputs, and submodels in an ODD-style description. ODD is a model-description protocol, not a validation certificate. [ODD update](https://www.jasss.org/23/2/7.html).

## Implementation gates

These are future acceptance gates. The planning-package checker does not execute them.

| Gate | Evidence required |
| --- | --- |
| Council review | Proposal, impact map, scope, typed plan, decision, run, and replay preserve exact revision identity and evidence limits |
| Organization behavior | Every decision respects the actor's authority and resource limits; cash, food, capacity, and schedules reconcile through committed events |
| Stakeholder evidence | Actual submissions preserve source, time, geography, method, reach, consent, disagreements, and known representation gaps; synthetic behavior remains separate |
| Persistence and replay | Checkpoint, restart, resume, branch, and replay reproduce the recorded world and economic event hashes |
| Outcome reporting | Matched scenarios report proposal-relevant household, organization, and public measures with group denominators, assumptions, and adverse cases |
| Data quality | Mixed units, invalid geography, stale resources, missing vintages, and duplicate IDs cannot enter a selected scenario silently |

Planner-specific acceptance gates are in the [agent planner plan](agent-planner-plan.md).

Rendering benchmarks, model-provider latency, and broad transport performance are deferred from the active scope. For the current pilot, measure only operational reliability needed for authoritative persistence, command idempotency, economic settlement, and replay. Do not treat a planning target as a measured result.

## Learning from real implementation

When a program launches, gather dated baseline and follow-up records for actual prices, quantities, participation, service time, costs, waste, and unmet demand. Collect actual attitudes separately through an appropriate survey or interview design.

Where phased rollout and a comparison group permit it, plan a matched difference-in-differences or other credible quasi-experimental design with an independent researcher. Check pre-trends, selection, spillovers, seasonality, and concurrent policy changes. Do not label a before-and-after average as causal without those conditions.

Use observations to test the simulator's mechanisms and predictions. Publish disagreements, including cases where a lower-cost service fails to reach its intended residents. Updating the model creates a new version and leaves prior runs reproducible.

## Result package

Each completed study exports the world-package and source hashes, active area, scenario and rollout versions, population definition, code and runtime versions, seeds, pedestrian decisions, service command receipts, event log, ledgers, subgroup outcomes, uncertainty intervals, modeled-response labels, costs, failure counts, and completion marker.

The report begins with the actual question, modeled population, baseline, and result. It distinguishes observed inputs, estimates, assumptions, and generated narrative. Include limitations and adverse outcomes beside benefits. A video of residents moving through the city is not validation.
