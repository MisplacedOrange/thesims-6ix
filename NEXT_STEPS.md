# Next steps for The Sims 6ix

Updated October 17, 2026. This roadmap reflects the repository at commit `81f1f78` and its integration documentation.

## Where we stand

The repository contains the system plan and a connected Python research prototype. The prototype covers 250 synthetic households, one school day, and one produce component. Household choices, municipal groceries, processing, school provision, procurement, and ground or drone logistics share one economic kernel.

The implementation can export completed runs and compare policies. Its inputs and modeled feelings remain illustrative. Durable backend services, real-data calibration, live provider transport, and a connected 3D experience remain implementation work.

## Immediate milestone

Connect an actual simulation export to a small 3D demonstration. Run a baseline and a municipal-grocery scenario, watch household actions, and explain the differences through recorded transactions.

Complete this milestone when:

- A resident travels to a store and collects food using recorded journey and settlement data.
- Household cash, store stock, and household food agree with the authoritative simulation.
- Selecting an action reveals its decision, settlement outcome, and causal events.
- Baseline and treatment display spending, produce shortfall, travel time, public outlay, and waste with their units.
- Reloading the same export reproduces the same economic results.
- The interface identifies synthetic inputs and illustrative feelings visibly.

Start with completed-run playback. Add live controls after the transaction path works.

## 1. Connect one transaction to 3D

Assign the frontend owner to connect the existing interface work to one genuine `sim.integration` export.

1. Generate a small baseline and grocery-policy comparison in a new output directory.
2. Inspect the export manifest, journey references, household results, and economic events.
3. Agree on the minimum scene contract with the simulation owner.
4. Render a household, its home, a store, and the recorded collection journey.
5. Add an inspector and a baseline-versus-treatment results panel.

Keep visual interpolation separate from economic settlement. An animation reaching a building cannot complete a purchase. Display actual household expenditure separately from a fixed-basket price measure.

## 2. Assign and build the backend

Explicitly assign a backend owner. The frontend assignment does not implicitly include persistence, API design, or provider transport.

Implement durable run storage, atomic commits, restart recovery, run controls, and ordered scene updates. Define command IDs, expected revisions, projection sequence numbers, and reconnect behavior with the frontend owner.

Terminal exports already exist. Recovery of a running world, including pending logistics, is a broader requirement.

Complete this step when a process can stop during an active run and resume without duplicate purchases, lost reservations, or inconsistent food custody. Verify that visible and headless runs with recorded choices produce the same economic state.

## 3. Acquire real data in parallel

Assign a data owner and choose one Toronto neighbourhood for the first observed-data district.

Acquire dated store locations, traversable routes, compatible household controls, and local basket prices. Record source URLs, reference periods, release dates, geography, units, licences, raw-file hashes, and transformations.

Request aggregate school participation, processing yields, procurement prices, delivery performance, and operating costs where partners can provide them. Keep missing values explicit.

Complete this step when the district can be rebuilt from immutable inputs and its aggregate controls can be checked against their sources. Keep assumed parameters separate from observations throughout the interface and exports.

## 4. Expand the economic model

Extend the current one-day produce model with multiple food categories, a continuous multi-day scheduler, school calendars, procurement lead times, and capacity ramps.

Add household essentials before enabling a financial-strain proxy that depends on those expenses. Model policy implementation through dependencies, funding, readiness, delays, and no-launch cases. Structured infrastructure proposals should identify sites, costs, timing, capacity, and supporting sources before deterministic validation.

Verify conservation, replay, adverse scenarios, and matched baseline comparisons after each extension. Add observed-data calibration and held-out checks before interpreting results as evidence about Toronto.

## 5. Activate live LLM decisions

Connect a provider to the existing bounded-choice interfaces after backend ownership and durable request records are established.

Keep the fixed household panel, legal option IDs, predeclared barrier selection, budget reservations, and deterministic fallbacks. Record prompts, observations, responses, usage, and uncertain charges. Replay must use recorded decisions without new provider calls.

Complete this step when invalid choices, refusals, late responses, exhausted budgets, and interrupted requests behave correctly. Compare live decisions against the rule baseline before increasing agent autonomy.

## Work order

Run frontend export playback and real-data acquisition in parallel. Begin backend design alongside the scene contract. Build recovery before live controls and provider integration. Expand the economic model in small verified changes.

The next concrete task is to export one baseline and grocery-policy pair, then connect one household's collection journey and purchase inspector to the 3D scene.
