# Pedestrian food interactions

The browser's preset traces model one explicit Toronto calendar day, with the
existing six-hour food-access activity window inside a full-day clock. The day
runner uses `sim.core` commands to settle every cash transfer, purchase, food
distribution, supplier delivery, movement home, and consumption. It does not
carry state into another day. The bounded Council action and legacy district
integration fixture remain separate executors.

## Run and view

From the repository root, Python 3.10 or newer:

```powershell
python -m sim.interactables
python -m unittest sim.interactables.test_simulation -v
```

The exporter reads its start date, timezone, horizon, seed, population presets,
budget provenance, and pinned input hashes from
`planning/scenarios/toronto-long-horizon-v1.json`. It writes baseline and
emergency-site traces for 200, 600, 1,200, and 2,400 household agents to
`apps/web/public/data/interactables/`. The primary sample is 2,400; 1,200 is
retained for matched comparisons.
These are unweighted sample sizes, not measured downtown pedestrian totals or
estimates of the number of people represented. Generated
files are ignored by Git. `npm run dev`, `npm run build`, and `npm test` in `apps/web`
automatically regenerate them when the map, kernel, catalog, generator, or pinned site snapshot changes.
The `PYTHON` environment variable can select a Python executable. Production
hosting serves the generated traces as static data and needs no Python service.
To change the scenario start date or another pinned input, create a new manifest
version instead of relying on the machine clock.

## Local Council scenario service

`python -m sim.council` starts the separate loopback-only Council service on
`127.0.0.1:8765`. It stores exact proposal revisions, immutable proposal-linked
organization revisions, append-only stakeholder-input records, reviewed scopes
and plans, decisions, idempotency receipts, and immutable baseline/intervention
traces in SQLite. The browser Council panel can create and inspect organization
and stakeholder-input records. Plans freeze their record IDs and hashes, and
rollout events identify the organization records linked to each stage. Those
links are review context only: they do not cause proposal-responsive
organization decisions, verify that input is representative, or conduct
consultation. The API supports one explicit `establish_service_site` action in a
matched six-hour scenario. Scope, plan, decision, and run controls remain
unfinished in the UI. The deterministic department-style advice is explanatory
only. It is not a model call or a source refresh. The service pins the current
population, seed, map, location snapshot, catalog, simulator input code hash,
and Python implementation/version; the map location is not evidence of
present-day operation or authority.

This local Council service does not replace cached trace playback, create a
persistent city account, or advance the world across days. Static production
hosting serves the existing generated traces; it does not provide the Council
API. See the root [startup guide](../../README.md) for running the local browser
and service together. Supplier quantities use 100 g purchase units at an
illustrative 20 cents per 100 g; zero stock is accepted only as an explicitly
reviewed no-launch plan. Recording a decision rechecks the frozen world and
simulator inputs, so a stale plan must be replaced before it can be decided.

By default, generated traces use the pinned City-listed location snapshot at
`sim/data/snapshots/toronto-downtown-sites-v3.json`. Pass
`--illustrative-sites-only` to retain the original generic site anchors.

For a different seed, population, or explicitly closed walking edge, export to a
separate directory:

```powershell
python -m sim.interactables --populations 80 --seed 17 --closed-edge 0:1 --out outputs/food-access
```

A closure must reference an existing edge. The browser exposes the default seed
and scenarios; custom exports are research inputs, not automatically loaded by it.

## State, decisions, and timing

- One pedestrian acts for each household. The household owns all cash and food.
- Every household starts at a fixed seeded home node. Changes to the emergency
  policy or walking closures preserve the household roster and site anchors.
- The rule offers currently affordable, eligible baskets at reachable sites with
  stock, open arrival/service times, capacity, and sufficient round-trip time.
  Delay and no purchase are recorded choices. One delayed decision is allowed.
- The illustrative score is grams obtained minus cents paid minus trip seconds
  divided by 20; ties break by site ID. This is a declared baseline, not a fitted
  preference model. A cheaper alternate retailer and smaller baskets provide
  substitution and constrained-purchase options.
- Each household makes at most one single-destination trip. Arrivals queue at a
  single server. Seeded admission ranks break simultaneous-arrival ties. Stock,
  current price, cash, hours, and capacity are rechecked at service completion.
  A failed attempt transfers neither food nor money and still returns home.
- School eligibility comes from synthetic child counts; pantry eligibility uses
  the synthetic income band. School capacity counts 300 g produce portions;
  other site capacities count household visits. No eligibility is inferred from
  a mapped location or personal program record.
- Purchases and support baskets stay at the collection place under household
  ownership until the resident reaches home. They are shown as carried food and
  cannot be consumed from the home pantry before return. School portions are
  consumed at school. At the end of the local calendar day the household consumes
  available home produce up to its remaining daily component need; the residual
  is modeled unmet need.
- A crossing adds a visible 12 s wait. Explicitly closed edges are removed from
  routing. The route generator records inaccessible destinations separately from
  closed sites, unaffordable baskets, stockouts, capacity denials, and time limits.
- Both scenarios include a paid supplier replenishment at 10:10 and an illustrative
  western-store price increase at 11:00. The emergency scenario grants CAD 300
  from the city at 09:30, receives paid supplier stock at 09:31, and closes the
  temporary site at 13:30. Quantity and visit capacity scale with the selected
  population. Supplier stock and city/store/program cash are finite.

## Event and browser contract

Each trace contains opening household and organization projections, routes,
offered options and exclusions, chosen actions, attempted services and denials,
committed transfers and consumption projections, terminal household state,
accounting totals, the map hash, kernel state hash, seed, and scenario assumptions.
Event quantities are integer cents, grams, and simulation seconds. Geometry and
movement speed may be floating point. Records retain resident/household/site,
decision/route IDs, result and failure reason, timing, and evidence metadata.

The browser samples routes and folds committed projections up to the playhead.
It never updates balances or recalculates purchases. Seeking and restarting are
read-only replay operations. Changing population or policy loads a separate run
and resets the playhead. Download exports the complete trace, including later
events. Site markers and household inspectors show the current playhead state.

In Council traces, `public_spending_cents` is the city's grant cash outflow, net
of any returned unspent grant. `site.spending_cents` is the site's supplier
procurement payment; it is not added to the grant transfer as a consolidated
resource-cost measure. An unspent grant may remain with the hypothetical
operator at closure. These are distinct cash-flow views, not a total-cost
estimate.

The dashboard reports current stock, prices, quantities purchased/received,
pantry, food used, pending/final unmet need, completed trips, attempted-service
timings, failures, program capacity/uptake, retailer revenue, procurement and
public spending, and outcome groups with household counts. Dashboard totals
are unweighted; income bands and mobility groups are synthetic categories.

## Evidence boundary

The network comes from the frozen attributed OpenStreetMap input. In the default
trace, the locations and names for the two supermarket anchors, food-support
anchor, and school anchor come from the pinned City GIS snapshot. Their current
operating status and source observation date are unknown. The emergency
intervention location remains synthetic. Prices, opening stock, capacities,
hours, household endowments, eligibility, preferences, delivery rules, grants,
and the 300 g produce-use rule are **illustrative scenario assumptions** under
`pedestrian-food-day-v1-toronto-downtown-sites-v3`. The selected source-listed
points are the nearest records to the old illustrative anchors, not a
representative sample of services. The trace records the source row, source
URL, retrieval time, selection method, and map snap distance. Observed operating
costs, eligibility, inventories, prices and capacity remain unknown. Produce
portions do not measure complete meals,
diet adequacy, clinical hunger, or observed food insecurity. No business margin,
income timing, non-food spending, LLM choice, or continuous multi-day economy is
implemented here.

The focused checks cover conservation, nonnegative balances, eligibility,
offered/chosen legality, contested capacity, route and time budgets, food custody,
closures, fixed policy rosters, and deterministic repeated runs. These checks
establish implementation invariants, not empirical calibration or validation.
