# Consolidated simulation implementation

The active product scope is the Council proposal flow, proposal-specific organization behavior, actual stakeholder evidence, and a persistent simulation. The local Python Council API implements exact Markdown intake, review records, proposal-linked organization and stakeholder-input records, three bounded municipal-service actions, and stored paired traces. The browser supports proposal intake and those records, and displays actor references on saved rollout events; the Simulation tab exposes scope, plan, decision and run controls. The six-hour scenario remains illustrative and is not a persistent multi-day world. This document also records the separate legacy economic vertical slice and its boundaries.

## Browser pedestrian food-access day

The browser now replays bounded runs exported by [`sim/interactables`](../sim/interactables/README.md). That executor routes one resident per household on the browser map, generates deterministic legal choices, and commits retail purchases, food support, school portions, supplier replenishment, and home food use through the public `sim.core` API. An optional emergency-site scenario records a city grant, paid stock delivery, explicit service capacity, activation, and closure. Its dashboard and inspectors read committed event projections at the current playhead; seeking and camera actions never settle transactions.

This is a separate six-hour illustrative scenario, not a connection to the legacy `sim.integration` run or a persistent evolving world. Site locations and operating values are scenario assumptions. It provides the initial [pedestrian interactables](pedestrian-interactables-plan.md) while broader department coordination, multi-day state, and empirical calibration remain open.

## Bounded Council workflow

`sim.council` stores a single local Council session in SQLite. It preserves submitted Markdown byte-for-byte as text, records recognized section spans and unclassified text, labels citations unverified, and pins the proposal to the location snapshot used for planning. It stores immutable organization revisions and append-only stakeholder-input records with evidence labels, geography, reach, consent limits, missing groups, conflicts, and optional source links. Plans freeze record IDs and hashes; rollout events identify the organization records linked to each stage. These references are contextual: organization choices do not yet respond to proposals, and the input form neither conducts consultation nor verifies representativeness. The API also supports saving a narrower scope, selecting `establish_service_site`, supplying labeled parameters, and recording approve, request-revision, or reject against the exact proposal, scope, plan, and world hashes. Unsupported actions cannot be approved. The browser Simulation tab includes these controls, the capability catalog, saved parameter review and explicit blockers. Department-style finance, readiness, supply, and access notes are deterministic advice with no authority to schedule or spend.

The executable actions establish a hypothetical municipal food site, expand its absolute operating-day visit limit, or reduce/close its service during one six-hour scenario. Capacity actions compare the same base site in both arms and commit only the intervention capacity change at its approved tick. They assume spare capability and do not add stock, capital assets or staffing. Broader funding, procurement, resource, road/transit, housing and utility entries remain proposal-only candidates; they cannot be approved. See the action contract in [the planner plan](agent-planner-plan.md#action-catalog). The plan pins population, seed, map, catalog, location snapshot, a content hash of the Python simulator inputs, and the organization/stakeholder record hashes available at planning time. Baseline and intervention are separate same-population, same-seed runs. Readiness, funding, supplier delivery, commissioning, opening, and closure appear as committed rollout events. Money and stock changes pass through `sim.core`; a runtime shortage produces a no-launch, returns unspent grant funds, and leaves service capacity at zero. This is a bounded scenario comparison, not persistent City state, observed operations, evidence refresh, or real authorization. It does not yet model proposal-specific incumbent-business responses or conduct stakeholder consultation.

The loopback API is `GET /api/council`, mutation routes under `/api/council`, and exact stored traces under `/api/council/runs/{run_id}/traces/{arm}`. Commands require schema version 1, an expected revision, and an idempotency key. Successful command receipts, immutable workflow records, and paired trace JSON survive a service restart. See the [local app guide](../apps/web/README.md) for startup and the [planner plan](agent-planner-plan.md) for future extensions.

## Why the prototype says school day

The phrase comes from the connected Python integration fixture, not from a Toronto school-calendar dataset or a measured Toronto routine.

- [scenario.py](../sim/integration/scenario.py) builds one illustrative district run. Its participation draw fixes `day=0`, school portions settle at simulation second `28000`, shopping starts at `36000`, and household consumption is evaluated at `72000`. The export input is explicitly labeled “one synthetic school day; produce component only.”
- [__main__.py](../sim/integration/__main__.py) sets the study window to “one synthetic school day.” [export.py](../sim/integration/export.py) repeats the limitation in each run manifest.
- The [Connected district day section](#connected-district-day) documents the same fixture: synthetic school service, one day of household budget, shopping, and delivery.
- The previous `PLAN.md` and roadmap made that fixture the initial demonstration. This was a product-story choice layered on top of the existing code, not a requirement established by user research or data.

The daily fixture appears to have been an engineering convenience for connecting school meal accounting, procurement, household shopping, and logistics in one small run. The current plan keeps it as an economic regression scenario. It makes Toronto, pedestrian movement, open proposal intake, coordinated department roles, and ongoing staged planning the product frame.

## Selected contributions

| Source | Pinned head | Retained | Excluded |
| --- | --- | --- | --- |
| PR #3 | `d89b7e488dcfb9e703eefcfbf37f442412eb3504` | Kernel, units, conservation, event replay, frozen district inputs, population, network, regression baseline | Competing policy, behavior, logistics, and experiment packages; prescribed screening outcomes |
| PR #2 | `85926e1428b32883073210f351b375f32e0bcc4f` | Grocery funding and pricing, rescue/processing, school portions, pooled/decentralized procurement, adverse fixtures | In-memory adapter as an authoritative runtime; it remains a test reference |
| PR #4 | `b791fe035549085e5f50d63c4217cbbd6e421766` | Queues, carriers, drone eligibility and fallback, unit-bearing metrics, animation events | In-memory logistics core as an authoritative runtime; it remains a test reference |
| PR #1 | `2688becf1e6401bd380c126f046b6e562c0281a1` | Legal offers, utility baseline, knowledge restrictions, bounded provider interfaces, latent proxies, replicated runner | Any implication that a provider, infrastructure planner, or observed calibration is implemented |

`sim/integration/ledger.py` implements both ports by submitting typed commands to `sim.core`. An isolated multi-command policy candidate is discarded entirely on failure. There is one ledger; test references cannot independently settle the connected run.

The original seven-day `sim.district` baseline remains a regression benchmark. It has its original simplified, immediate household settlement and does not execute policy combinations. Use `sim.integration` for the connected policy comparison.

## Current contracts

Kernel version is **0.2.0**, event schema **2**. The state body retains schema 1 with a required kernel-version pin. Version 0.1.0 states are rejected. Provenance on food lots and non-mass losses are replayed. The updated regression hash reflects the new version and record shape, not retuned baseline outcomes.

Core commands and settled `ChoiceRecord` values remain economic records. There is one household offer/receipt schema, `sim.behavior.draft`, currently version `0-draft`. The incompatible duplicate proposal from PR #3 was removed. There is no public service compatibility promise for these draft offers. `SceneSnapshot` is a read-only economic projection.

Policies keep integer cents and grams. Logistics sees integer scenario seconds and local metres. The adapter explicitly maps catalog `refrigerated` storage to logistics `chilled`; it does not silently equate arbitrary storage classes. Routing for the new municipal candidate uses its declared synthetic area plus an explicit access-time parameter. This is not a measured site.

Food in transit is unavailable to purchases, consumption, processing, and further reservations. A travelling lot requires a declared arrival or its matching whole-lot holder to change custody. Ownership changes after physical arrival. Food that expires before collection is a failed delivery; it is not transferred to the recipient.

Processor shifts and procurement contracts require funding for their declared input and operating commitments before production or distribution. Store price support is a finite authorization derived from an actual public transfer. Failed purchases do not consume that authorization. A mismatched provider reservation ceiling is rejected before dispatch; maximum reservations round upward.

## Connected district day

The active run builds the frozen 250-household population. Smaller smoke configurations select actual, evenly spaced records from that roster and export their IDs. They do not use weights or claim to reproduce all population margins.

1. Allocate explicit synthetic public and household budgets. Household budgets represent one seventh of the regression week's allowance, with the declared matched income shock.
2. Preserve a baseline food-bank donation. Processing can use separate surplus, never that donation. Unprocessed extra surplus is written off under an explicit illustrative baseline assumption.
3. Assign processed output and procure the remaining school ingredients. Compare separate and pooled procurement at the same target demand; procurement mode is independently configured.
4. Deliver school stock through the logistics engine and actual kernel custody. Drones default to no approval with ground fallback. Conditional routes are scenarios, never flight permissions.
5. Prepare portions under eligibility, participation, attendance, stock, and kitchen limits. Existing synthetic active-school assignments form baseline eligibility. Expansion broadens eligibility. Absences produce waste, not served portions.
6. Open a funded municipal-store candidate when enabled. Generate household offers from actual stock, cash, network collection time, capacity, and current price rules. Routine choices use PR #1's utility policy.
7. Reserve distinct stock pieces and maximum cash in a matched, seeded admission order. Settle at recorded collection times. Recheck stock and municipal price support; an increased price beyond the held maximum cancels the purchase. Selection and settlement outcome remain distinct records.
8. Record consumption, shortfall, public cash flows, and explicitly illustrative latent responses. Release all remaining reservations and verify kernel replay before exporting completion.

The source population's `daily_need_grams_per_person` remains the illustrative target. Only produce is currently modeled. These targets and portions cannot establish nutritional adequacy, complete diet quality, hunger prevalence, or clinical outcomes. Household shopping rounds to 100 g catalog units. Non-food essentials are not settled, so the latent proxy's financial-strain component is explicitly disabled rather than presented as observed zero strain.

`household_payment_cents` is realized expenditure. It is not a fixed-basket price. `unmet_grams` is the declared produce-component shortfall after actual home and school consumption. Household spending can rise when a policy makes more food affordable. Report both quantities.

`fiscal_outlay_cents` is the change in consolidated public cash: public purchases and capital payments less household receipts at the public store. Internal transfers between the municipality and programs cancel. `subsidy_transfer_cents` separately records the store grant. A grant, its downstream supplier payment, and the household's discount must not be added as three resource costs.

## Commands and exports

From the repository root after installing `.[test]`:

```powershell
python -m pytest -q
python -m sim.integration run --households 250 --seeds 17 --policies groceries processing school drones --out outputs/district-17
python -m sim.integration paired --households 250 --seeds 17 18 --policies groceries --out outputs/grocery-pair
python -m sim.integration screening --households 12 --seeds 17 --out outputs/screen-smoke
```

The last command executes 16 actual connected worlds. It is a smoke test, not a research result. The former 16-by-30 batch belonged to the superseded food-policy plan. The current one-day component model cannot represent a staged multi-year rollout or establish annual school-service effects.

For a nested procurement comparison, run the same policies and seeds in separate new directories with `--procurement decentralized` and `--procurement pooled`. Conditional drone studies additionally use `--conditional-drone-route`; retain a no-approval comparison.

Terminal exports contain state, events, decisions, settlement outcomes, household metrics, latent proxies, policy reports, logistics, and journey references. A manifest pins inputs and file hashes. `COMPLETE` is written last and hashes the manifest. `verify_export` rejects missing or changed files. Existing directories are refused, including interrupted runs. There is no refresh-in-place or automatic resumption.

The experiment executor creates a new world for every cell and seed, checks supplied shock hashes, and actually uses the district income/weather shocks. Unsupported parameters, outcomes, and live-provider modes fail explicitly. Sensitivity runs compare each treatment against a baseline at the same level and seed; baseline-only explicit studies report baseline sensitivity separately. The interval is a normal approximation for simulation variation, not a real-world confidence interval.

## Revision priorities and remaining gates

| Requirement | Current evidence | Next implementation gate |
| --- | --- | --- |
| Current economic data | Source register and illustrative snapshot only | Toronto API/resource downloads, Statistics Canada inputs, immutable raw checkpoints, dates/geographies/units, rejected-row reports |
| Toronto 3D world | Frozen, attributed Toronto geometry and a walking graph are used by the browser and bounded food-access traces | Expand source coverage and connect validated geography to a persistent world service |
| Policy impacts | Connected within-model mechanisms | Multi-product baskets, longer calendars, parameter studies, independent review and observed calibration |
| Human response | Choices and labeled latent proxies | Behavioral validation; real attitudes require a separate consent-based measurement design |
| Pedestrian agent layer | Existing choices are deterministic household shopping rules | Add resident positions, paths, schedules, mobility constraints, and rule-driven movement before small-model or LLM calls |
| Operational platform | The Council workflow has local SQLite command receipts, immutable paired traces, and a loopback API; `sim.integration` still uses terminal exports | Persistent world state, checkpoints, ordered world events, broader API recovery, gateway and charge reconciliation |

Planner design, authority, and staged activation gates are documented in the [agent planner plan](agent-planner-plan.md).

The legacy one-day `sim.integration` coordinator does not implement the proposed world clock, pedestrian movement, durable process recovery, whole-world replay, or renderer/headless hash parity. The Council service persists its bounded run records and replays stored traces, which is narrower evidence than a recoverable world. Route coverage, operating data, model behavior, and held-out validation remain open.
