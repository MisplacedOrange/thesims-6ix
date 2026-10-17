# Pedestrian, economic, and policy model

## Scope and units

The target model represents people moving through a 3D Toronto environment while public solutions are planned and rolled out over time. The first policy examples are municipal groceries, food rescue and processing, and expanded school meals. The current code covers only a synthetic food-economy slice; it is not a citywide model or an observed forecast. It measures direct household, institutional, and municipal effects. It does not infer employment multipliers, land-price changes, long-run migration, clinical health outcomes, or Toronto GDP.

The Python simulation service is the authority for pedestrian positions, paths, physical activities, and logical simulation time, as well as the economic kernel's money, food, household accounts, and settled services. The browser receives versioned snapshots and events and renders them; its frame loop and camera cannot advance simulation state. A school schedule is one possible local schedule inside the world. The current one-day school fixture is not the target time horizon; see [why the prototype says school day](integration.md#why-the-prototype-says-school-day).

Use integer Canadian cents for money, integer grams for food mass, integer simulation seconds for time, and metres for route geometry. Record conversion and rounding rules. Monetary comparisons use a declared base month. Cash balances remain nominal. Converting reported outcomes into real dollars must never rewrite historical ledger entries.

Allocate fractional cents by a documented largest-remainder rule with stable tie-breaking. Carry recipe mass remainders within a batch and assign the final remainder to a declared output or process-loss record. Round travel and service duration upward to at least one second. Unit conversion never silently creates value or mass.

Use a single versioned product catalog. Start with a small set of basket components and storage classes. Each product has a unit mass, procurement and retail pricing units, nutritional attributes where sourced, storage limits, and recipe eligibility. Different food groups are not interchangeable merely because they have the same mass.

## Actors and resources

| Entity | State it carries | Decisions or transitions |
| --- | --- | --- |
| Pedestrian | Position, path, activity, mobility needs, schedule, knowledge, household or institution link | Choose a legal destination or activity; move on the world network |
| Household | Members, cash account, pantry, time availability, home, preferences, known offers | Authorize a basket, shop, collect, or substitute meals |
| Retailer | Lots, prices, hours, staff capacity, supplier contracts, cash | Reorder, allocate stock, markdown, donate, serve customers |
| Municipal retailer | Retailer state plus public budget and pricing rule | Spend subsidy, apply price rule, delay procurement if unfunded |
| Processor | Eligible input lots, equipment queues, recipes, staff, storage | Accept or reject rescue, process batch, allocate output |
| School | Enrollment, school calendar, menu, uptake, kitchen capacity | Order food, prepare meals, serve eligible participants |
| Food hub | Contracts, cold storage, loading capacity, dispatch windows | Consolidate orders and assign deliveries |
| Supplier | Products, prices, lead times, available quantities | Fulfill purchase orders within declared capacity |
| Carrier | Vehicle, payload, shift, location, route, energy | Collect, deliver, return, charge or refuel |
| Municipality | Budget appropriations, accounts, policy schedules | Fund, activate, limit, or stop program expenditure |
| Infrastructure planner | Frozen evidence snapshot, candidate sites, budgets, constraints, horizon | Draft a sourced rollout proposal; it cannot activate a stage |
| Reviewer and validator | Draft, feasibility checks, evidence references, approval record | Reject, revise, or approve a versioned plan |

People are embodied agents in the 3D world and can belong to households. A household remains the owner of purchasing authority, money, and pantry accounting. Institutional demand follows its own rules. A school cannot create a household purchase to disguise the cost of a school meal.

## Money accounting

Every settlement posts a balanced journal. A CAD 5 household purchase decreases household cash by 500 cents and increases store cash by 500 cents. A public subsidy transfers cash from the municipality's funding account to the store. Supplier payments, wages, energy, rent, and capital costs use named counterparties or external accounts.

Opening assets, capital injections, taxes, grants, and outside income have explicit sources. The system does not create money by changing a balance directly. No credit is available in the first model unless a scenario explicitly defines a credit account and its limit.

At every committed transition:

```text
sum(journal_entry.cents) = 0
spendable_cash = settled_cash - reserved_cash
spendable_cash >= 0 for actors without authorized credit
```

Reservations hold a maximum price and finite stock. On settlement, post actual charges and release the remainder. On cancellation, release both resources. Validate them again at settlement because an option was feasible at observation time, not guaranteed forever.

Report fiscal cash outlay and annualized economic cost separately. Capital cash expenditure is not a recurring yearly expense. Annualization needs a stated lifetime and discount-rate assumption. Count fee relief as forgone municipal revenue. A subsidy is a transfer for social accounting and a cost to the public budget. Do not add the same transfer to a total resource-cost estimate twice.

Municipal store viability has separate cash and operating views:

```text
cash_before_subsidy = sales_receipts - inventory_payments
                      - other_operating_cash_payments
cash_funding_gap = max(0, minimum_cash_reserve
                         - opening_cash - cash_before_subsidy)

operating_result = sales_revenue + operating_subsidy
                   - cost_of_food_sold - inventory_writeoffs
                   - labor - occupancy - energy - logistics
                   - disposal_charges - other_overhead
```

Use a stated inventory valuation method, initially acquisition cost with lot-specific lineage. Purchasing inventory changes cash and inventory assets. Selling food or writing off spoiled stock recognizes that acquisition cost exactly once. Never subtract spoiled stock's acquisition value again as an extra cash expense. Disposal fees are separate cash payments and expenses. Cash funding needs and operating break-even subsidy can differ because inventory and payment timing differ. Capital cash and depreciation remain separate from these operating comparisons.

Removing a corporate profit margin is not a complete price model. Wholesale terms, scale, rent, capital, labor, waste, and subsidy can outweigh that margin. Distinguish procurement savings from a price reduction funded by taxpayers.

## Food accounting and processing

Each lot records product, grams, owner, custody as either a place or active journey, storage state, expiry or unsafe-after time, and source lineage. Ownership and custody can differ while a carrier transports a school's food. Store stock cannot also exist at the processor. Available-stock indexes exclude reserved or travelling lots.

The district mass balance includes external imports and exports:

```text
opening_inventory + imports + added_recipe_material
  = closing_inventory + consumption + waste + exports
```

Every processing batch records accepted input, rejects, added ingredients or water, edible output, byproducts, and process loss. Food-safety eligibility and shelf-life rules are explicit simplified assumptions reviewed with a domain expert. Software must not treat an expired lot as safe because an LLM wants to use it.

Use earliest-expiring eligible stock first unless a declared allocation rule chooses otherwise. A rescue offer competes against markdown sales, direct donation, and disposal. Reserve a lot for exactly one destination. Donations to other organizations remain part of the baseline so an intervention cannot claim benefits by diverting food already being used.

Reported facility capacity is an upper bound. Daily output is limited by inbound eligible food, staff, machine time, recipe yield, storage, and downstream demand. A pound of rescued produce is not a meal. Meal conversion needs an explicit menu, portion, and nutrition rule.

## Pedestrians, households, and routine choice

Generate synthetic residents and household attributes from aggregate controls. A resident carries a current location, destination, activity, schedule, mobility profile, and known information. A household carries size, child age bands, income band, essential non-food expenses, home, cooking access, food preferences, cash, and pantry. Do not infer individual routines from neighbourhood averages or assign preferences through ethnic stereotypes.

The Python simulation service moves residents along a sourced or explicitly illustrative pedestrian network. Route feasibility accounts for barriers, crossings, mobility constraints, access time, and destination opening hours when those data exist. A straight line between home and a store is not a measured walkable route. Agents may walk, wait, attend a service, shop, or return home; movement state does not directly settle an economic event.

At a shopping opportunity, construct feasible baskets and routes using available stock, prices, opening hours, household cash, storage, and time. Include a no-purchase or delayed-purchase option so residents can fail to meet need. The household retains spending authority even when one member carries out the trip.

The transparent baseline uses a discrete-choice score:

```text
utility(option) = preference_fit + habit_value + known_quality
                  - price_sensitivity * expected_payment
                  - time_sensitivity * total_minutes
                  - stockout_penalty - uncertainty_penalty
                  + seeded_choice_noise
```

Coefficients have units and documented calibration sources. A price coefficient in utility per dollar cannot silently consume cents. Habit and limited knowledge prevent every household from instantly finding the global cheapest store. Income affects affordability and time constraints through declared mechanisms. It does not determine intelligence or virtue.

Expected expenditure, nutritional fit, and realized outcomes are separate. A cheaper basket can still contain less usable food. Report quality and shortfall as well as cash savings.

## School meals as one service scenario

School meals are one of the three proposed solutions and may be the first rollout-planning demonstration. They do not define the geography, clock, agent model, or city simulation. Distinguish candidate schools, planned reach, eligible students, daily participants, meals prepared, and meals consumed. A synthetic child has a household, age band, school assignment, eligibility, attendance schedule, and dietary constraints. Apply local calendars, allergies, menus, staffing, waste, and kitchen limits. Participation and attendance are separate, so an absent child cannot consume a school meal.

The proposed unlimited-lunch idea is not yet a complete service specification. Eligibility, participation, menu, service days, portion rules, dietary accommodation, and what “unlimited” means must be defined before estimating infrastructure or outcomes. Do not assume unlimited quantity in the model based on the label alone.

The household substitution parameter states how much school food replaces home purchases. It ranges across declared sensitivity values and can be zero. School meals may reduce household spending, increase food consumed, or allow the household to improve other meals. Their procurement cost does not automatically equal household cash savings.

Shared purchasing affects supplier prices, contract volume, delivery frequency, hub labor, storage, and reliability. It can reduce unit prices while increasing handling cost or spoilage. Compare decentralized and pooled procurement at the same served demand before changing uptake.

Attendance and educational attainment are outside the first causal model. Existing research does not justify an automatic attendance increase whenever a child receives a meal. Keep any later education module separate and evidence-backed.

## Travel and delivery

Use a dated road and pedestrian network. Travel time includes access legs, waiting, service, and return travel where relevant. A straight line between a home and a store is not a measured walkable route.

Ground vehicles have payload, shift, loading, route, congestion, and cold-chain limits. Vehicle routing can start with a transparent heuristic. Introduce optimization only after the baseline can explain its assignments and missed deliveries.

For drones, use fixed approved-in-scenario hub-to-locker corridors. The lifecycle is preparation, ground transfer, loading, queue, flight, unloading, notification, customer pickup, and return or charging. Include payload, battery reserve, site hours, weather exclusions, maintenance, failed handoff, and ground fallback.

Check every proposed route against a scenario route-eligibility record. The record is a modeling condition, not real flight permission. Do not extrapolate Meituan's advertised Chinese times or weather limits into Toronto parameters.

Door-to-collection time and cost are:

```text
total_minutes = preparation + access_transfer + queue + loading
                + flight + unloading + customer_pickup
cost_per_completed_order = all_allocated_operating_cost / completed_orders
```

Report unserved orders separately. Dividing by all requested orders would hide the cost of failures. Include ground alternatives, locker accessibility, worker time, and idle capacity.

## Bounded pedestrian-model decisions

At a decision boundary, the model gateway receives a stable decision ID, resident ID, linked household or service context, world and economic revisions, known facts, recent event references, and a finite set of legal intent IDs. It returns one intent ID and an optional short explanation. It receives no unrestricted tools or database credentials. The Python service validates the selected intent, route, movement constraints, and any economic effects before committing a transition.

A resident cannot know another household's balance, future stock, or unannounced plan unless the scenario gives that information. Household purchase authorization remains separate from a pedestrian destination choice. Observations are built by explicit knowledge rules. Generated narrative and retrieved text are untrusted data.

Use deterministic movement and rule policies first. Add a small model or LLM only for selected decision types after replay, validation, and economic ownership are in place. Fix the focal resident panel and request schedule before each experiment; do not let camera selection or response speed change who receives a call. The existing 40-household, 30-day, four-request-barrier, and CAD 30 limits belong to the earlier food-policy prototype plan. They are not approved limits for the pedestrian population. Set new concurrency, latency, token, and cost ceilings after the active-area scale and decision frequency are measured.

At a decision barrier, freeze one observation revision. Use a deterministic fallback for missing, refused, invalid, late, stale, or unaffordable choices. Resolve resource contention with a recorded seeded admission order. Provider response order must not determine who gets the last food lot or who is admitted to the study panel.

Persist the exact selected option, observation hash, prompt version, model configuration, response, reason for fallback, usage, and charge reservation. Optional cached responses require identical observation and configuration hashes. Replay uses recorded receipts and makes no provider calls.

## Modeled human response

Keep behavior, latent state, and explanation as three fields. Behavior is an event such as changing stores. Latent state is a declared proxy. Explanation is generated text grounded in events.

An initial proxy family can use bounded, exponentially smoothed values:

```text
food_strain = normalized recent basket shortfall
financial_strain = normalized inability to fund essentials
time_strain = normalized time-budget overrun
stress_next = clamp(0, 1,
                   persistence * stress_now
                   + weighted(food_strain, financial_strain, time_strain)
                   - recovery)
```

The weights, normalization, and persistence require sensitivity analysis. They are illustrative behavioral assumptions until calibrated. Trust updates from recorded fulfillment and broken expectations. Satisfaction compares expected and realized service. Do not label these scores as clinical stress, diagnosed hunger, or measured Toronto sentiment.

An LLM explanation cites event IDs and can only describe facts present in its observation. Validate that claimed prices, waits, and purchases match those events. Show a rule-generated explanation when grounding fails. Aggregated generated comments must carry a visible synthetic label and remain separate from real survey results.

## Policy rollout state and outcomes

Each solution moves through explicit states: proposed, checked, reviewed, approved, scheduled, active, delayed, reduced, stopped, or completed. A rollout record has source and assumption references, candidate sites, stage windows, dependencies, funding, capacity ramps, uncertainties, and stop conditions. The grocery proposal can exist in a planning state without any store serving shoppers. A school expansion can have funding while kitchen capacity remains unavailable. A processor can be commissioned before reaching its stated operating capacity. Only a committed activation event changes modeled capacity.

Compare baseline and rollout by neighborhood and population group. Keep household spending, public costs, service reach, food access, travel, capacity, and waste in their own units. A change in modeled trust, satisfaction, stress, or perceived access is a labeled model output, not measured Toronto sentiment. Keep observed survey evidence in a separate stream. The baseline uses verified actual service where available. When rollout observations are missing, provide separate conservative and announced-capacity variants; do not silently choose full delivery because it makes a comparison easier.
