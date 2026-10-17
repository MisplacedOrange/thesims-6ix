# Logistics

Queues, carrier constraints, ground vans, and hypothetical drone corridors for one neighbourhood run. The package is the simulation side of delivery: who waits, which vehicle moves, when food changes custody, what the trip costs, and which events a renderer can play back.

It does not keep the food-and-money ledger. `sim.core` is expected to implement `CorePort`. The in-memory core in `core_interface/memory.py` is a contract double for tests, not the ledger. This package does not import the API, the database, the replay service, the UI, or the LLM gateway.

Run the tests from the repository root:

```bash
python3 -m unittest discover -s sim/logistics/tests -v
```

## Units

| Quantity | Unit | Rule |
| --- | --- | --- |
| Money | Canadian cents | Integers. A posting is a positive amount that leaves one account and enters another. |
| Food | grams | Logistics does not change grams. |
| Time | simulation seconds | Travel with a positive distance rounds upward and lasts at least one second. Zero distance is not travel. |
| Geometry | metres | Integer coordinates in a local frame. Distances are declared on each leg. They are not remeasured from waypoints. |
| Energy | `energy_units` | A carrier parameter. It is not a measured kilowatt-hour. |

`congestion_milli` of 1000 means a factor of 1. Travel seconds are `ceil(distance_m * congestion_milli / (speed_m_per_s * 1000))`.

## What a run does

`LogisticsEngine` is the only writer of logistics state for one run.

1. Submit every order whose `requested_second` is still in the future.
2. Call `advance_to(second)`. The target is inclusive.
3. Read `metrics()`, `economic_hash()`, and `outcome()`.

Orders that share a second are admitted by a SHA-256 rank of the scenario seed, the opportunity, and the recipient. Submission order does not decide who gets the van. The rank does not draw on a kernel random stream.

Inside one second the engine finishes completions, then handoffs, then dispatch. A stage lasts at least one second. Calling `advance_to` in several steps produces the same hash as one call to the same target.

The routing rule is a heuristic, not an optimizer. One consignment rides one vehicle per trip. The engine picks the earliest free vehicle that can carry the mass, the storage class, the shift, and the energy reserve, and it breaks ties by carrier id. A shift must cover the outbound leg and the return to the hub. Charging after the return may run past the end of the shift.

## Vans

A van trip is preparation, loading at the hub bay, road travel, unloading, and the return. The loading bay has a server count. Households that cannot start wait in a line of finite length. A full line rejects the new order. It does not evict someone already waiting.

Cold food needs `cold_chain`. A single order heavier than every van's payload is unserved. Food with `unsafe_after_second` at or before the load start is excluded and is not moved.

Operating cost for a van is declared cents per metre, including the return, plus cents per loading and unloading second. Preparation is time, not an extra cent charge.

## Drones and ground fallback

A corridor is a scenario record: waypoints, declared metres, an eligibility flag, and an approval value of `no_approval`, `conditional`, or `approved_in_scenario`. That record is a modeling condition. It is not a Transport Canada permission, and flight time is not taken from Meituan announcements.

`no_approval`, an ineligible corridor, weather overlap, site hours that cannot cover unload, a short battery, payload, cold chain, downtime, or a shift miss keep the drone on the ground. If the order allows fallback and a van can take the food, the engine emits the blocker and `GroundFallbackAssigned`, then runs an ordinary hub-to-door van trip. It does not wait out a weather window, and it does not top up an idle drone before launch.

The drone lifecycle on an allowed corridor is preparation, pad loading, flight, unload into the locker, notification, customer walk, and return or charging. The walk is part of door-to-collection. The empty return is vehicle time and cost, not extra customer time.

A handoff fails when the order says `miss`, or when the walk is longer than `pickup_window_seconds`. With fallback, the van drives to the locker, loads the same reserved lots, and delivers them to the door. The drone's operating cost remains on the order, and `fallback_handling_cents` is added because the food was handled twice. Without fallback, the drone reloads, flies the food back to the hub, and the order is failed. The ratio of cost to completed orders stays undefined.

## Metrics

Counts are orders. Time is seconds. Money is cents. Distance is metres.

Door-to-collection for a completed order is the customer's critical path:

```text
queue + preparation + access transfer + loading + flight
    + unloading + customer pickup + failed pickup wait
```

`cost_per_completed_order` is all allocated operating cents divided by completed orders. Failed and unserved work stays in the numerator. It is not in the denominator. When nothing is completed the ratio is undefined. It is stored as a numerator and a denominator, not a float.

An exclusion (no approval, ineligible corridor, weather, site hours, unsafe food) takes precedence over a capacity reason when both apply. Every reason is kept on the order.

## Paired runs and the economic hash

`paired_difference(baseline, treatment)` subtracts treatment minus baseline. It refuses mismatched unit systems, populations, baseline ids, catalog versions, scenario epochs, logistics model versions, or metric units. Rates that are undefined on either side are not reported as zero.

`economic_hash()` is SHA-256 of canonical JSON for carriers, orders, the waiting line, outstanding actions, postings, corridor flags, and committed events. `cosmetic_note` is display text and is omitted. Interpolated frames are not part of the state. The renderer can attach them without changing the hash.

## Animation events

Movement events carry `waypoints_m`, `depart_second`, and `arrive_second`. The renderer interpolates along that path. The engine does not emit a position per frame.

| Kind | What it shows |
| --- | --- |
| `QueueJoined`, `QueueAdvanced`, `QueueRejected` | Who is in line, and the position |
| `ServiceStarted` | A vehicle has taken the order |
| `PreparationStarted`, `PreparationCompleted` | Stationary preparation |
| `LoadingStarted`, `LoadingCompleted` | The bay or pad |
| `JourneyStarted`, `JourneyArrived` | A van leg |
| `DroneFlightStarted`, `DroneFlightCompleted` | A corridor leg |
| `UnloadingStarted`, `UnloadingCompleted` | The stop |
| `NotificationSent` | The locker is ready |
| `CustomerPickupStarted`, `CustomerPickupCompleted` | The walk to the locker |
| `HandoffFailed` | The window closed first |
| `GroundFallbackAssigned` | A van took over, and why |
| `RouteIneligible`, `WeatherExcluded`, `CarrierUnavailable` | Why a drone did not launch |
| `ChargingStarted`, `ChargingCompleted` | The drone at the hub |
| `DeliveryCompleted`, `DeliveryFailed`, `DeliveryExcluded`, `DeliveryUnserved` | The terminal outcome |
| `CostAllocated` | The balanced operating posting |

Each event has a logistics-local sequence and the id of the event that caused it. The kernel assigns the global run sequence when it wraps the event.

## Integration assumptions

These are the contracts a later wiring to `sim.core` and the kernel should keep.

1. `sim.core` implements `CorePort` (`lot`, `reserve`, `release`, `move_custody`, `transfer_ownership`, `post`). Logistics does not import `sim.core`. `MemoryCore` only checks that contract in tests.
2. Logistics never changes grams. It reserves a lot for one holder, moves custody between exactly one place and one journey, transfers ownership only when a recipient collects, and posts one balanced cash pair. Reservation ids are `res-{order_id}-{lot_id}`. Posting ids are `post-{order_id}-operating`. Duplicate ids are rejected so a retry cannot settle twice.
3. A posting debits the fleet operating account and credits the external energy-and-labor account by a positive number of cents. A zero-cost order posts nothing. The sum of the core's account balances stays zero.
4. The kernel submits every order for a second before `advance_to` passes that second. `advance_to` refuses to move backwards. Orders at or before the settled horizon are refused.
5. Logistics phases inside a second are completions (10), handoffs (20), and dispatch (30). They are not the kernel's six world phases. Toronto civil time and daylight saving stay in the kernel. This package only sees integer scenario seconds.
6. Admission ranks are local SHA-256 values. They do not consume kernel random streams, so a queue cannot shift weather or income draws.
7. Event sequence numbers are logistics-local. The kernel wraps each event in its envelope and assigns the global sequence. Waypoints plus departure and arrival seconds are the animation contract.
8. Coordinates are local integer metres. Declared leg and corridor distances are the economic lengths. Waypoints are the path the renderer draws.
9. The vehicle rule is one consignment per trip and earliest-free carrier id, not a solver. The shift covers the return. Charging can continue after the shift. An idle drone that is already short of its reserve is not charged before launch.
10. Corridor approval is a scenario flag. `no_approval` never flies. Weather and site-hour failures are not waited out. Site hours must cover the unload interval. The customer walk is limited by the pickup window instead.
11. Pre-launch fallback uses the direct hub-to-door legs. A failed locker handoff uses the approach, locker-to-door, and return legs. `fallback_handling_cents` is charged only after that second handling, not when the drone never launched.
12. Door-to-collection components cover completed orders only. Return legs are cost and vehicle time. `cost_per_completed_order` uses completed orders as the denominator and is undefined at zero.
13. `paired_difference` requires the same unit system, population, baseline id, catalog version, epoch, and logistics model version (`logistics-1`). Metric units must match. Differences are treatment minus baseline.
14. Lots on an order already sit at the origin, match the order storage class, and sum to the order's grams. Logistics does not create lots. Unsafe lots are excluded at the load second and are not moved.
