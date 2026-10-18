# City Planning Agent Actions for Infrastructure and the Economy

## Status and purpose

Status: proposed design, not an implemented planner or a calibrated Toronto policy model. Action names, schemas, delegation rules, and validation gates below are specifications for future work.

Planning agents should be able to make decisions that change infrastructure and economic conditions inside a scenario. They select and coordinate supported actions; Python validates, schedules, and commits the resulting changes. An accepted action must eventually produce a recorded state change or a recorded failure, rather than ending as an unexecuted recommendation.

The initial proof is one municipal food site with a fixed funding envelope, staged opening, supply, operating costs, pedestrian use, and measured outcomes. Broader proposals remain admissible, but execution depends on implemented mechanisms and supported measures.

## Relationship to existing plans

- The [product plan](../PLAN.md#infrastructure-rollout-planner) defines department roles and structured work packages.
- The [planner and rollout interface plan](agent-planner-rollout-interface-plan.md) defines proposal intake, review, schedules, and milestone activation. This document specifies the action vocabulary and proposes an additional mode of delegation within an approved mandate.
- The [pedestrian interactables plan](pedestrian-interactables-plan.md) defines how residents use resulting facilities and services. Its interaction catalog does not define the planner's action space.
- The [dashboard plan](dashboard-implementation-plan.md) defines reporting. Planning agents consume computed measures through a bounded observation interface; dashboard rendering does not control execution.
- The [architecture](architecture.md#state-ownership-and-flow) retains Python as the sole authority for world state and economic transactions.

The existing rollout plan requires review of an exact plan revision. This proposal preserves that mode and adds mandate-based delegation as an explicit design extension. Delegation must be implemented and approved before it can replace review of individual work packages; it is not implied by the current interface.

## Current implementation boundary

The repository has a bounded Python food-access simulation and browser playback of generated interactions. The [interactables simulation](../sim/interactables/simulation.py) includes a synthetic six-hour scenario, queued events, and a temporary food intervention. It is not a general infrastructure planner or persistent world service.

The [economic command types](../sim/core/commands.py) already express transfers, reservations, purchases, food movements, processing, and consumption. The [kernel](../sim/core/kernel.py) returns accepted transitions or rejections. These are useful foundations, but they do not provide durable atomic commits spanning infrastructure, schedules, and economic state. The proposed facility actions, mandates, resource calendars, and adaptive planning loop remain future work.

## Responsibilities and authority

Keep three decision layers distinct:

| Layer | Responsibility | Authority |
| --- | --- | --- |
| Council/user | Define goals, acceptable tradeoffs, funding, and permitted scope | Approve an exact plan or a bounded planning mandate; approve material scope changes |
| Planning agents | Analyze conditions, select sites and interventions, allocate authorized resources, schedule and revise work | Submit typed action requests within their role and mandate |
| Python simulation | Validate commands, resolve contention, advance time, commit effects, and calculate outcomes | Sole writer of infrastructure, resources, policy state, and accounts |

A planning agent can cause a supplier payment or site opening through an accepted command. It cannot directly edit balances, declare a prerequisite satisfied, or make an unsupported mechanism executable.

Begin with one rule-based planning policy using this boundary. Department roles can later submit coordinated work packages through the same coordinator; separate agents are not required to prove the execution mechanism.

## Approved planning mandate

A mandate is a versioned authorization record containing:

- Run, proposal, mandate, and version IDs; reviewer and approval time.
- Objectives and outcome-measure IDs, including any priorities or tradeoff rules.
- Permitted action types, responsible roles, geography, and eligible site classes.
- Funding accounts, commitment limits, operating horizon, and any periodic spending limits.
- Bounds on capacity, prices, subsidies, staffing, procurement, and schedule revisions where applicable.
- Allowed scenario assumptions and their evidence labels.
- Review cadence, expiry, escalation conditions, and stop conditions.

Within an active mandate, an agent may submit compliant work packages without another human approval for each routine action. Python still checks every request and every milestone. A plan outside the mandate requires a revised authorization, not an agent-generated exception.

Revocation blocks new commitments and triggers the declared handling of pending work. It does not erase settled payments or automatically terminate existing services. Existing contracts, safe shutdown requirements, and outstanding liabilities remain recorded.

Exact-plan review remains available for controlled experiments and scenarios where autonomous revisions are outside the study design.

## Open proposals, supported actions, and evidence

Preserve any uploaded Markdown proposal as a versioned source. Produce a coverage record linking each requested change to supported actions, required parameters, dependencies, and measurable outcomes. Assess mechanism coverage and outcome coverage separately: opening a food site does not establish a model of its clinical health effects.

Use `supported`, `requires_parameters`, or `unsupported` for each requested mechanism and measure. An unsupported component prevents execution of the full scope. A supported subset may proceed only as an explicitly reviewed scope revision or an alternative already authorized by the mandate. Preserve exclusions and their consequences; do not report that subset as an evaluation of the entire proposal.

Parameter values may come from observed inputs, announced commitments, explicit estimates, or illustrative scenario assumptions. Preserve those evidence states and sources; unknown is not zero. Agents may propose an assumed capacity or cost within declared bounds, but cannot label it observed or use it to bypass resource requirements. An assumed future grant is not spendable cash until its modeled funding event occurs.

An eligible location and a new facility are different entities. A facility may receive a new stable scenario ID at a validated location. Source geography IDs remain unchanged. A genuinely new location or spatial footprint requires a supported geometry and access-validation operation; it cannot be fabricated as an existing mapped feature.

## Proposed action catalog

These are candidate domain operations. Each needs a versioned schema, units, preconditions, resource effects, timing, cancellation behavior, and committed events before use. They are not implemented tool names.

| Action | Required decisions | Infrastructure or service effect | Economic effect |
| --- | --- | --- | --- |
| `establish_service_site` | Eligible location, facility/operator type, access connection, schedule, funding, supply, and operating requirements | Creates a planned facility; later milestones make it usable | Reserves commitments and settles implementation and operating payments when due |
| `expand_facility` | Existing facility, equipment/storage/service increment, installation requirements, and capacity definition | Adds installed capability after readiness checks | Capital costs and changed operating obligations |
| `fund_program` | Source account, recipient/program, amount, period, eligibility, and conditions | Authorizes a defined service scope; does not itself create stock or readiness | Appropriation/commitment and actual transfer remain distinct |
| `set_municipal_price_policy` | Municipal operator, products/services, pricing rule, effective period, and subsidy ceiling | Changes the public operator's offer-generation rule | Alters settled receipts and any explicitly funded discount |
| `arrange_procurement` | Supplier, product, quantity, price/price rule, delivery schedule, storage, and failure terms | Creates a supply commitment; stock becomes available only after modeled delivery | Reserves funds and settles according to contract terms |
| `allocate_operating_resources` | Facility, staff/equipment pool, quantities, schedule, and costs | Allocates declared resources and affects available service capacity | Records modeled wages, rental, or other operating payments |
| `reduce_or_close_service` | Target, effective time, reason, pending users/contracts, and shutdown rules | Reduces or removes available capacity without deleting history | Releases eligible reservations; retains sunk costs and remaining liabilities |

Route construction, new crossings, taxation, borrowing, private-market price controls, and new production technologies require separate mechanisms. They are not automatically enabled by this catalog. A mandate authorizes supported operations; it does not implement missing ones.

For each action, document whether it requests an absolute value or an increment, the effective interval, and the difference between physical capacity and service throughput. Explicit units must distinguish storage grams, grams processed per shift, visits per operating day, portions, and simultaneous service slots.

## Facility and operator state

An operational facility needs more than a visual marker:

- Facility ID, eligible spatial location, access connection, and operator ID.
- Economic accounts, funding commitments, and implementation status.
- Installed equipment, storage, and physical capacity.
- Assigned staffing and equipment, hours, eligibility, and service rules.
- Inventory, replenishment/contract state, and recurring operating requirements.
- Capacity history, shutdown conditions, and provenance for parameters.

Keep installed capacity, currently available capacity, and realized throughput separate. Available capacity must respect all represented binding constraints, such as staff, equipment, hours, and supply; a common numeric minimum is meaningful only after converting those limits into compatible service units. Throughput follows actual interactions and may be below capacity because demand is low or access is poor.

Use a defined lifecycle such as `planned -> scheduled -> in_progress -> commissioned -> operational`. Here, commissioning establishes readiness and grants no public service by itself. A separate operational milestone makes initial capacity available. A rollout work package can complete while its facility continues operating. Delay, suspension, reduction, cancellation, and closure need explicit transitions and resource effects.

## Command and execution contract

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

Every action request carries schema/action versions, run and command IDs, an idempotency key, actor/role, mandate or exact-plan approval reference, plan/stage IDs, observation hash, relevant revisions, target IDs, parameters with units, evidence references, and timing requirements.

The service performs the following sequence:

1. Validate schema, authorization, supported mechanism, units, targets, dependencies, and required inputs.
2. Revalidate relevant sites, budgets, contracts, and resource calendars against current state. Normal pedestrian movement must not invalidate an unrelated construction plan merely because a global revision advanced. Material changes to reviewed scope require renewed approval.
3. In one commit, reserve required resources, record acceptance, and enqueue milestones. Reserving funds is not expenditure.
4. At each due time, recheck prerequisites and atomically commit that milestone's infrastructure, economic, resource, and queue effects. Publish browser updates only after commit.
5. Return or persist a receipt with committed effects or an explicit rejection/delay reason. Repeating an identical command returns the prior receipt; reusing its key with a changed payload is rejected.

Reusing existing kernel commands does not make a multi-command milestone atomic. Compute and validate the whole transition before accepting it, then persist its state/events and queue updates in one archive transaction. On restart, reload the committed revision. An in-memory advance must not survive a failed durable commit.

## Conflicts, delays, and revisions

Two plans based on the same snapshot may compete for the same location, funds, workers, equipment, or storage. Validate aggregate commitments, including overlapping time intervals. Record an explicit priority/allocation rule and deterministic tie-break before execution; model response order must not allocate scarce resources.

Hard feasibility failures block execution. Conflicting evidence requires an explicit assumption or revision. Preference tradeoffs are resolved by the approved objective/priority rule or escalated to the reviewer. Keep the alternatives, decision rationale, and unresolved dissent.

A delayed milestone records its failed prerequisites, next retry time or triggering condition, and latest permitted completion time. Dependencies cannot bypass it. Bounded rescheduling may occur within a mandate; material revisions need review. Version changes invalidate superseded pending milestones so they cannot activate later.

Cancellation releases only unspent, releasable commitments. Construction already paid for, consumed stock, and contractual liabilities remain. Reduction or closure specifies what happens to current queues, pending trips, reserved purchases, inventory, and safe completion of service.

## Economic mechanisms and limits

Planner actions directly control authorized municipal allocation, public price rules, procurement, infrastructure investment, and program operation. Their effects on household spending, food obtained, service use, and operator revenue arise through actual transactions and interactions.

Keep accounting consistent with the existing kernel: integer cents, grams, and simulation seconds; named counterparties for transfers; explicit imports, transformations, consumption, and losses for food. Budget authorization is not cash, inventory is not created by a funding announcement, and delivery commitments are not received stock. Do not count a subsidy transfer and its downstream expenditure twice as consolidated public cost.

Private operators retain their own modeled behavior. A city planner can change conditions they face or enter supported contracts; it cannot directly assign their prices or investment decisions without a separately defined policy mechanism. Employment, wage responses, competition, migration, inflation, and GDP effects require their own models and evidence. Recording an operating payment alone does not establish those wider effects.

## Planning observations and adaptation

At declared decision times, provide a frozen snapshot of eligible sites, active/planned infrastructure, funds and commitments, resource availability, supported actions, and computed outcomes. Expose only the information available under the experiment's observation policy; private household details and future shocks are not automatically visible.

Useful aggregates include modeled food shortfall, completed and failed trips, reasons for no feasible choice, travel and queue times, capacity utilization, stockouts, deliveries, household expenditure, operator receipts, and public cost. Include group counts and distributions by permitted area, income, size, and mobility strata. Distinguish attempted visits, unique households, eligible populations, and portions served. Unobserved demand must remain unknown where non-attempts are not recorded.

Each metric needs a definition, units, denominator, population, time window, evidence status, and provenance. Python computes these values. The planner interprets them and selects actions; generated arithmetic is not the authoritative metric pipeline.

Adaptive decisions must record the observation, selected action, alternatives/reason, and model or rule configuration. Adaptation only takes effect through future valid milestones. Persist all choices and stochastic draws for replay without new model calls. Declare review cadence and any provider/fallback behavior before a run so response latency does not change simulated priorities.

## First implementation and acceptance gates

| Gate | Deliverable | Required evidence |
| --- | --- | --- |
| 1. Contract | One site action, facility/operator schema, units, coverage record, and exact-plan/mandate rules | Supported, missing-input, unsupported, and outside-mandate fixtures have explicit outcomes |
| 2. Transaction boundary | Resource reservations, deterministic event queue, and durable milestone commits | No partial money/capacity changes; duplicate commands do not duplicate effects; competing plans cannot overcommit |
| 3. One site | Rule-based planner selects an eligible location, funds readiness, arranges supply, and opens service | No pre-opening service; commissioning alone grants no capacity; operational milestone creates a reachable legal option |
| 4. Operations | Actual visits, purchases/service, replenishment, and recurring costs | Household, operator, stock, and public accounts reconcile; unavailable staff/supply limit service |
| 5. Recovery and change | Delay, revision, cancellation, reduction, closure, checkpoint/resume, and replay | Obsolete milestones never activate; sunk costs remain; resumed and replayed authoritative state matches the recorded run |
| 6. Evaluation | Matched no-intervention baseline and simple fixed planning comparator | Report costs, access, shortfall, distribution, and adverse cases over equivalent horizons |
| 7. Model planner | Model policy uses the same observations, mandate, action schema, and validator | Feasibility, unsupported-action attempts, objective outcomes, decision cost, and fallback frequency are measured against the rule baseline |

Do not add a department team, broad action catalog, or RL training before the one-site proof passes. These gates describe required future evidence; no result is claimed here.

## Evaluation design and unresolved decisions

Define success and cost constraints before comparing planners. Report the full rollout horizon, including pre-opening costs and delay/no-launch cases; service effects begin at operational activation, while construction or funding may have earlier modeled effects. Include unmet modeled food need, access failures, distributional effects, and public expenditure rather than a single unqualified score.

Pin map, population, inputs, code, action semantics, mandates, and planner configurations. Match baseline and intervention external conditions. Use named random streams or frozen exogenous schedules so a planner's extra actions do not silently change unrelated shocks. Estimate policy differences across paired run seeds; parameter uncertainty is a separate sensitivity dimension. Households and visits within one interacting world are not independent run replicates.

For later adaptive planners, distinguish evaluation of a fixed rollout from evaluation of a feedback policy. Use separate development and held-out scenario conditions; preserve planner versions and decision histories. These are within-model comparisons until calibration and external validation support stronger claims.

Resolve the following before coding gate 1:

1. Which facility type and eligible locations form the first proof?
2. Which decisions require exact-plan review, and which may be delegated?
3. What capital and operating assumptions, workforce/supply pools, and funding horizon are represented?
4. Which outcomes and tradeoffs define success, including subgroup constraints?
5. What priority, retry, cancellation, and shutdown rules apply?

Implement the smallest supported action chain that answers those questions. Keep this plan in `docs`; defer new packages, dependencies, and experiment infrastructure until implementation demonstrates a concrete need.
