# Delivery plan

## Current planning status

This roadmap sequences work by evidence and dependencies. It does not set a delivery date, staffing commitment, or approved budget.

Browser delivery is a product requirement. The local TypeScript/React/Three.js/Vite environment in apps/web renders a frozen Toronto map, seeded pedestrian itineraries, and a bounded six-hour food-access scenario replayed from Python-generated traces. It has no proposal chat or ongoing connection to a Python simulation service. The target browser adds a side-panel Council chat for Markdown proposals and review. The proposed production stack keeps world and economic state in a Python service and uses the browser for presentation, proposal review, commands, and replay. HTTP commands/snapshots with sequenced WebSocket event updates and FastAPI are candidates, not implemented contracts. See [system architecture](architecture.md).

## Delivery gates

| Gate | Work | Observable result |
| --- | --- | --- |
| 1. World and data foundation | Validate the frozen downtown Toronto map, source attribution, coordinate transform, and walking graph; choose initial browser/device targets; plan broader licensed layer coverage | Current sourced map and active routes resolve to stable source features; source coverage and synthetic geometry are explicit; expansion area and data gates are documented |
| 2. Proposal contract and Council chat | Define Markdown intake, source preservation, outcome-measure fields, unknown/assumption handling, clarification, versioning, and review/approval states | A new proposal becomes a sourced, versioned, human-reviewable record without a proposal-specific code path; unsupported claims remain flagged or unknown |
| 3. Ongoing Python world simulation | Add a pedestrian graph, synthetic population, schedules, mobility constraints, deterministic movement and rule choices; define persistent clock, checkpoint, resume, branch, and replay | A world advances across days and staged infrastructure events; checkpoint/restart and headless replay reproduce authoritative state |
| 4. Browser projection and service | Define versioned commands, receipts, snapshot and event schemas; connect Council chat, one route, and one economic action to the service | The browser renders server-confirmed state; duplicate and stale commands cannot settle twice; reconnect and sequence-gap recovery restore the current world |
| 5. Expert agents and staged rollout | Define simulated department roles, work-package schema, evidence snapshot, deterministic validator, review/approval records, funding and activation rules | Expert recommendations expose dependencies, outcomes, unknowns, and disagreements; only approved feasible stages alter simulated capacity; delay and cancellation are recorded |
| 6. Demonstration proposals and outcome tracking | Load the grocery, surplus-processing, and school-food examples through the shared intake; compare baseline, rollout, and adverse cases | Each proposal tracks its defined measures and standard economic, access, movement, public-cost, uncertainty, and modeled-response outcomes over time; a new proposal follows the same path |
| 7. Browser performance and recovery | Profile startup, frame time, memory, resize, WebGL failure/context loss, background-tab resume, and reconnect on the lowest-supported device | Agreed performance targets pass on the declared browser/device matrix; accessible non-3D controls remain usable when WebGL is unavailable |

Each gate should end in an inspectable artifact and a recorded acceptance result before the next depends on it. The prototype verification record reports a roughly 569 kB minified Three.js scene chunk, but this is not a frame-rate result. Measure download, render, and memory costs separately on the chosen devices; do not carry forward targets from the earlier food-economy plan.

## First implementation work

1. Inspect Toronto building massing and Centreline downloads, metadata, coverage, licenses, coordinate systems, and stable identifiers.
2. Select an initial active area based on the availability of routes and destinations, while preserving citywide context in the scene.
3. Define and review the reusable Markdown proposal record, including source links, proposal-defined measures, unknowns, assumptions, and revision history.
4. Extend the Python service so one resident advances on the same graph in headless and browser-connected runs, with persistent checkpoints and replay.
5. Define the API envelope: schema version, run ID, command ID/idempotency key, expected revision, simulation time, event sequence, receipt, and snapshot-recovery behavior.
6. Connect Council review and one receipt from the existing economic kernel; verify headless/browser projection parity using authoritative run hashes.
7. Freeze the source manifest and record what remains synthetic before adding more pedestrians, department roles, or policy detail.
8. Profile the active area on the lowest-supported device before increasing geometry detail, agent count, shadows, or continuous animation.

## Scope boundary

The first product release should connect a Council chat and proposal intake to the Toronto world, then run a persistent simulation where staged work changes infrastructure and proposal-specific outcomes are tracked. The initial food-policy examples demonstrate the shared workflow. It does not claim a complete digital twin, calibrated citywide behavioral model, observed Toronto sentiment, unrestricted LLM autonomy, or real operational authority.

The grocery, food-rescue/processing, and school-meal proposals are initial demonstration inputs, not a closed set of solution IDs. Their specific service rules and unresolved questions remain proposal-level unknowns until clarified. New proposals should follow the same intake path. Delivery methods are modeled only when supported by proposal evidence and explicit scenario assumptions.

Simulated expert agents can recommend candidate sites, equipment, staffing, procurement, storage, and delivery stages. A deterministic validator and recorded user review control whether a plan can enter the simulation. They do not represent officially delegated City authority. Actual project funding, permits, and real-world implementation decisions remain outside the simulator.

The browser prototype is a frontend demonstration, not an executable policy simulator. It does not provide authoritative world movement, live service access, server persistence, policy execution, or performance evidence for target devices. Those require the Python service and the integration gates above.
