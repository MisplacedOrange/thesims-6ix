# Agent Planner and Time-Based Infrastructure Rollout

## Status and purpose

Status: planning recommendation. The planner interface, rollout scheduler, and infrastructure activation described here are not implemented or approved as calibrated Toronto parameters.

This document specifies how a simulated planning team can propose changes to the city and how approved changes unfold over logical simulation time. It supplements the [system architecture](architecture.md), [economic and agent model](simulation.md), and [roadmap and delivery gates](../NEXT_STEPS.md).

The core rule is that a planner submits a versioned schedule of proposed work. Python validates and records the schedule. The simulation changes infrastructure state only when a due milestone passes its checks and commits. Council or plan approval does not make a service immediately operational.

## Current implementation boundary

The browser currently renders a Toronto scene and seeded pedestrian itineraries. It has no connection to an authoritative Python world service. The Python packages provide a limited headless economic prototype, not a persistent city-world scheduler. The planner, its review flow, and time-based infrastructure rollout remain future work.

The design below follows the existing architecture boundary: Python owns logical time, infrastructure state, policy activation, and economic transactions; the browser renders committed snapshots and events. See [architecture](architecture.md#state-ownership-and-flow) and [integration status](integration.md).

The repository's `sim/data` package now retrieves and validates City GIS candidate snapshots with BM25-style lexical ranking and record citations. The current pedestrian simulation uses a pinned derived location snapshot. Proposal-time evidence refresh, proposal-to-source matching, and a planning agent are not implemented. The current location data do not establish operating status or service capacity.

## Design rules

1. **Plans are proposals, not world writes.** Planner agents may read a bounded planning snapshot and submit a structured draft. They cannot call arbitrary setters, write directly to the database, spend funds, move residents, or activate infrastructure.
2. **Actions use a controlled catalog.** Each action has a versioned type and acts on stable, validated feature IDs or known entities. A plan cannot invent map geometry, a site, a service type, a budget, or an operating capacity.
3. **Approval and activation are separate events.** Approval permits the schedule to enter the run. Each milestone still checks its prerequisites before it changes the world.
4. **Planning and pedestrian time use different scales.** Daily resident activity can continue while procurement, readiness, commissioning, and capacity ramping unfold over months or years.
5. **Unknown inputs stay explicit.** Missing costs, durations, staffing, and capacity remain unknown or use clearly labeled scenario ranges. The planner must not silently fill gaps with generated values.
6. **Committed events drive the display.** The browser renders a planned, in-progress, delayed, or operational state after it receives the corresponding authoritative snapshot or event.

## Open proposal scope and executable actions

The proposal intake is open-ended: users can upload Markdown proposals that are not among the current grocery, food-processing, or school-food demonstration examples. Those examples and their IDs are planning fixtures, not an allowlist of proposals the product can accept. Proposal intake preserves and versions a new proposal even when the simulator cannot yet represent its requested changes.

Execution remains bounded by the versioned action registry described below. The registry defines reusable, validated simulation operations and their units, preconditions, and state effects; it does not define the full set of policy proposals. A planner may map a proposal to supported actions and parameterize them from cited evidence and explicit assumptions. If a requested change needs an unsupported action type or mechanism, the plan must identify that gap and remain unschedulable until the simulation action is deliberately specified and implemented. An agent must not invent an executable action, site, capacity, funding source, or world-state change to make the proposal appear supported.

This separates open proposal intake from supported simulation coverage. Acceptance of a Markdown proposal does not guarantee that every requested effect can already be modeled.

Food-bank, pantry, meal-program, and other food-support proposals may target either a new service site or an existing source-listed location/program. The City's food-support layer is mixed: preserve its `PROGTYPE` and source record IDs, and do not infer current operation, eligibility, hours, stock, capacity, or a unique operator from the mapped point alone. Existing partner-run services enter an executable plan only when their operating status is verified or explicitly assumed and the scenario records an agreement authorizing the proposed funding, procurement, resource assignment, expansion, reduction, or stop. Otherwise the location remains planning context and the requested action is unschedulable.

## Proposal-time evidence workflow

Every new proposal submission and material proposal revision starts a retrieval request before department agents draft a plan. The request is based on the versioned proposal and its structured intent, including requested actions, target geography and population, time horizon, required inputs, outcome measures, and constraints.

The Python evidence coordinator matches proposal requirements to registered sources and fields, checks freshness for relevant sources, refreshes sources when their declared update policy says they are due, and retrieves from the newest complete, validated snapshot available. The retrieval runs for each submission or material revision; the coordinator need not redownload every source when a current validated snapshot is already available. “Latest” means latest complete validated data available from the registered source. Source update and observation dates, source refresh-check time, and retrieval time are separate fields. Unknown dates remain unknown. The [City of Toronto Open Data FAQ](https://open.toronto.ca/docs/frequently-asked-questions/) notes that its last refresh check does not establish the freshness or accuracy of underlying records.

If a refresh fails, the coordinator returns the last complete snapshot with a stale label or marks the source unavailable. It never silently calls old data current. Proposal matching returns field-level coverage, citations, conflicts, missing inputs, and unsupported outcome measures. The planner receives the proposal, evidence bundle, and frozen world snapshot together. It submits typed actions only; evidence retrieval does not change world state, grant authority, or make unsupported actions schedulable.

Each plan version pins the proposal revision, evidence bundle ID, source snapshot IDs and content hashes, retrieval and matching-rule versions, and source freshness labels. If relevant evidence changes before approval or scheduling, rebuild the evidence bundle and revalidate the plan. The approved plan remains tied to its exact evidence and world revisions for replay.

## Planner interface

Expose a small Python-side tool boundary to the planner:

| Operation | Caller | Effect |
| --- | --- | --- |
| `build_proposal_evidence(run_id, proposal_id, proposal_revision)` | Python evidence coordinator, on proposal submission or material revision | Checks relevant source freshness, retrieves from newest complete validated snapshots, and returns a cited evidence bundle with coverage, missing, stale, and unavailable fields; does not mutate simulation state |
| `get_planning_snapshot(run_id, expected_revision)` | Planner | Returns read-only world, budget, site, capacity, evidence, and active-stage data with revision and content hashes |
| `submit_plan_draft(run_id, plan)` | Planner | Stores a new draft version and returns schema and feasibility findings; does not schedule or activate work |
| `review_plan(plan_id, revision, decision)` | Human reviewer through the browser | Records approve, request-revision, or reject against that exact plan revision |
| `schedule_approved_plan(plan_id, revision)` | Python coordinator | Creates the run's pending milestone events after approval and validation |
| `process_due_milestone(run_id, milestone_id)` | Python simulation service | Rechecks current prerequisites and commits the state transition, or records a delay/rejection reason |

The tool names are illustrative, not implemented API endpoints. The planner does not receive an `activate_stage` or unrestricted `set_world_state` tool. Commands that enter the simulation should carry a schema version, run ID, idempotency key, and expected revision, as described in the [architecture command boundary](architecture.md#state-ownership-and-flow).

### Planning snapshot

The read-only snapshot should be sufficient to make and validate a plan without exposing unrelated household records or provider credentials. It should include:

- The run ID, logical time, current revision, and immutable world/evidence snapshot hashes.
- Eligible candidate site IDs and their relevant constraints, provenance, and evidence status.
- Existing food-support location/program record IDs, source `PROGTYPE`, verified or unknown operating status, and any authority agreement and scope that permits intervention.
- Existing and already-planned services, their current status, capacity, dependencies, and schedules.
- Available and committed budgets, relevant staffing/equipment/supply limits, and the planning horizon.
- Supported action types and units, plus the proposal version and required outcome measures.
- Proposal evidence bundle ID, relevant source snapshot IDs and hashes, retrieval time, freshness labels, and evidence coverage or gaps.

All planning uses one frozen snapshot. If the world changes before a plan is approved or scheduled, the coordinator checks the expected revision and requires revalidation when affected facts have changed.

### Plan record

Each plan version should carry:

- Plan ID, schema version, proposal ID/version, run ID, base world revision, and evidence snapshot hash.
- Proposal evidence request and bundle IDs, source snapshot IDs and content hashes, source-level freshness labels, and matching-rule version.
- Stages with stable IDs, typed actions, targets, dependencies, earliest/latest windows, duration assumptions, and prerequisites.
- Target references that distinguish a source-listed location/program record, a modeled physical facility, an operator, and a contracted service scope; retain source IDs and do not collapse records without a reviewed crosswalk.
- Resource requests and estimates for funding, staffing, equipment, storage, and supply, with units and evidence state.
- Capacity milestones or a piecewise capacity ramp, including the service unit (for example, meals/day or visits/day).
- Source IDs, assumptions, unknowns, expected outcome-measure IDs, risks, and delay/reduction/stop conditions.
- Planner/model configuration and the deterministic validation result.

The draft format is declarative. It describes the intended change and its timing; it does not contain executable code. Proposed action types should be added deliberately to a registry, with schema, units, preconditions, and committed state effects documented for each type.

## Rollout lifecycle and simulator time

Represent a rollout as ordered stages. A typical infrastructure pathway is:

`planned -> scheduled -> in_progress -> commissioned -> operational -> completed`

Stages can instead transition to `delayed`, `reduced`, `stopped`, or `canceled`. The proposal and work-package lifecycle should retain the explicit records already described in the [simulation model](simulation.md#policy-rollout-state-and-outcomes).

Each milestone has a logical due time or a condition that makes it eligible to occur. When the simulation clock reaches that boundary, Python processes due events in stable order and rechecks:

- Site eligibility and any location or access constraints.
- Funding and required resource availability.
- Upstream stages and explicit dependencies.
- Staffing, procurement, equipment, and capacity prerequisites.
- Whether the plan revision is still valid for the current world state.

If checks pass, Python commits one atomic milestone event and any associated ledger/resource events. If checks fail, it records why the stage is delayed, reduced, or stopped and leaves unavailable capacity unavailable. A later revised schedule creates a new version; it does not erase the original plan or event history.

Infrastructure schedules should use the logical world clock, stored as integer simulation seconds against a scenario epoch. User-facing dates can be displayed in Toronto local time. The service advances to the next decision or physical event boundary; browser playback speed changes presentation speed only. These clock conventions are specified in [architecture](architecture.md#time-replay-and-persistence).

Use fixed durations for tightly controlled comparisons. When uncertainty is part of a study, declare a duration range or distribution and its evidence state. Resolve stochastic durations from a versioned, seeded stream and persist the realized duration before execution so the same run can replay exactly. Model delay scenarios explicitly; do not ask an LLM to improvise delays while a run is executing.

### Capacity and operational effects

Planning, procurement, or construction status can appear on the map and timeline without providing service. Only a committed operational milestone changes modeled capacity or makes a destination available to pedestrian choice generation. A capacity ramp is a sequence of committed milestones; for example, commissioning can open a site at partial capacity, followed by later increases when staffing and supply conditions pass.

Existing food-support points are baseline location records, not proof of operational service. A verified, authorized provider may already operate in the baseline; a proposed grant or service expansion is a separate versioned scope with its own funding, supply, staffing, and capacity events. A mapped point alone must not make food available to residents. Reducing or stopping a partner intervention ends only the modeled agreement scope unless the scenario explicitly represents a broader authorized change.

The visual layer may show candidate, planned, in-progress, commissioning, operating, delayed, or stopped status. Its appearance is a projection of simulation state. A visual construction animation by itself does not imply a real modeled capacity or cost change.

Costs should be treated consistently with the economic kernel. Plan estimates and reservations are not settled expenditures. Record public or operator costs when their corresponding funding, procurement, construction, or operating events commit, using explicit accounts and units. Prevent a milestone from partially changing capacity or money if its transaction fails.

## Illustrative timeline

The following durations are placeholders to demonstrate scheduling mechanics, not Toronto estimates:

| Simulator period | Stage | World effect after milestone commit |
| --- | --- | --- |
| Month 0 | Plan approved and scheduled | Timeline appears; no service capacity is added |
| Months 0–3 | Site readiness and procurement | Recorded commitments and readiness progress; site remains unavailable to residents |
| Month 3 | Commissioning | Site becomes operational at a declared initial capacity if funding, staffing, equipment, and supply checks pass |
| Months 4–9 | Capacity ramp | Additional capacity milestones commit only when their prerequisites pass |
| Month 9 onward | Operation | Residents can consider the service; operations, reach, costs, delays, and outcomes continue to be recorded |

Daily resident decisions continue during this schedule. A rollout comparison therefore observes both the period before service opens and the later operating period, instead of treating the proposal approval date as the treatment start.

## Human review surface

The browser review view should connect the plan to the city and its evidence:

- A map overlay for candidate sites and planned/in-progress/operational stages.
- Existing food-support locations and program types, with candidate versus verified status and the authorized intervention scope visible for any partner-run service.
- A timeline showing dependencies, stage windows, current simulator time, and capacity ramps.
- Costs, resources, expected measures, and eligibility/feasibility results in declared units.
- Source links, source observation/update and retrieval times, freshness labels, assumptions, unknowns, disagreements, validation errors, and warnings beside the relevant stage.
- Versioned approve, request-revision, and reject actions. Each decision records the reviewer, plan revision, and simulation revision.

Approval records the user's simulated decision. Python remains responsible for scheduling and later committing every state change. The interface should show the recorded delay or failure reason when a milestone does not activate as planned.

## Events, persistence, and replay

At minimum, record versioned events for plan submission, validation, review decision, scheduling, stage start, milestone activation, capacity change, delay, reduction, stop/cancellation, and completion. Every event should include its simulation time, run and plan revisions, stage ID, source/assumption references, and cause or prerequisite result.

Checkpoints must preserve active stage state, the pending milestone queue, realized duration draws, current infrastructure capacity, resource reservations, and event sequence. Replay uses recorded choices and committed events without new model calls. Baseline and rollout branches pin the same starting world and record the plan version and schedule differences.

## Implementation sequence and validation gates

1. **Build proposal-time evidence retrieval.** Define versioned proposal intents and outcome measures, the source freshness registry, source-to-field matching rules, and the immutable evidence bundle. Use labeled proposal-to-source fixtures to report retrieval precision and recall. Exercise relevant, irrelevant, missing, stale, unavailable, and conflicting-source cases; verify that unknown or stale records cannot be labeled observed. Pin exact source snapshots and hashes.
2. **Define the action registry and plan schema.** Start with one service-site action and stable site IDs. Specify units, allowed states, preconditions, and economic effects. Preserve food-support source/program IDs and `PROGTYPE`; require explicit agreement scope before actions target a partner-run program.
3. **Build the logical-time scheduler.** Prove that a scheduled event fires at its simulator time in a stable order, independent of browser rendering and playback speed.
4. **Implement one end-to-end staged site.** Verify that approval schedules work, pre-opening time has no service capacity, commissioning changes capacity only after checks, and the ramp follows the declared milestones. After this proof, exercise one existing food-support program under an explicit scenario agreement; verify that funding or a mapped point alone does not create stock or service capacity.
5. **Exercise delay and failure cases.** Verify missing funding, unavailable staffing/supply, stale revisions, reduction, cancellation, checkpoint/resume, and replay. Confirm that failures leave no partial economic or capacity changes.
6. **Add the review timeline and map projection.** Ensure displayed state changes follow committed events and carry their source and plan version.
7. **Compare baseline and rollout.** Measure outcomes before and after opening, include delayed/reduced/no-launch cases, and report the modeled population, time windows, units, and uncertainty.
8. **Add model-generated plans only after rule-based plans work.** Keep the same schema and validator, freeze each planner's inputs/configuration, record disagreements, and require human review. Evaluate model proposals against the same snapshots and feasibility checks.

These are future acceptance gates, not completed validation. The first useful proof is one site with an auditable schedule, deterministic activation, and replay before adding multiple departments, more action types, or LLM planning.
