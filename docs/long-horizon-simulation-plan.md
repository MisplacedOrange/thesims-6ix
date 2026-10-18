# Long-Horizon Simulation Time Plan

**Status:** Gate 0 is frozen and Gate 1's one-local-day runner is implemented. Browser preset sessions now continue across local days with cash, food and prices carried forward. Durable checkpoints, the full Gate 2 pilot, monthly planning, annual ledgers, and the five-year engine are not implemented.

This plan defines how to replace the current six-hour food-access trace with persistent daily operations and monthly planning over five years. It focuses on simulation time, recurring state, finance, execution order, and validation. It does not claim measured Toronto pedestrian totals or calibrated long-run outcomes.

The versioned run contract is [toronto-long-horizon-v1.json](../planning/scenarios/toronto-long-horizon-v1.json). Related specifications: [simulation model](simulation.md), [agent planner and staged activation](agent-planner-plan.md), and [experiments and validation](experiments-and-validation.md).

## Current boundary

The bounded Council runner retains `HORIZON = 21,600` seconds. Browser presets use a separate one-local-day entry point: its clock runs from local midnight to the next local midnight, the existing activity window begins at 08:30, and daily food consumption occurs at day close. The run records the local date, timezone, and end boundary. Live sessions generate successive days on demand, carrying cash balances, remaining household/site/supplier food and prices across midnight. Opening endowments and the emergency grant are not repeated. Daily admissions and trip schedules renew using the same seeded synthetic population. Without recurring income or supplier imports, depletion is expected.

`sim/live.py` retains only the latest daily trace and a close checkpoint in service memory; retrying a day-advance request returns the already committed next day. The next daily ledger is initialized from the previous close, so daily accounting is conserved but the kernel journal is not a continuous multi-day audit log. The dashboard follows the latest day's trace and labels its totals as daily. Refresh/restart starts a fresh session. This provides continuation while the app is open, not durable save/resume, annual accounting, or a validated long-run economic model. Multi-instance hosting requires shared session storage.

The 2,400-agent preset is an unweighted synthetic sample, with 1,200 retained for paired comparison. It is a simulation sample size, not a count of people observed in downtown Toronto. Population expansion weights require a defined target population and suitable local data.

The $31.7M amount is a proposed FY2026 planning envelope, not an executable balance in the current runner. The bounded Council action still uses a separate finite scenario grant. Implement a distinct annual planning ledger before allowing the planner to commit against the $31.7M envelope.

## Proposed time contract

| Clock | Resolution | Responsibility |
| --- | --- | --- |
| Event time | Integer seconds from a scenario epoch | Pedestrian movement, transactions, deliveries, opening and closing, and other physical events |
| Civil calendar | `America/Toronto` local dates and times | Weekdays, weekends, school terms, holidays, daylight-saving changes, and fiscal dates |
| Activity cycle | One local calendar day | Repeating household and service schedules, with state carried across midnight |
| Planning cycle | One calendar month | Planner observation, typed action proposal, validation, and milestone scheduling |
| Reporting cycle | Quarter and fiscal year | Service, access, finance, capacity, and uncertainty summaries |
| Run horizon | 60 calendar months from a required scenario start date | Five-year scenario; end date is calendar-based and includes leap days |

Store event time as a monotonic integer timeline and derive local calendar time from the scenario epoch and timezone. Local days around daylight-saving transitions may contain 23 or 25 elapsed hours. Schedules follow local civil time; event ordering uses the monotonic timeline. Browser playback speed changes presentation only.

The start date must be explicit in the run manifest. A first-of-month start is recommended so monthly decisions align with calendar boundaries; any other start requires a declared first decision boundary. Do not infer the date from the machine clock. Configure fiscal-year boundaries from the appropriation terms instead of assuming they match calendar years. The manifest should also pin the timezone, horizon, random seed, calendar inputs, population sample, simulator version, and budget assumptions.

For v1, the scenario start date is **2026-10-18** in `America/Toronto`. The daily epoch is local midnight on that date; manifest creation time is recorded separately in UTC. Because the start is mid-month, the first planning boundary is **2026-11-01**. The 60 monthly decisions run through **2031-10-01**, and the five-calendar-year horizon ends at local midnight on **2031-10-18**. The appropriation's fiscal-year boundary remains explicitly unconfigured pending source-backed terms.

## Daily operating cycle

Daily schedules should be data-driven and versioned. They should distinguish ordinary weekdays, weekends, school days, school breaks, holidays, and seasonal cases. Each event receives a stable ID, timestamp, phase, actor, source or assumption reference, and resulting state change.

The event runner should process the next event boundary without resetting world state at midnight. A typical daily schedule may include:

1. Household income, benefits, and recurring obligations on their declared dates.
2. Site opening, staff shifts, service windows, and available capacity.
3. Supplier deliveries, procurement settlement, inventory receipt, and expiration.
4. Household activity choices, pedestrian routes, queues, purchases, and service visits.
5. Food use and other modeled needs according to explicit household schedules.
6. Daily close summaries and state/accounting checks.

Events that occur at the same simulation second need a documented deterministic phase order and stable tie-breaking. Do not use browser selection, animation speed, or wall-clock processing time to decide event order.

## Persistent world state

The state that must survive day boundaries includes:

- **Households:** agent identity, location, schedules, cash, pantry lots, household membership, and any authorized credit.
- **Sites and organizations:** accounts, inventory lots and expiry, prices, hours, staff, equipment, capacity, eligibility, and operating status.
- **Municipal finance:** appropriation authority, reserved commitments, payments, returned amounts, and remaining balance.
- **Work packages:** construction/readiness stages, dependencies, realized durations, delays, capacity ramps, and pending milestones.
- **Replay state:** event sequence, named random-stream state, input hashes, and the latest checkpoint.

Python remains the sole authority for committed state and economic transactions. The browser displays dated snapshots and events. A checkpoint must contain enough state to resume deterministically without recomputing prior events or making new planner calls.

## Monthly planning and implementation

At each monthly decision point, the planner receives a versioned snapshot containing current service and infrastructure state, funds and commitments, available staff and supplies, evidence limits, and pending work. For the initial implementation, use deterministic rules and typed actions. The planner proposes; Python validates and commits.

Infrastructure actions create dated milestones with prerequisites and resource effects. Approval schedules work but does not make a site operational. Funding, procurement, delivery, readiness, commissioning, and opening remain separate events. Capacity changes only after the required milestones succeed. Delays and no-launch outcomes are recorded and replayable.

Compare baseline and intervention from the same initial world, seed, calendars, and exogenous schedules. Add no-launch, delayed opening, reduced capacity, supply failure, and budget exhaustion cases before interpreting an intervention effect.

## Funding treatment

Keep the user-selected **$31.7M FY2026 scenario balance** separate from daily operating cash. Toronto's Council record identifies a **$31.170M Student Nutrition allocation**; retain that exact source value, its program restrictions, and reserve in provenance. Record the $530,000 difference between the rounded scenario balance and source amount as an explicit scenario adjustment. The allocation is not general-purpose infrastructure funding. See the [2026 Council decision](https://secure.toronto.ca/council/agenda-item.do?item=2026.HL33.2).

The annual ledger should distinguish:

- authorized budget;
- planned and reserved commitments;
- settled payments and returned funds;
- capital costs versus recurring operating costs;
- remaining spendable balance and any restricted reserve.

Do not automatically repeat the FY2026 amount in later years or roll unused funds forward. Later fiscal-year appropriations and rollover authority are explicit scenario inputs. Actions must pass program eligibility and available-balance checks before commitment.

## Execution and performance strategy

First implement exact calendar-day execution and benchmark it. With 2,400 agents, one daily decision for each agent over five 365-day years would create roughly 4.38 million household-days before leap days or additional service events. Measure runtime, memory, event volume, and checkpoint size on a 30-day pilot before choosing five-year execution optimizations.

If exact daily execution is too costly, consider deterministic repeat-day compression only after showing that it preserves path-dependent household balances, stock, capacity, budget, and milestone outcomes. Representative-day weights may be used for aggregate reporting. Do not multiply ledger transactions, cash balances, inventory, or capacity by a reporting weight unless the accounting semantics and conservation checks explicitly support it. Keep exceptional days and decision/milestone dates exact.

Long-run results should not be stored or sent to the browser as one unbounded JSON trace. Persist committed events and periodic checkpoints, expose date-windowed event queries, and compute daily, monthly, quarterly, and annual summaries from the same event record.

## Implementation gates

| Gate | Work | Acceptance evidence |
| --- | --- | --- |
| 0. Freeze contracts | Define manifest fields, timezone/calendar rules, event ordering, metric units, funding semantics, and start-date requirements | **Implemented:** the v1 manifest pins the current date, monthly boundaries, seed, sample, data hashes, funding provenance, and unresolved calendar/fiscal inputs |
| 1. Full-day runner | Extract reusable daily execution from the six-hour routine and represent the current activity window within a full 24-hour day | **Implemented:** one-day baseline repeats exactly; 23-, 24-, and 25-hour Toronto dates are recognized; trip events remain ordered and the food/cash invariants pass |
| 2. Persistent 30-day pilot | Carry household, site, and municipal state across dates; add recurring schedules and checkpoints | Uninterrupted and checkpoint-resumed runs produce the same state and event hashes; no midnight reset or duplicated recurring event occurs |
| 3. Annual operations | Add calendar seasonality, school schedule variation, delivery lead times, recurring costs, and fiscal-year close | A 12-month run closes each budget once, uses only authorized funds, and reports defined denominators and units |
| 4. Monthly planning | Schedule typed infrastructure/resource actions and milestone dependencies on the monthly clock | Approved plans commit only after prerequisites; delayed, reduced, canceled, and no-launch cases replay exactly |
| 5. Five-year run | Execute 60 monthly planning steps with daily operations, checkpoints, and dated summaries | A five-year run resumes and replays deterministically; paired baseline/intervention runs share initial conditions; performance limits are documented |

## Reporting and interface

Show the scenario date, local time, month, quarter, fiscal year, and horizon progress. Provide day, month, quarter, and year summaries with a date-windowed event log. Keep unique households, visits, attempted trips, and service units distinct. Label observed inputs, synthetic assumptions, sample counts, reporting weights, and unknowns beside their results.

The map may animate one selected activity window while the simulation continues through the full horizon. Selecting or moving the camera must not alter agent choices or planner decisions.

## Open inputs before a five-year run

- Scenario start date and alignment with FY2026.
- Household income/benefit dates, food needs, non-food obligations, and recurring activity schedules.
- School and service calendars, delivery frequencies, lead times, and inventory expiration rules.
- Verified site roster, operating status, hours, capacity, staffing, and authority to change them.
- Future-year appropriations, eligible uses, reserves, and rollover rules.
- Whether measured local population weights are available; until then, keep the 2,400-agent sample unweighted.
- Runtime and storage limits established by the 30-day benchmark.

These inputs remain unknown until supported by a source or labeled as scenario assumptions. The first implementation target is Gate 0 and Gate 1; the five-year horizon is not ready to run until the intermediate state and budget gates pass.
