# Focused roadmap: Council-led organization and stakeholder simulation

Updated October 18, 2026. This is the active roadmap. Current work is limited to four linked concerns: a complete Council proposal flow, bounded organization behavior, real stakeholder evidence, and a persistent simulation with traceable evidence. Other features remain supporting infrastructure or are deferred; this roadmap sets no delivery date, staffing commitment, or approved budget.

## Current implementation status

The browser renders a frozen, attributed downtown Toronto map and replays seeded pedestrian and food-access traces from a deterministic six-hour scenario. The scenario includes household purchases and food use, retailer and support-site service, school portions, supplier deliveries, and a hypothetical emergency site. Prices, operating schedules, capacities, eligibility, household attributes, and food-use values are illustrative assumptions. This is a runnable prototype, not an empirically calibrated Toronto model.

The local Python Council service stores exact Markdown revisions, scopes, typed plans, reviewer decisions, idempotency receipts, proposal-linked organization revisions, stakeholder-input records, and paired baseline/intervention traces in SQLite. It supports one hypothetical municipal food-site action. The browser panel now supports proposal intake plus organization and stakeholder-input records, and shows organization references on stored rollout events. Scope, plan, decision, and run controls remain API-only, so the Council UI is still incomplete.

Retailers, suppliers, schools, and food-support sites have limited operational state in the food scenario. Proposal-linked organization records and group-level stakeholder-input records can be saved as immutable, source-labeled revisions. They are review context only: organizations do not generally respond to proposals, the form does not conduct or verify consultation, and synthetic households do not represent stakeholder views. There is no persistent multi-day world, checkpoint, resume, or evidence-refresh service. The data and scenario limits are recorded in [integration status](docs/integration.md) and the [implemented scenario contract](sim/interactables/README.md).

## Active scope

The first integrated proof will take one proposal through a human-reviewed Council workflow and a reproducible multi-day scenario. Use the existing `establish_service_site` action as the starting point unless a better-supported proposal is selected during scope definition. Include only the organizations, affected groups, resources, and outcomes needed to evaluate that proposal.

The simulation must distinguish:

- observed evidence, announced plans, estimates, illustrative assumptions, and unknowns;
- organization state, organization decisions, and committed resource changes;
- synthetic household behavior, modeled outcomes, and actual consultation evidence;
- the proposal's rollout calendar and the repeated daily operation of services.

No simulated role may claim to represent a real department, company, resident, worker, or community group. No proposal decision authorizes real City action.

## Delivery sequence and acceptance gates

| Gate | Status | Work | Acceptance evidence |
| --- | --- | --- | --- |
| 1. Council flow | Partial: proposal, organization, and stakeholder-input records are available in the browser; scope, plan, decision, and run remain API-only | Complete the browser path from exact proposal revision through impact map, evaluated scope, typed supported plan, explicit reviewer decision, paired run, and result replay. Unsupported requests remain visible and cannot be approved for execution. | A human can inspect the proposal and evidence limits, record the affected actors and groups, review the exact plan revision, and open the exact stored baseline and intervention traces. Stale or duplicate commands do not create duplicate effects. |
| 2. Organization and stakeholder behavior | Partial: immutable proposal-linked records and plan/run references exist; behavior and actual consultation remain unimplemented | Use source-backed records to implement only proposal-relevant bounded decisions, such as order acceptance, delivery timing, stock, hours, or service capacity. Establish a separate real-world consultation process before treating stakeholder entries as representative evidence. | Every modeled organization decision has an actor, authority, resource limit, evidence state, and committed event. Input records preserve source, date, geography, method, groups reached, consent limits, missing groups, and conflicting views. Synthetic agents are never presented as consultation. |
| 3. Persistent pilot world | Not started | Extend the authoritative Python state across repeated operating days and rollout milestones. Add versioned checkpoints, restart, resume, branch, and deterministic replay. Choose the horizon to capture the proposal's relevant delivery and operating cycles; represent rollout dates separately from daily schedules. | Restarted and replayed runs reproduce state and event hashes. Inventory, cash, commitments, capacity, schedules, and pending milestones remain consistent across day boundaries. |
| 4. Integrated proposal evaluation | Not started | Run a same-start-state baseline and intervention for the selected proposal. Report household access and distribution, operator activity and costs, public spending, service capacity, and implementation delays. Add only measures the evidence and model support. | Each result traces to committed events, source snapshots, or labeled assumptions. Show group denominators, uncertainty ranges, adverse/no-launch cases, and data gaps. External calibration claims require compatible independent observations and held-out validation. |

Complete each gate with a reviewable artifact and recorded acceptance result before expanding the model. Preserve the deterministic rule-based scenario as the baseline while adding organization decisions and persistence.

## Evidence and validation rules

Pin source snapshots, transformation versions, scenario assumptions, code version, population, and random seed to every run. Keep raw source data immutable and distinguish publication, observation, retrieval, and refresh-check dates. A recent download does not establish current operations. Missing operating status, inventory, prices, capacity, authority, staffing, costs, or consultation remains unknown unless explicitly supplied or labeled as an assumption.

Separate household expenditure, business receipts, procurement, wages, operating costs, grants, public cash outlay, and resource costs. Do not infer business viability from revenue alone or count transfers twice. Report outcomes by affected groups with denominators, and keep synthetic outcomes separate from survey or consultation findings.

Conservation, legal actions, idempotency, restart, and replay are implementation checks. They do not establish empirical calibration, causal policy effects, representative public opinion, or a forecast for Toronto. Use scenario ranges and sensitivity analysis where evidence is insufficient; make stronger claims only after external validation against compatible data.

## Deferred from the active roadmap

The following are not active deliverables unless the selected proposal makes them necessary: citywide map expansion and visual polish, traffic or transit simulation, drones, a broad catalog of policy actions, additional school/processing demonstrations, autonomous department or company agents, LLM decision-making, reinforcement learning, detailed rendering-performance targets, and modeled sentiment or dialogue. Existing code and documentation may remain as implementation context; these items should not be described as current product commitments.
