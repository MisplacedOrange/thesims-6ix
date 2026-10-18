# Pedestrian food interactions

This is a deterministic six-hour food-access scenario connected to the browser
walking graph. It uses `sim.core` commands to settle every cash transfer, purchase,
food distribution, supplier delivery, movement home, and consumption. The legacy
district integration fixture remains a separate executor.

## Run and view

From the repository root, Python 3.10 or newer:

```powershell
python -m sim.interactables
python -m unittest sim.interactables.test_simulation -v
```

The exporter writes baseline and emergency-site traces for 200, 600, and 1200
households to `apps/web/public/data/interactables/`. These generated files are
ignored by Git. `npm run dev`, `npm run build`, and `npm test` in `apps/web`
automatically regenerate them when the map, kernel, catalog, or generator changes.
The `PYTHON` environment variable can select a Python executable. Production
hosting serves the generated traces as static data and needs no Python service.

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
  consumed at school. At 14:30 the household consumes available home produce up
  to its remaining daily component need; the residual is modeled unmet need.
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

The dashboard reports current stock, prices, quantities purchased/received,
pantry, food used, pending/final unmet need, completed trips, attempted-service
timings, failures, program capacity/uptake, retailer revenue, procurement and
public spending, and outcome groups with household counts. Dashboard totals
are unweighted; income bands and mobility groups are synthetic categories.

## Evidence boundary

The network comes from the frozen attributed OpenStreetMap input. Site anchors,
prices, opening stock, capacities, hours, household endowments, eligibility,
preferences, delivery rules, grants, and the 300 g produce-use rule are
**illustrative scenario assumptions** under `pedestrian-food-day-v1`.
Observed operating costs, eligibility, inventories, prices and capacity remain
unknown and are listed as unknown in the trace. These sites are not asserted to
be actual Toronto operators. Produce portions do not measure complete meals,
diet adequacy, clinical hunger, or observed food insecurity. No business margin,
income timing, non-food spending, LLM choice, or continuous multi-day economy is
implemented here.

The focused checks cover conservation, nonnegative balances, eligibility,
offered/chosen legality, contested capacity, route and time budgets, food custody,
closures, fixed policy rosters, and deterministic repeated runs. These checks
establish implementation invariants, not empirical calibration or validation.
