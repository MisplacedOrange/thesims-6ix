# Agent planner and infrastructure rollout plan

## Status and first proof

Status: one bounded Council proof is implemented in `sim/council.py` and the browser. It preserves exact Markdown revisions, marks only explicit section headings and citations, keeps unclassified text, saves a reviewed scope and typed site plan, records approve/request-revision/reject decisions, and generates a matched baseline/intervention pair. Deterministic department-role notes are advice; they are not model calls or authority. One supported action adds a hypothetical municipal food site to one six-hour run. Scenario values are not calibrated Toronto parameters.

The local API stores immutable proposal, scope, plan, decision, run, and trace records in SQLite, with revision checks, idempotency receipts, schema version 1, and a simulator source hash. Each run pins its population, seed, map, catalog, location snapshot, and Python simulator inputs. Funding and supplier payments use `sim.core`; runtime shortages produce a recorded no-launch and leave service capacity at zero. The city still has no persistent multi-day world.

The proposal parser does not infer semantics from prose or refresh evidence. The pinned location snapshot can be stale or incomplete; operating status, current inventory, capacity, authority, freshness, and measured outcomes remain unknown unless explicitly modeled as assumptions. General proposal matching, source refresh, separate model agents, a reusable action catalog, mandate-based delegation, broad infrastructure actions, and ongoing-world persistence remain future work.

The first proof is a rule-based planner that can open one hypothetical municipal food site under a finite scenario grant. It covers site selection, staged readiness, supplier stock and procurement, pedestrian use, and modeled access outcomes. Staffing, capital investment, recurring operations costs, and operating-cost measures are not modeled yet. Add mechanisms only after their accounting and evidence requirements are explicit.

The repository has a bounded Python food-access simulation, a browser that replays generated traces, and City GIS location retrieval. It has no persistent Python world service or general infrastructure planner. Location records are planning candidates. They do not establish a provider's current operation, hours, eligibility, stock, capacity, or authority to intervene.

### Current code to build on

The [interactables runner](../sim/interactables/simulation.py) generates a deterministic six-hour food-access scenario; its [README](../sim/interactables/README.md) documents the scenario contract. The [economic commands](../sim/core/commands.py) and [kernel](../sim/core/kernel.py) settle typed transactions and return accepted transitions or rejections. They do not commit one durable transaction across economic state, infrastructure, and a milestone queue.

The [City data pipeline](../sim/data/README.md) retrieves and cites candidate locations. The pedestrian trace generator uses the pinned [downtown location snapshot](../sim/data/snapshots/toronto-downtown-sites-v3.json). The snapshot does not establish operating status, hours, inventory, capacity, eligibility, or operator authority. Per-proposal evidence refresh and matching remain unimplemented.

This plan extends the [system architecture](architecture.md), [economic and agent model](simulation.md), [pedestrian food interactables](pedestrian-interactables-plan.md), [dashboard plan](dashboard-implementation-plan.md), and [roadmap](../NEXT_STEPS.md). Python remains the sole authority for world state, schedules, resources, and economic transactions. The browser displays committed snapshots and events.

## Planning boundaries

Proposal intake is open-ended. A person can submit and revise any Markdown proposal, including proposals beyond the grocery, food-processing, and school-food examples. Intake preserves and versions the proposal even when the simulator cannot represent all requested effects.

Execution is bounded by a versioned action catalog. Each action defines its schema, units, targets, preconditions, resource effects, timing, cancellation behavior, and committed events. The catalog describes supported simulation operations. It does not limit which proposals the product can accept.

The planner submits declarative, typed requests. It cannot execute code, call arbitrary setters, write directly to the database, spend funds, move residents, or activate infrastructure. Python validates every request and milestone. If a proposal requires an unsupported mechanism, the plan records the gap and remains unschedulable until the mechanism is deliberately implemented. A supported subset proceeds only through an explicitly reviewed scope revision or an existing mandate that permits it.

Keep proposal coverage separate for mechanisms and outcomes. A modeled site opening does not support a claim about clinical health effects. Use `supported`, `requires_parameters`, and `unsupported` for each requested mechanism and outcome measure. Preserve exclusions and their consequences. Do not present a supported subset as an evaluation of the full proposal.

Unknown inputs remain unknown unless a reviewer approves a labeled scenario assumption. A generated value cannot become an observed fact. A budget authorization is not cash, a funding announcement does not create inventory, and a delivery commitment does not mean stock has arrived.

## Authority and review

| Actor | Responsibility | Authority |
| --- | --- | --- |
| Council or user | Define goals, tradeoffs, funding, and permitted scope | Approve an exact plan or a bounded planning mandate; approve material scope changes |
| Department role agents | Assess evidence and constraints within a declared responsibility | Recommend sourced work packages; cannot activate stages or claim real department authority |
| Reviewer | Check a plan draft, validation findings, and evidence | Approve, request revision, or reject an exact plan revision |
| Planning agent | Assess conditions, select sites and interventions, allocate authorized resources, schedule work, and propose revisions | Submit typed requests within its role and mandate |
| Python simulation | Validate requests, resolve contention, advance time, commit effects, and calculate outcomes | Sole writer of infrastructure, resources, policy state, and accounts |

The initial interface uses review of an exact plan revision. A separate mandate mode can delegate routine decisions within defined bounds. Mandate-based delegation is a proposed extension. It must be explicitly approved and implemented before agents can use it.

A versioned mandate records:

- Run, proposal, mandate, and version IDs, plus the reviewer and approval time.
- Objectives, outcome-measure IDs, priorities, and tradeoff rules.
- Permitted action types, roles, geography, and eligible site classes.
- Funding accounts, commitment limits, operating horizon, and periodic spending limits.
- Bounds for capacity, prices, subsidies, staffing, procurement, and schedule revisions.
- Allowed scenario assumptions and their evidence labels.
- Review cadence, expiry, escalation conditions, and stop conditions.

Within an active mandate, an agent may submit compliant work without individual approval for each routine action. Python still checks every request and milestone. Work outside the mandate requires revised approval. Revocation blocks new commitments and applies the declared handling to pending work. It does not erase settled payments, contracts, liabilities, or safe shutdown requirements.

Exact-plan review remains available for controlled experiments and any scenario where delegated revisions are out of scope.

### Planning roles

Simulated roles can cover public health, planning and construction, finance and procurement, food operations, and logistics. Map each role to relevant public responsibilities without implying City staff participation or delegated authority. Roles work from the approved proposal, frozen evidence, current world state, budgets, and explicit constraints. They can identify dependencies, disagreements, and unsupported assumptions. Their recommendations do not carry real department authority.

The bounded proof produces deterministic finance, site-readiness, supply, and access notes. The reviewer explicitly chooses the supported action and labeled parameters; advice cannot approve or schedule it. Separate department agents are not needed to prove validation, resource checks, staged activation, and replay. Add role agents only after those execution rules work.

## Proposal evidence

Every proposal submission and material revision starts an evidence request before planning. Parse the request into typed intent: requested actions, target geography and population, time horizon, mechanisms, required inputs, outcome measures, and constraints. Match each intent to registered sources, fields, and supported actions. Free-text similarity alone cannot establish that evidence supports an action.

The evidence coordinator checks source freshness and retrieves from the newest complete, validated snapshots. It refreshes sources when their declared update policy says they are due. It need not redownload a valid current snapshot for each proposal. Record source update dates, observation dates, refresh-check times, and retrieval times separately. Unknown dates stay unknown. A recent retrieval does not prove that the source record is recent or accurate. The [City of Toronto Open Data FAQ](https://open.toronto.ca/docs/frequently-asked-questions/) also distinguishes a dataset refresh check from the freshness and accuracy of its records.

If a refresh fails, return the last complete snapshot as stale or mark the source unavailable. Never label old data current. Report field-level coverage, citations, conflicts, missing inputs, and unsupported outcomes. Retrieval is read-only. It does not change world state, grant authority, or make an unsupported action schedulable.

Each immutable evidence bundle records:

- Proposal ID and revision, request ID, source-registry version, and matching-rule version.
- Query, filters, source snapshot IDs, content hashes, and retrieval time.
- Source record IDs, citations, source freshness, and field-level evidence states.
- Coverage, missing fields, conflicts, and unsupported measures.

The evidence request also records affected population groups, businesses and organizations that control relevant sites or services, responsible public authorities, and likely spillover effects. Keep actual resident, worker, business, and community input as dated, source-linked evidence. Record its geography, collection method, population reached, consent or publication limits, disagreements, and representation gaps. Synthetic behavior and simulated expert recommendations do not establish real consultation or endorsement.

Each plan version pins its proposal revision, evidence bundle, source snapshots and hashes, retrieval and matching-rule versions, and freshness labels. A relevant evidence change before approval or scheduling requires a new bundle and plan validation. The approved plan stays tied to the exact evidence and world revisions used for replay.

### Existing food-support records

Preserve the source ID, record ID, name, coordinates, `PROGTYPE`, retrieval time, evidence state, and source URL. A listed row is a location or program record. It is not automatically a unique operator or a verified operating facility.

Keep the source-listed location/program, modeled facility, operator, and contracted service scope as distinct entities. Link them only through a reviewed crosswalk. Do not merge records because names or addresses look similar. Keep unknown operating status, hours, eligibility, inventory, and capacity explicit.

A partner-run program can enter an executable plan only when the scenario verifies its operation or labels an assumption, and records an agreement authorizing the proposed intervention. The agreement names the operator, program, site, permitted scope, resources, term, and limits. Without it, the location remains planning context. A City action can affect only its authorized grant or contract scope. It cannot close or change the provider's wider service.

## Planner interface and records

The local Council API in [sim/council.py](../sim/council.py) exposes `/api/council` commands for intake, explicit scope, one typed plan, human decisions, paired runs, and exact trace retrieval. They are narrower than the general planning operations below, whose names remain design examples.

| Operation | Caller | Effect |
| --- | --- | --- |
| `build_proposal_evidence(run_id, proposal_id, proposal_revision)` | Evidence coordinator on submission or material revision | Checks relevant source freshness and returns a cited bundle with coverage, missing, stale, and unavailable fields; does not mutate simulation state |
| `get_planning_snapshot(run_id, expected_revision)` | Planner | Returns read-only world, budget, site, capacity, evidence, and active-stage data with revisions and hashes |
| `submit_plan_draft(run_id, plan)` | Planner | Stores a draft version and returns schema and feasibility findings; does not schedule or activate work |
| `review_plan(plan_id, revision, decision)` | Human reviewer through the browser | Records approve, request-revision, or reject for that exact plan revision |
| `schedule_approved_plan(plan_id, revision)` | Python coordinator | Creates pending milestone events after approval and validation |
| `process_due_milestone(run_id, milestone_id)` | Python simulation | Rechecks prerequisites and commits the transition or records a delay or rejection reason |

Commands that enter the simulation carry a schema version, run and command IDs, an idempotency key, actor and role, mandate or exact-plan approval reference, plan and stage IDs, observation hash, relevant revisions, target IDs, typed parameters, evidence references, and timing requirements.

`sim6ix plan validate plan.json` remains an illustrative CLI command. It is not implemented.

### Planning snapshot

The read-only snapshot includes:

- Run ID, logical time, current revision, and immutable world and evidence hashes.
- Eligible site IDs, constraints, provenance, and evidence status.
- Existing and planned services, status, capacity, dependencies, and schedules.
- Food-support source/program IDs, `PROGTYPE`, operating status, and any authority agreement.
- Available and committed budgets, staffing, equipment, supply limits, and planning horizon.
- Supported action types, units, proposal version, and required outcome measures.
- Evidence bundle and source snapshot IDs, hashes, retrieval time, freshness, coverage, and gaps.

Expose only information allowed by the experiment's observation policy. Do not include unrelated household records, provider credentials, or future shocks. Freeze one snapshot for each planning decision. If relevant world facts change before approval or scheduling, revalidate against the new revision.

### Plan record

Each plan version carries:

- Plan ID, schema version, proposal ID and revision, run ID, base world revision, and evidence snapshot hash.
- Evidence request and bundle IDs, source IDs and hashes, freshness labels, and matching-rule version.
- Stable stage IDs, typed actions, targets, dependencies, time windows, duration assumptions, and prerequisites.
- Distinct target references for source records, modeled facilities, operators, and contracted scopes.
- Funding, staffing, equipment, storage, and supply requests with units and evidence states.
- Capacity milestones or a piecewise capacity ramp with an explicit service unit.
- Sources, assumptions, unknowns, outcome measures, risks, and delay, reduction, or stop conditions.
- Planner configuration and deterministic validation results.

Plan drafts describe intended changes and timing. They contain no executable code. Add action types deliberately, with schemas, units, preconditions, and committed effects.

Proposal records move through `received`, `clarified`, `reviewed`, and `approved_for_simulation`. Work packages then move through `planned`, `scheduled`, `active`, `delayed`, `reduced`, `stopped`, or `completed`. Keep these records separate from the facility lifecycle below. Every version retains its sources, assumptions, outcome measures, dependencies, funding, capacity ramps, uncertainties, and stop conditions.

## Action catalog

The current executable catalog contains only a bounded `establish_service_site` action: a hypothetical municipal operator, a selected pinned location, a fixed grant and stock quantity, and explicit readiness, funding, delivery, commissioning, opening, and closure ticks for one scenario day. Every other action below remains a candidate. Each needs a versioned schema, units, preconditions, resource effects, timing, cancellation behavior, and committed events before use.

| Action | Required decisions | World effect | Economic effect |
| --- | --- | --- | --- |
| `establish_service_site` | **Implemented narrowly:** a pinned location, labeled hypothetical municipal operator, grant, stock, capacity, and strict stage schedule; it does not alter a listed provider | Adds a projected site with zero capacity until opening, then closes it at the scheduled tick | Transfers a scenario grant and settles full supplier procurement through `sim.core`; runtime shortages block launch and return unspent grant |
| `expand_facility` | Existing municipal or agreement-authorized partner facility, equipment, storage, service increment, installation needs, and capacity definition | Adds installed capability after readiness checks | Adds capital costs and operating obligations |
| `fund_program` | Source account, recipient, operator and program, authority agreement, amount, period, eligibility, and conditions | Authorizes a defined service scope; does not create stock or readiness | Records appropriation, commitment, and transfer as separate events |
| `set_municipal_price_policy` | Municipal operator, products or services, pricing rule, effective period, and subsidy limit | Changes the public operator's offer-generation rule | Changes settled receipts and any funded discount |
| `arrange_procurement` | Supplier, product, quantity, price, delivery schedule, storage, failure terms, and authorized recipient | Creates a supply commitment; stock becomes available after delivery | Reserves funds and settles under contract terms |
| `allocate_operating_resources` | Facility or program, staff and equipment pools, quantities, schedule, costs, and assignment authority | Allocates resources and changes available service capacity | Records modeled wages, rental, or other operating payments |
| `reduce_or_close_service` | City-run service or contracted scope, effective time, reason, pending users and contracts, and shutdown rules | Reduces or removes authorized capacity without deleting location or history | Releases eligible reservations and retains sunk costs and liabilities |

An existing food-support program can receive scoped funding, procurement, resources, and expansion of verified facility capability. A new program at an existing mapped location gets its own scenario ID and links to the location record. Do not duplicate the physical place. Route construction, new crossings, taxation, borrowing, private-market price controls, and new production technologies need separate mechanisms.

For each action, define whether values are absolute or incremental, the effective interval, and the difference between physical capacity and service throughput. Units distinguish storage grams, grams processed per shift, visits per operating day, portions, and simultaneous service slots.

## Facilities, stages, and simulator time

An operational facility records its facility ID, eligible location, access connection, operator, economic accounts, funding commitments, implementation status, installed equipment, storage, physical capacity, assigned staff, hours, eligibility, service rules, inventory, replenishment contracts, recurring requirements, capacity history, shutdown conditions, and parameter provenance. Food-support facilities also retain source location/program IDs, `PROGTYPE`, evidence states, and reviewed crosswalks.

Keep installed capacity, available capacity, and realized throughput separate. Available capacity respects binding staff, equipment, hours, and supply limits after converting them into compatible service units. Throughput follows actual interactions and may remain below capacity because demand is low or access is poor.

A typical facility lifecycle is:

`planned -> scheduled -> in_progress -> commissioned -> operational`

A rollout work package can complete while its facility continues to operate. Stages may also become `delayed`, `reduced`, `suspended`, `stopped`, `canceled`, or `closed`, with explicit resource effects. Commissioning establishes readiness but grants no public service. A separate operational milestone makes initial capacity available. Capacity ramps through later committed milestones.

Planning, procurement, and construction can appear on the map without providing service. Only a committed operational milestone changes capacity or makes a destination available to pedestrian choices. The visual layer is a projection of simulation state. A construction animation does not imply a modeled capacity or cost change.

Use integer simulation seconds against a scenario epoch for logical time. User-facing dates may use Toronto local time. The service advances to the next decision or physical event boundary. Browser playback speed changes presentation speed only. Use fixed durations for controlled comparisons. Declare uncertain duration ranges and evidence states, resolve stochastic durations from a versioned seeded stream, and persist each realized duration. Model delays explicitly; do not have an LLM improvise delays during execution.

The following timeline is illustrative. Its durations are not Toronto estimates.

| Period | Stage | Effect after commit |
| --- | --- | --- |
| Month 0 | Plan approved and scheduled | Timeline appears; service capacity stays at zero |
| Months 0 to 3 | Site readiness and procurement | Commitments and readiness are recorded; the site remains unavailable |
| Month 3 | Commissioning and opening | Initial capacity becomes available if funding, staffing, equipment, and supply checks pass |
| Months 4 to 9 | Capacity ramp | Later increments commit when their prerequisites pass |
| Month 9 onward | Operation | Residents can use the service; costs, reach, delays, and outcomes continue to be recorded |

Daily resident decisions continue during rollout. Compare both pre-opening and operating periods. Do not treat plan approval as the treatment start.

Project duration assumptions need operator evidence or an explicit scenario label. They do not set the software delivery schedule.

## Command validation and commits

The execution path is:

```mermaid
flowchart LR
    A[World and aggregate observations] --> B[Planning policy]
    B --> C[Typed action request]
    C --> D[Mandate and feasibility checks]
    D --> E[Atomic reservation and scheduling]
    E --> F[Due milestone checks]
    F --> G[Committed world and economic events]
    G --> H[Pedestrian and organization interactions]
    H --> I[Computed outcome measures]
    I --> A
```

The service performs these steps for each action:

1. Validate the schema, authorization, supported mechanism, units, targets, dependencies, and required inputs.
2. Revalidate affected sites, budgets, contracts, and resource calendars against current state. Ordinary pedestrian movement does not invalidate an unrelated construction plan because a global revision advanced. A material scope change requires renewed review.
3. Validate aggregate commitments so competing plans cannot overbook locations, funds, staff, equipment, or storage. Apply a recorded priority rule and deterministic tie-break.
4. In one durable commit, reserve resources, record acceptance, and enqueue milestones. A reservation is not an expenditure.
5. At each due time, recheck prerequisites and atomically commit infrastructure, economic, resource, and queue changes. Publish browser updates only after the commit.
6. Return or persist a receipt with committed effects or an explicit rejection or delay reason.

Repeating an identical command returns its prior receipt. Reusing its idempotency key with a changed payload is rejected. Reusing economic kernel commands does not make a multi-command milestone atomic. Validate the full transition before accepting it, then persist state, events, and queue updates together. After restart, reload the committed revision. An in-memory advance must not survive a failed durable commit.

Hard feasibility failures block execution. Conflicting evidence requires an explicit assumption or revision. Resolve preference tradeoffs using the approved objective or escalate them to a reviewer. Preserve alternatives, rationale, and unresolved dissent.

A delayed milestone records failed prerequisites, its next retry time or trigger, and its latest permitted completion time. Dependencies cannot bypass it. A mandate may allow bounded rescheduling; material revisions need review. A new plan version invalidates superseded milestones. They cannot activate later.

Cancellation releases only unspent, releasable commitments. Retain construction already paid for, consumed stock, and contractual liabilities. A reduction or closure defines what happens to active queues, pending trips, reserved purchases, inventory, and safe service shutdown.

## Outcomes, adaptation, and accounting

At declared decision times, provide a frozen snapshot of eligible sites, active and planned infrastructure, available funds and commitments, resource limits, supported actions, and computed outcomes. Include only information allowed by the experiment's observation policy. Household private details and future shocks are not automatically visible.

Useful aggregates include modeled food shortfall, completed and failed trips, reasons no choice was feasible, travel and queue times, capacity use, stockouts, deliveries, household spending, operator receipts, and public cost. Include group counts and distributions by permitted area, income, household size, and mobility. Distinguish attempted visits, unique households, eligible populations, and portions served. Unobserved demand remains unknown when the simulation does not record non-attempts.

Each measure defines its units, denominator, population, time window, evidence state, and provenance. Python computes measures. The planner interprets them and selects actions. Generated arithmetic is not authoritative.

Compare baseline and rollout by neighborhood and population group. Use the proposal's measures and relevant city outcomes. Keep household spending, public costs, service reach, food access, travel, capacity, and waste in their own units. Separate modeled trust, satisfaction, stress, or perceived access from observed survey evidence. Use verified active service in the baseline. When rollout delivery is unknown, report separate conservative and announced-capacity cases. Mark measures unavailable when the model lacks defensible inputs.

Planner actions may control authorized municipal funding, public price rules, procurement, infrastructure investment, and program operations. Effects on household spending, food obtained, service use, and operator revenue arise through actual transactions and interactions. Private operators retain their modeled decisions unless a supported contract or policy mechanism changes them. Do not infer employment, wage, competition, migration, inflation, or GDP effects without separate models and evidence.

Use integer cents, grams, and simulation seconds. Name counterparties for transfers. Record imports, transformations, consumption, and food losses. Do not count both a subsidy transfer and its downstream expenditure as consolidated public cost.

For an adaptive planner, record each observation, selected action, alternatives, reason, and model or rule configuration. Adaptation takes effect only through future valid milestones. Persist choices and stochastic draws so replay needs no new model calls. Declare review cadence and provider fallback rules before a run. Provider response time must not change simulated priorities.

## Review and display

The browser review view connects each plan to the city and its evidence. It shows:

- Candidate sites and planned, active, commissioning, operational, delayed, or stopped stages on a map.
- Existing food-support records, program types, candidate or verified status, and authorized intervention scope.
- Stage dependencies, time windows, current simulator time, and capacity ramps on a timeline.
- Costs, resources, expected outcomes, and feasibility results in declared units.
- Source links, source observation and update dates, retrieval times, freshness, assumptions, unknowns, disagreements, validation errors, and warnings beside each stage.
- Versioned approve, request-revision, and reject actions. Each decision records the reviewer, plan revision, and simulation revision.

Approval records a simulated decision. Python schedules and commits each state change. The interface displays the recorded reason when a milestone is delayed or fails.

## Events, checkpoints, and replay

Record versioned events for plan submission, validation, review, scheduling, stage start, milestone activation, capacity change, delay, reduction, stop or cancellation, and completion. Each event includes simulation time, run and plan revisions, stage ID, source and assumption references, and cause or prerequisite results.

Checkpoints preserve active stage state, pending milestones, realized duration draws, infrastructure capacity, resource reservations, and event sequence. Replay uses recorded choices and committed events without model calls. Baseline and rollout branches pin the same starting world and record plan and schedule differences.

## Implementation gates

| Gate | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 0. Proposal evidence | Versioned intent and outcome schema, freshness registry, proposal-time retrieval, immutable evidence bundle | Labeled fixtures cover relevant, irrelevant, missing, stale, unavailable, and conflicting evidence. Coverage labels, citations, snapshot IDs, and hashes are checked. Unknown or stale records cannot be labeled observed. |
| 1. Action contract | One site action, facility and operator schema, units, coverage record, and exact-plan or mandate authorization rules | Fixtures cover supported, missing-input, unsupported, and outside-mandate requests. Food-support actions require a reviewed crosswalk and explicit agreement scope. |
| 2. Transaction boundary | Resource reservations, deterministic event queue, and durable milestone commits | No partial money or capacity changes occur. Duplicate commands do not duplicate effects. Competing plans cannot overcommit resources. |
| 3. One site | Rule-based planner selects an eligible location, funds readiness, arranges supply, commissions, and opens service | No service is available before operation. Commissioning alone grants no capacity. The operational milestone creates a reachable legal option. |
| 4. Operations | Actual visits, service or purchases, replenishment, and recurring costs | Household, operator, stock, and public accounts reconcile. Unavailable staff or supply limits service. An existing partner program changes only under an explicit scenario agreement. |
| 5. Recovery and revisions | Delay, revision, cancellation, reduction, closure, checkpoint, resume, and replay | Obsolete milestones never activate. Sunk costs remain. Resumed and replayed state matches the recorded run. Failed transitions leave no partial effects. |
| 6. Review and evaluation | Map and timeline projections, matched baseline and rollout, fixed planning comparator | Displayed changes follow committed events and retain source and plan versions. Results cover the full horizon, delayed or no-launch cases, costs, access, shortfall, distribution, and adverse cases. |
| 7. Model planner | Model policy uses the same observations, mandate, action schema, and validator as the rule-based planner | Measure feasibility, unsupported-action attempts, outcomes, decision cost, and fallback frequency against the rule-based baseline. |

Do not add multiple departments, a broad action catalog, or reinforcement learning before the one-site proof passes. These gates are future acceptance criteria. They do not claim completed validation.

## Evaluation and open decisions

Define success measures and cost limits before comparing planners. Report the full rollout horizon, including pre-opening costs and delay or no-launch cases. Service effects begin at operational activation. Construction or funding may have earlier modeled effects. Report modeled food need, access failures, distribution, and public spending rather than one unqualified score.

The scenario catalog at `planning/scenarios.json` is a study registry, not an executable scenario file. Its grocery, food rescue/processing, and school-food entries are examples for open proposal intake, not an exhaustive action catalog. Confirm each proposal's intervention boundary and outcome measures before a study treats them as defined.

Freeze source snapshots, world package, population, schedules, product catalog, planner policy versions, and external shocks. The baseline uses verified active service where known. Represent unknown capacity with separate conservative and announced-capacity cases. Compare the same world, population, seed, and shocks under baseline and an approved plan. Include no-launch, delay, reduced capacity, and budget exhaustion. Measure intervention interactions explicitly:

```text
interaction = outcome(A and B) - outcome(A only)
              - outcome(B only) + outcome(baseline)
```

Do not infer a citywide effect from one active area. Report the modeled geography and population coverage. Choose the time horizon for the question. Pedestrian schedules unfold daily; infrastructure rollouts can span years. A single school day cannot establish annual school-service performance.

Pin the map, inputs, code, action semantics, mandates, and planner configurations. Use named random streams or frozen exogenous schedules so extra planner actions do not change unrelated shocks. Compare paired run seeds. Treat parameter uncertainty separately. Households and visits within one interacting world are not independent run replicates. Test stage delays, capital and operating costs, prerequisites, budget exhaustion, and stop conditions as sensitivity factors.

For adaptive planners, separate fixed-rollout evaluation from feedback-policy evaluation. Use development and held-out scenario conditions. Preserve planner versions and decision histories. These comparisons remain within-model until calibration and external validation support stronger claims.

Resolve these choices before Gate 1:

1. Which facility type and eligible locations form the first proof?
2. Which decisions require exact-plan review, and which may use a bounded mandate?
3. Which capital and operating assumptions, workforce and supply pools, and funding horizon are represented?
4. Which outcomes and tradeoffs define success, including subgroup constraints?
5. Which priority, retry, cancellation, and shutdown rules apply?

Implement the smallest supported action chain that answers these questions. Add packages, dependencies, and experiment infrastructure only when implementation shows a concrete need.
