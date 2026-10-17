# Policy mechanisms

Weeks 6 to 8 of the neighbourhood model: municipal groceries, food rescue and processing, school meals, and pooled procurement. Each mechanism changes one declared rule, posts the resulting cents and grams through a ledger, and returns its costs as separate fields.

This package does not own accounts, persistence, replay, the HTTP API, the 3D client, or the LLM gateway. Those belong elsewhere. `sim/core` is the future owner of settlement. Until it is wired in, `core_interface.InMemoryCore` is a small adapter that implements the same operations.

Run the fixtures from the repository root:

```bash
python -m unittest discover -s sim/policies/tests -t .
```

The tests use integer cents and grams only. Expected balances are written out in the tests. Running the same command on the same opening state returns the same result. Nothing in this package reads the wall clock or draws a random number.

Parameters on the fixtures are `illustrative`. They are not Toronto shelf prices, yields, or program costs. Announced city and agency figures stay in the planning documents and are not copied in as defaults.

## Ledger seam

Policies call `CoreLedger`. They do not import `sim.core`.

| Operation | Rule |
| --- | --- |
| `endow` | Opening cash comes from `external:opening`. That source may be negative. Every other account must stay spendable at zero or above. |
| `transfer` | One balanced cash movement. A zero amount does nothing. |
| `open_lot` | Opening inventory. Book value can be nonzero without a cash movement in this window. |
| `buy_lot` | Pay the supplier and import the same number of cents as the lot's acquisition value. |
| `add_material` | Recipe water or ingredients. Grams are added mass, not an import and not free food created inside a yield. |
| `take` | Move `acquisition * grams // lot_grams` cents. Remainder cents stay on the source lot. |
| `reserve_lot` | The whole lot, one destination. A second reservation fails. Releasing an inactive reservation fails. |
| `replace_lot` | Output grams and acquisition cents must equal the input lot. Waste recognizes acquisition once and does not post cash. |
| `write_off`, `consume` | Remove grams and recognize acquisition. They are not cash expenses. |
| `recognize_non_mass_loss` | Cents already paid for grams that never arrived. No second cash movement and no imaginary inventory. |

The mass identity is:

```text
opening + imported + added = on hand + consumed + waste + exported
```

Cash across every account, including `external:opening`, sums to zero.

Largest-remainder allocation breaks ties by key ascending. Lot splits do not use that method; they use the floor rule above so the last grams carry the leftover cents.

## Municipal groceries

`apply_grocery` runs one store cycle.

1. The store stays in `planning` unless funding, a site, and an operator are all present. Planning posts nothing.
2. The municipality transfers the operating subsidy once, limited by its spendable cash.
3. Price support is an authorization capped by the subsidy that actually arrived. It is not a second transfer.
4. Capital, then overhead. Each is all or nothing.
5. The purchase order waits entirely when spendable cash minus the minimum reserve cannot cover it.
6. Shoppers are served in `(admission_rank, household_id)` order. A trip beyond the time budget does not take stock. A basket that does not fit in stock or cash is refused whole.
7. Under `subsidized_below_cost`, the household pays the target price only while the remaining authorization covers `acquisition - target`. Otherwise the price returns to acquisition cost.
8. Spoilage writes off grams and recognizes acquisition once. A disposal fee is a separate cash payment.

The result reports the simulation spec's two store views, which are allowed to differ:

```text
cash_before_subsidy = sales - inventory payments - other operating cash
cash_funding_gap = max(0, minimum reserve - opening store cash - cash_before_subsidy)
operating_result = sales + subsidy - cost of food sold - writeoffs
                   - labor - occupancy - energy - logistics - disposal - other overhead
```

`external_resource_cents` is inventory payments plus overhead and disposal actually paid. The subsidy is not added to that resource cost. Fee relief is forgone municipal revenue and does not move cash. Capital is reported on its own line.

The main fixture gives the first household the subsidized price and the second household the at-cost price after the 150-cent authorization is exhausted. A second fixture leaves the store in planning. A third delays procurement, records fee relief, and separates a time-budget miss from a stockout. A fourth spoils unsold stock.

## Rescue and processing

`apply_processing` runs one shift. Callers reserve baseline donations before this runs. Reserved lots are skipped even when they expire sooner than the food the processor takes.

1. Buy the farm inputs the processor can pay for. Unpaid purchases are counted and not invented.
2. Skip reserved lots, then expired lots. Accept the rest earliest-expiry first, then by lot id, up to shift capacity.
3. Apply transport loss. Added water, if any, joins the batch only in `process` mode.
4. `process` splits each accepted portion into edible output and process loss. Edible grams are allocated across portions by largest remainder, and each portion's acquisition cents follow its own edible and loss grams. `direct` keeps the same product and skips the recipe.
5. Deliver earliest-expiry edible lots up to demand.
6. Cold storage applies only to edible output still at the processor. Raw input that did not fit in the shift is not spoiled to meet that cap.
7. Labor is paid when food was accepted, and also when the shift is idle if `pay_labor_if_idle` is set. Transport is paid only when food was accepted. Each payment is all or nothing.

`operating_cents` is transport plus labor. Purchased-input cash is separate, so a rescued gram is not given the farm price. `unit_cost_defined` is false when delivered grams are zero. Rescued and purchased grams stay in `accepted_by_class` and `edible_by_class`.

The main fixture keeps a 200-gram reserved donation, fills a 1000-gram shift with 800 rescued grams and 200 purchased grams, yields 750 edible grams, delivers 500, and spoils 50 because cold storage holds 200. Direct redistribution of the same 800 rescued grams delivers more food at a lower operating cost than processing. An expired lot produces no food and still pays idle labor.

## School meals

`apply_school_day` plans meals for pupils who are eligible, participating, and menu-compatible, in `(admission_rank, pupil_id)` order. The number prepared is the minimum of candidate count, kitchen capacity, portions the program can pay for, and portions already on hand. Every limit that equals that minimum is listed in `binding_constraints`, in the order capacity, budget, food, demand.

A present pupil eats the portion minus plate waste. An absent pupil's prepared portion is absence waste and is not eaten. The program account pays the supplier. The household account does not.

`replaced_grams = min(need, school grams eaten * substitution_numerator // substitution_denominator)`. Substitution may be zero. `settle_home_purchases` buys the residual need from a store, in household-id order. Cash saved on that smaller basket is reported next to program ingredient cost and is not treated as the same number. A home purchase that does not fit in stock or cash does not count as savings.

The main fixture prepares two meals, serves one, wastes the absent pupil's meal, and leaves a later pupil unserved because the kitchen is full. Household cash savings are 90 cents. The program pays 160 cents. The budget fixture can fund only one meal, assigns it to an absent pupil, and leaves the next present pupil unserved.

## Pooled procurement

`run_decentralized` and `run_pooled` are counterfactual arms. Give them separate ledgers. Both size the order as the smallest integer that would meet the target after the expected receipt ratio and the storage-loss ratio. The actual receipt ratio is applied when the goods arrive, so a short delivery does not change the order that was already placed.

The price band is the highest threshold the ordered quantity meets. Cents are `grams * cents_per_1000g // 1000`. An order below the contract minimum posts nothing: no food, no hub fees.

Delivered grams are imported. Missing grams are not. Cash paid for the missing grams is a supplier transfer plus `recognize_non_mass_loss`. Storage loss is then written off. Decentralized sites keep their own residual. The pool allocates remaining grams in `(priority, site_id)` order, and grams above the targets stay at the hub.

Hub labor, the inbound trip, and one outbound fee per site with a target are charged when the order is placed, including for a site that receives nothing after a short delivery. `total_cents` is food plus labor plus delivery actually paid. A lower unit price can still raise that total.

The equal-demand fixture serves 6000 grams either way. Separate orders cost 1250 cents. The pool orders 7499 grams, pays 1124 cents for food at the discounted band, and spends 1274 cents after spoilage and hub fees. A half delivery of that same order still costs 1274 cents, imports 3749 grams, and fills only the higher-priority site. An order under the minimum buys nothing.

## Joint day

`apply_joint` processes food, serves school meals from the delivered lot, then sells each grocery shopper `need - replaced` grams. School grams that were eaten are consumption, not pantry stock. The grocery subsidy and the processor's operating cost stay on separate fields. The joint fixture's at-cost counterfactual for a 500-gram need is 250 cents: 30 paid, 120 funded by the store subsidy, and 100 avoided because the meal replaced a purchase.

## What `sim.core` needs to provide

The adapter can be replaced without editing the policy modules if the core, through a thin wrapper, does all of the following.

1. Settlement uses integer cents and integer grams. Policies pass `now` as an integer simulation second and do not read a clock.
2. Opening cash is a transfer from a named source account. The sum of all accounts is zero. Accounts other than that source have no credit. Spendable cash is settled cash minus active reservations.
3. `take` uses floor division for acquisition cents and leaves the remainder on the source lot. Transforming a lot conserves grams and acquisition cents. Largest-remainder splits, with ties broken by key ascending, match `core_interface.allocate.largest_remainder`.
4. A lot is reserved whole, for one destination, until a single release. Baseline donations are reserved before rescue runs. Reserved lots cannot be taken.
5. Write-offs and consumption recognize acquisition once and do not move cash. Disposal fees, wages, rent, freight, and supplier payments are ordinary transfers.
6. A prepaid supplier shortage imports only the delivered grams. The cents that bought nothing are recorded without creating those grams and without a second payment.
7. Eligible stock is earliest `unsafe_after`, then lot id. A lot with `unsafe_after <= now` is expired. This package skips expired lots; it does not implement the kernel's expiry phase.
8. Baskets and meal portions that cannot be filled exactly are refused. Policies do not draw partial sales.
9. Admission ranks and site priorities are inputs from the kernel's seeded order. This package only sorts by those values and then by id.
10. Policy functions are not idempotent. The kernel applies each command once. This package does not store events, checkpoint, or deduplicate command ids.
11. Ownership and custody are both explicit on every lot movement. The adapter stores custody as a string. The core may distinguish a place from a journey as long as the wrapper still round-trips both.
12. Result objects are reports. They are not a second set of balances. Subsidy, fee relief, capital, and operating resource cost must remain separate so a transfer is not added into a resource-cost total twice.
13. Copy `evidence_state` from the command onto the result. An illustrative fixture must not become an observed input inside the core.
14. Grocery price support is an authorization inside the policy, capped by the subsidy transfer that already posted.
15. A school meal is not a household purchase. Substitution only reduces a later home basket.
16. Run pooled and decentralized procurement on separate ledger states. They are alternative contracts, not two postings in one world.
17. Drones, provider calls, replay, and the HTTP API are outside this package.
