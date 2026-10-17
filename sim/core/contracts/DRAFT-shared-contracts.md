# DRAFT shared contracts

Status: **DRAFT** for review by Person 2 and by the owners of `sim.policies`, `sim.logistics`, `sim.behavior`, and `sim.experiments`.

Kernel version under discussion: **0.1.0**. Event, catalog, and scenario schema versions are **1**. Typed records live in `sim.core.contracts` and the command and event modules exported from `sim.core`. This note is not a second schema. If a sentence here disagrees with the code, the code is what version 0.1.0 does, and the disagreement is one of the open questions below.

## What is proposed

### Units

- Money is integer Canadian cents. Food mass is integer grams. Time is integer simulation seconds. Length, when a caller records it, is integer metres.
- Booleans are not integers. Floats are refused.
- Keys that contain `dollar` are refused in the catalog and in district inputs. A price coefficient is stored as points per 100 cents.
- `price_base_month` is null. Presentation in real dollars must not rewrite the ledger.

### Scenario and catalog

- A runnable scenario names a catalog id, a catalog SHA-256, a run id, and integer opening amounts. `sim/core/data/fixture_scenario.json` is the literal accounting fixture. `planning/scenarios.json` is a planning catalog, not an executable file.
- The district snapshot header points at planning scenario `baseline` / `observed_service_with_explicit_unknowns` with `enabled: []`.
- The frozen catalog id is `sim6ix-basket-v1`. Product ids, recipe ids, and actor ids match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$`.

### Command

A command is an intent. `apply_command(state, command)` returns a `Transition`:

- `accepted`: new state and one or more events
- `rejected`: the same state object, no events, a stable `reason` from `REJECTION_CODES`
- `duplicate`: the same state object, no events, reason `duplicate_command`

The caller supplies `command_id`. The kernel mints reservation ids `rsv.{command_id}`, child lots `{lot_id}.{command_id}`, and process outputs `{lot_id}.{command_id}.out`.

Phases are integers 1 through 6: policy, expiry, arrival, choice, settle, consume. Within one second the phase may not move backwards. A later second may use an earlier phase.

### Event envelope

Each committed event has `schema_version`, `run_id`, `event_id` (`{run_id}:{sequence}`), `sequence`, `second`, `phase`, `kind`, `causes`, `command_id`, and `payload`.

Payloads are patches: `accounts_set`, `lots_set`, `reservations_set`, `journal_appended`, `movements_appended`, `choices_appended`, and a closing `command_recorded`. `movements_appended` carries the absolute gram counters. `fold_events` writes those values. It does not reprice a basket or recompute a yield.

`state_from_json` refuses a schema other than 1, a kernel version other than 0.1.0, and a body that fails conservation.

### Scene snapshot

`SceneSnapshot` is the economic projection: schema version, run id, scenario id, sequence (`next_sequence - 1`), second, phase, state hash, accounts, lots, reservations, and the gram counters. It has no meshes, camera, or interpolation fields.

### Choice offer and receipt

`ChoiceOffer` has a decision id, household id, revision, known facts, and feasible options (option id plus a short summary). `ChoiceReceipt` has the decision id, chosen option id, origin (`rule`, `llm`, `recorded`, `fallback`), observation hash, and an optional explanation of at most 400 characters.

`RecordChoice` appends a `ChoiceRecord` and moves no money and no food. The district baseline submits origin `rule`.

### Metric units

`Metric` values use `cad_cents`, `grams`, `sim_seconds`, `metres`, or `count`. `paired_difference` rejects a name or unit mismatch. `funded_discount`, `cash_before_subsidy`, `cash_funding_gap`, and `operating_result` are reporting helpers. They do not post journal lines.

### Conservation the reducer checks

- Sum of settled cents, including the external contra account, is 0.
- Each journal entry sums to 0, and settled cents match the journal.
- Spendable cents (`settled - reserved`) stay non-negative unless `allows_credit` is set. Only `kind: external` may allow credit. Credit accounts cannot hold reservations.
- Food: imported + added = on hand + consumed + loss + exported. Loss kinds are `process_loss` and `waste`.
- Acquisition cents: introduced = recognized (consume, process loss, waste) + acquisition still on lots.
- One reservation may bind cash and stock together. A purchase releases that reservation, posts the actual cents, and splits the lot.
- Largest-remainder ties break toward the smaller key. Lot splits use the keys `keep` and `take`, so a tied cent stays on the kept lot.
- A process command states edible grams and loss grams. Those grams plus any added material must equal the input. The kernel does not look up a recipe.

### District baseline that already uses this surface

- 250 households, population generator `district-pop-1`, population seed 17. The run id is `baseline-{seed}`.
- Seven local days, 2026-10-19 through 2026-10-25, each 86400 simulation seconds, timezone `America/Toronto`, epoch `2026-10-19T04:00:00Z`.
- Shopping uses `RecordChoice`, `ReserveResources`, `PurchaseLot`, and `ConsumeFood`.
- The quality report is complete only when margins, assignment, conservation, reservations, rejections, spending, stock, and travel all agree.

## Open questions

1. Duplicate commands. The kernel returns status `duplicate` and no events. It does not keep the earlier payload on the state. Should the store return the prior commit receipt, and is that receipt outside the kernel?
2. Canonical JSON (sorted keys, compact separators, UTF-8, SHA-256) is the proposed wire encoding for states and events. Confirm the API will not invent a second encoding.
3. `SceneSnapshot` is economic only. Person 2 can wrap it for a checkpoint or a projection. Meshes, camera, and interpolation stay in the client. Is that wrap a new type, or is this snapshot stored as-is?
4. `RecordChoice` is in the kernel and moves no money or food. The behavior package submits it. LLM transport, prompts, and charge reservations stay outside. Explanation max is 400 characters. Is that the receipt the gateway should persist?
5. The caller supplies command ids. The kernel mints `rsv.{command_id}`, `{lot_id}.{command_id}`, and `{lot_id}.{command_id}.out`. Should any other id be minted by the store?
6. One reservation may bind cash and stock together. Policies that want two independent holds would submit two commands. Is that acceptable?
7. Phases 1–6 are enforced per command. Policy activation, journeys, and school meals are commands other packages submit. The kernel does not run those handlers. Which package owns a same-second decision barrier?
8. One cash account per actor. Credit is only the external opening contra. A real credit limit would be a version bump. Is the external contra the account Person 2 should show as "outside the district"?
9. Opening cash is a balanced transfer from `acct-external-opening`. Replay from an empty state includes those events. A mid-run checkpoint is valid when its hash matches and the kernel version matches. Should the store also require the catalog SHA-256?
10. The economic hash is SHA-256 of the canonical state JSON. It includes the kernel version and the run id. It excludes wall-clock time. Is that the hash the client displays?
11. Largest-remainder ties go to the smaller key. Lot splits use `keep` and `take`, so a tied cent stays on the kept lot. Should a published split show both the rule and the cents?
12. Process commands must state edible and loss grams that add up. `split_mass_by_ratio` is for callers. The kernel does not silently apply a recipe. Should a logistics or policy package be required to cite the recipe id on the command in a later version?
13. `funded_discount` is the capped-subsidy price rule. Policy code should call it and submit the resulting cents. The API should not recompute a second price. Is the unfunded remainder reported only as a metric?
14. Schemas are version 1. `state_from_json` refuses a different kernel version. There is no migration. Is a hard refusal the store's behavior as well?
15. Other packages import `sim.core` only, not submodules. District code follows that rule. Should the same rule be a test in each package?
16. `price_base_month` is null. Real-dollar presentation must not rewrite the ledger. Where should a display conversion live if a later study needs one?
17. `seeded_admission_order` is provided. The kernel does not reorder a batch. The district baseline shops households at distinct seconds so each sees remaining stock. A same-second frozen decision barrier belongs to the behavior package. Does that package own the barrier, with this baseline remaining sequential?
18. The baseline purchase settles custody immediately and reports travel beside it. Logistics can later separate reserve and arrival with the existing `ReserveResources`, `PurchaseLot`, and `TransferLot` commands. Confirm that split before adding a journey field to purchase.
19. Population quotas are illustrative, generator `district-pop-1`, not Census. The joint distribution is a stripe across exact margins. A calibrated population should be a new snapshot id, not an edit of these files.
20. Catalog storage-life seconds are descriptive. Lot `unsafe_after` is what the kernel enforces. Should opening stock derive `unsafe_after` from the catalog automatically, or should the snapshot keep setting it explicitly?
21. The baseline municipality opens at 0 cents because no operating appropriation is assumed. A later policy package funds it with an explicit transfer. The toy subsidy in `sim.core.examples` is not that policy.
22. Policy fixtures post the existing kernel commands. A till subsidy is a `TransferCash` with memo `price_subsidy`, and an operating subsidy uses memo `operating_subsidy`. There is no `policy_activated` payload. Should Person 2 treat those memos and command ids as the audit keys, or is a dedicated event required?
23. `operating_result` in the grocery fixture counts household cash as sales and counts every public transfer once in the subsidy term. The list price is not also added. Confirm that this is the viability split the API should display.
24. School meals are `ConsumeFood` by the school actor plus a `RecordChoice` for the pupil. The pupil does not receive a lot. Confirm the client should animate the meal from that pair rather than from a household purchase.
25. A van trip is two `TransferLot` commands. Departure keeps the shipper as owner and sets `journey_id`. Arrival clears the journey and can change the owner. `available_grams` still includes a travelling lot. This package does not offer it for sale. Should the client animate `journey_id` on the lot, and should a later kernel version exclude travelling grams from availability?
26. `ChoiceOffer` and `ChoiceReceipt` are the DRAFT records the gateway should exchange. This package does not open a socket or reserve a provider charge. `ResolvedChoice.reason` sits beside the receipt because the receipt has no reason field. Should a later schema add that reason, plus tokens and a charge reservation, without putting them in the economic hash?
27. `not_selected_for_live_barrier` means the household was not in the predeclared four-seat slice. It is not a timeout and not a refusal. The gateway should not retry it.
28. Drone corridor eligibility is a scenario flag in `run_drones`. It is not a Transport Canada decision and not a permission to draw a flight path. Cost per completed order is integer division of allocated cents, plus a remainder so the report does not use a float. Unserved orders stay out of the denominator. Should the client show the remainder beside the average?
29. The screening report declares 480 planned runs and executes 16 cells at the seeds it is given. It does not re-simulate the 250-household week inside every cell. A full replication would be a later run budget. Person 2's export can store the report object; this package does not open a database.
30. Animation cues are a projection of `command_recorded` events with stable command-id prefixes (`q-`, `depart-`, `arrive-`, `buy-`, `batch-`, `serve-`). They are not a second ledger. Confirm those prefixes are enough for the client, or say which dedicated event kinds are still required.
