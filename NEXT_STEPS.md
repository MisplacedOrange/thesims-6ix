# Next steps and delivery plan

Updated October 17, 2026. This is the canonical roadmap for The Sims 6ix. It sequences work by dependencies and acceptance evidence; it does not set a delivery date, staffing commitment, or approved budget.

## Current implementation status

The browser application in `apps/web`, built with TypeScript, React, Three.js, and Vite, renders a sourced downtown Toronto snapshot with building massing, street geometry, shoreline, parks, railways, and stylized landmarks. Seeded pedestrians follow connected outdoor routes. The browser provides camera compositions, orbit and zoom, resident inspection and follow, pause, speed, restart, and timeline seeking. The run uses 1,200 synthetic households; buildings and greenery remain visible, and lighting cycles automatically through day, golden hour, and night.

The food-access prototype is a bounded six-hour scenario. Python generates routes, rule-based choices, kernel-settled transactions, service events, and food and economic measures; the browser loads and replays the resulting static traces. The baseline and emergency-site variants demonstrate bounded scenario behavior. They are not proposal submissions or ongoing planner-driven infrastructure rollouts. Development scripts regenerate the cached traces; the browser does not connect to a live Python service or model API.

The proposal chat and intake, department agents, persistent authoritative world service, durable run archive, and staged policy rollout are not implemented. Existing browser routes and the bounded Python trace generator provide a starting point for the future world graph and simulation; they do not establish persistent movement across days. Current browser controls also do not establish performance on a declared target-device matrix.

## Product direction

Browser delivery is a product requirement. The TypeScript, React, Three.js, and Vite application is the presentation, proposal-review, command, and replay surface; the target architecture keeps authoritative world and economic state in a Python service.

The target experience has a side-panel Council chat that accepts Markdown proposals. Intake preserves source material and creates a reviewable, versioned record of requested changes, outcome measures, constraints, assumptions, and unknowns. The workflow supports clarification, revision history, and explicit review and approval states.

Simulated experts for relevant departments and delivery partners coordinate feasible work packages. Deterministic checks expose dependencies and unsupported assumptions; a person reviews and approves proposed stages. Only a validated, approved stage can change the simulated city.

Infrastructure changes unfold over simulator time through planning, procurement, readiness or construction, operation, delay, reduced capacity, and cancellation. The simulation records proposal-specific measures alongside standard city outcomes, with source and assumption traceability. Simulated recommendations do not authorize real City spending, permits, or construction.

## Delivery gates

| Gate | Status | Work | Observable acceptance |
| --- | --- | --- | --- |
| 1. World and data foundation | Partial | Validate the existing downtown map, source attribution, coordinate transform, and walking graph. Record source coverage and synthetic geometry; choose browser and device targets, the next expansion area, and gates for broader licensed layers. | Active routes resolve to stable source features; coverage and synthetic content are explicit; expansion and data gates are documented. |
| 2. Proposal contract and Council chat | Not started | Define open Markdown intake, source preservation, outcome-measure fields, unknown and assumption handling, clarification, versioning, and review and approval states. | A new proposal becomes a sourced, versioned, human-reviewable record without a proposal-specific code path; unsupported claims remain flagged or unknown. |
| 3. Ongoing Python world simulation | Not started | Integrate the existing map and route information into an authoritative Python world. Add the persistent clock, synthetic population, schedules, mobility constraints, deterministic movement and rule choices, checkpoint, resume, branch, and replay. | The world advances across days and staged infrastructure events; checkpoint restart and headless replay reproduce authoritative state. |
| 4. Browser projection and service | Not started | Define versioned commands, receipts, snapshots, and sequenced events. Connect Council review, one route, and one economic action to the service. HTTP commands and snapshots, WebSocket event updates, and FastAPI remain candidates, not implemented contracts. | The browser renders server-confirmed state; duplicate or stale commands cannot settle twice; reconnect and event-sequence-gap recovery restore the current world. |
| 5. Expert agents and staged rollout | Not started | Define department roles, work-package schema, evidence snapshot, deterministic validator, review and approval records, funding assumptions, and activation rules. | Recommendations expose dependencies, outcomes, unknowns, and disagreements; only approved feasible stages change simulated capacity; delay and cancellation are recorded. |
| 6. Demonstration proposals and outcome tracking | Not started | Bring the grocery, surplus-food rescue and processing, and school-meal examples through the shared intake. Compare baseline, rollout, and adverse cases. | Each proposal tracks its measures and standard economic, access, movement, public-cost, uncertainty, and modeled-response outcomes over time; a new proposal follows the same path. |
| 7. Browser performance and recovery | Partial | Profile startup, frame time, memory, resize, WebGL failure or context loss, background-tab resume, and reconnect on the lowest-supported device. Keep usable non-3D controls available when WebGL fails. | Agreed performance targets pass on the declared browser and device matrix; recovery behavior is recorded. |

Each gate should end with an inspectable artifact and a recorded acceptance result before dependent work proceeds. Gate 1 reflects existing map and route work, with validation and expansion decisions still open. Gate 7 has browser controls to build on, but no target-device performance or recovery result is established. A prior prototype record reports a roughly 569 kB minified Three.js scene chunk; that bundle size is not a frame-rate or memory result. Measure download, rendering, and memory costs separately on the chosen devices.

## First implementation sequence

1. Validate the frozen Toronto source manifest, map coverage, coordinate systems, stable identifiers, route graph, and synthetic areas. Select the first active area and browser/device targets based on route and destination coverage, while preserving citywide context.
2. Define and review the reusable Markdown proposal record, including source links, proposal-defined measures, unknowns, assumptions, and revision history.
3. Extend the Python simulation so a resident advances on the same graph in headless and browser-connected runs, with persistent checkpoints and replay.
4. Define the service envelope: schema version, run ID, command ID and idempotency key, expected revision, simulation time, event sequence, receipt, and snapshot-recovery behavior.
5. Connect Council review and one receipt from the existing economic kernel. Verify headless and browser projection parity using authoritative run hashes.
6. Load the three demonstration proposals through the open intake, then show that a new proposal needs no hard-coded policy ID. Add department roles and rollout detail after the service and review path work end to end.
7. Profile the active area on the chosen device before increasing geometry detail, agent count, shadows, or continuous animation. Continue route review around crossings, waterfront paths, and the railway corridor; add landmark or Toronto massing detail only where it adds value, and expand the detailed area after navigation and performance are satisfactory.

## Scope and modeling boundaries

The first product release should connect Council chat and open proposal intake to the Toronto world, then run a persistent simulation where staged work changes infrastructure and proposal-specific outcomes are tracked. The grocery, surplus-food, and school-meal proposals are initial demonstration inputs, not a closed set of supported solution IDs. Their service rules and unresolved questions remain proposal-level unknowns until clarified. Delivery methods are modeled only when supported by proposal evidence and explicit scenario assumptions.

Simulated experts may recommend candidate sites, equipment, staffing, procurement, storage, and delivery stages. A deterministic validator and recorded user review control whether a plan can enter the simulation. These agents do not hold officially delegated City authority. Real project funding, permits, and implementation decisions remain outside the simulator.

The project does not claim a complete digital twin, a calibrated citywide behavioral model, observed Toronto sentiment, unrestricted LLM autonomy, or real operational authority. Keep rules and simple baselines ahead of model complexity. Add small or LLM decisions only after observations, legal actions, replay, fallback behavior, and cost controls are defined.

No revised production schedule, budget, hosting topology, or device performance target is approved. Estimates for real municipal project durations belong to the policy evidence and scenario assumptions; they are not software delivery commitments.
