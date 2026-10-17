# Consolidated simulation implementation

The planning documents and the user's October 17 revision govern this integration. A small inspectable model is an engineering checkpoint. It is insufficient as the finished current-world food simulator.

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

The last command executes 16 actual connected worlds. It is a smoke test, not the planned 16-by-30 final study. No full 480-run research batch is implicitly launched. The existing runner can enumerate 30 seeds, but the current one-day component model does not satisfy the planned multi-day or school-year studies.

For a nested procurement comparison, run the same policies and seeds in separate new directories with `--procurement decentralized` and `--procurement pooled`. Conditional drone studies additionally use `--conditional-drone-route`; retain a no-approval comparison.

Terminal exports contain state, events, decisions, settlement outcomes, household metrics, latent proxies, policy reports, logistics, and journey references. A manifest pins inputs and file hashes. `COMPLETE` is written last and hashes the manifest. `verify_export` rejects missing or changed files. Existing directories are refused, including interrupted runs. There is no refresh-in-place or automatic resumption.

The experiment executor creates a new world for every cell and seed, checks supplied shock hashes, and actually uses the district income/weather shocks. Unsupported parameters, outcomes, and live-provider modes fail explicitly. Sensitivity runs compare each treatment against a baseline at the same level and seed; baseline-only explicit studies report baseline sensitivity separately. The interval is a normal approximation for simulation variation, not a real-world confidence interval.

## Revision priorities and remaining gates

| Requirement | Current evidence | Next implementation gate |
| --- | --- | --- |
| Current economic data | Source register and illustrative snapshot only | Toronto API/resource downloads, Statistics Canada inputs, immutable raw checkpoints, dates/geographies/units, rejected-row reports |
| Real-world environment | Synthetic household and network records | Compatible observed controls, actual locations and routes, local basket measurements, held-out checks |
| Infrastructure planner | Not implemented | Structured site/cost/dependency/timing/capacity proposals with source IDs and deterministic rejection/revision |
| Implementation duration | Existing planning ranges, not official promises | Dependency schedule with operator evidence, uncertain delays, capacity ramps and no-launch cases |
| Policy impacts | Connected within-model mechanisms | Multi-product baskets, longer calendars, parameter studies, independent review and observed calibration |
| Human response | Choices and labeled latent proxies | Behavioral validation; real attitudes require a separate consent-based measurement design |
| Sims-like interface | Existing local frontend work remains separate | Reconcile one real exported transaction, then connect replay, comparisons and richer routines |
| Operational platform | Terminal exports only | Assigned backend owner, SQLite commits, restart/recovery, API, projection sequencing, gateway and charge reconciliation |

The frontend implementation guide defers backend ownership. This merge does not assign API, persistence, or provider transport to Person 2 by implication. These are explicit backend work items with an owner still to be assigned.

The one-day coordinator does not yet implement the complete six-phase production scheduler, durable process recovery, whole-world replay of pending logistics, a 30-day calibrated environment, the 1,000-household target, or renderer/headless hash parity. Terminal economic replay and deterministic completed-world checks are narrower evidence. Calendar seasonality, real-time procurement lead times, and held-out behavior remain release gates.
