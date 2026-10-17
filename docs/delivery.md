# Delivery plan

## Current planning status

This roadmap sequences work by evidence and dependencies. It does not set a delivery date, staffing commitment, or approved budget. The earlier 16-week food-policy prototype and its illustrative CAD 252,480 envelope are superseded; they did not estimate a Toronto-first 3D simulation.

Browser delivery is a product requirement. A local TypeScript/React/Three.js/Vite frontend prototype is present in apps/web; it displays one synthetic recording and is not connected to a simulator. The proposed production stack keeps world and economic state in a Python service and uses the browser only for presentation, commands, and replay. HTTP commands/snapshots with sequenced WebSocket event updates and FastAPI are candidates, not implemented contracts. See [system architecture](architecture.md).

## Delivery gates

| Gate | Work | Observable result |
| --- | --- | --- |
| 1. Browser foundation | Reconcile the existing local frontend prototype, choose initial browser/device targets, audit source licenses and vintages, freeze one map area and coordinate transform | The browser loads a sourced Toronto context and one active area; a selected building, street, and destination resolve to stable source features; synthetic geometry is labeled |
| 2. Python world simulation | Add a pedestrian graph, small synthetic population, schedules, mobility constraints, deterministic movement, and rule choices to the Python service | One resident follows a feasible Toronto route; headless replay returns repeatable positions and choices |
| 3. Browser projection and API | Define versioned commands, receipts, snapshot and event schemas; connect one route and one economic action to the existing kernel | The browser renders server-confirmed state; duplicate and stale commands cannot settle twice; reconnect and sequence-gap recovery return the correct projection |
| 4. Planner and rollout | Define the three solution IDs, evidence snapshot, stage format, deterministic validator, review record, and activation rules; use the school meal plan as an initial case if its service definition is agreed | A validated school rollout includes candidate infrastructure and prerequisites; rejected or unfunded stages never change the running world |
| 5. Outcomes and evaluation | Compare baseline, staged treatment, and adverse rollout cases; label data and modeled response | Results report economic outcomes, reach, movement, public cost, uncertainty, and modeled response by supported groups |
| 6. Browser performance and recovery | Profile startup, frame time, memory, resize, WebGL failure/context loss, background-tab resume, and reconnect on the lowest-supported device | Agreed performance targets pass on the declared browser/device matrix; the accessible non-3D controls remain usable when WebGL is unavailable |

Each gate should end in an inspectable artifact and a recorded acceptance result before the next depends on it. The prototype verification record reports a roughly 569 kB minified Three.js scene chunk, but this is not a frame-rate result. Measure download, render, and memory costs separately on the chosen devices; do not carry forward targets from the earlier food-economy plan.

## First implementation work

1. Inspect Toronto building massing and Centreline downloads, metadata, coverage, licenses, coordinate systems, and stable identifiers.
2. Select an initial active area based on the availability of routes and destinations, while preserving citywide context in the scene.
3. Extend the Python service so one resident advances on the same graph in headless and browser-connected runs.
4. Define the API envelope: schema version, run ID, command ID/idempotency key, expected revision, simulation time, event sequence, receipt, and snapshot-recovery behavior.
5. Connect one receipt from the existing economic kernel and verify headless/browser projection parity using authoritative run hashes.
6. Freeze the source manifest and record what remains synthetic before adding more pedestrians, destinations, or policy detail.
7. Profile the active area on the lowest-supported device before increasing geometry detail, agent count, shadows, or continuous animation.

## Scope boundary

The first deliverable establishes Toronto as the primary 3D environment, supports pedestrian agents, and demonstrates one sourced infrastructure rollout plan. It does not claim a complete digital twin, calibrated citywide behavioral model, observed Toronto sentiment, unrestricted LLM autonomy, or real operational authority.

School meals, including the proposed unlimited-lunch option, are one rollout scenario. The exact eligibility, participation, service days, menu, and meaning of “unlimited” remain to be specified. Municipal groceries and food rescue/processing remain the other two solution entries indicated in the current planning documents. Drone delivery remains an optional logistics case, not a core solution ID.

The planner can recommend candidate sites, equipment, staffing, procurement, storage, and delivery stages. A deterministic validator and recorded review control whether a proposed schedule can enter a simulation. Actual project funding, permits, and real-world implementation decisions remain outside the simulator.

The browser prototype is a frontend demonstration, not an executable policy simulator. It does not provide authoritative world movement, live service access, server persistence, policy execution, or performance evidence for target devices. Those require the Python service and the integration gates above.
