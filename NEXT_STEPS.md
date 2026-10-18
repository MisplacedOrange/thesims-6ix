# Next steps and delivery plan

Updated October 18, 2026. This is the canonical roadmap for The Sims 6ix. It sequences work by dependencies and acceptance evidence; it does not set a delivery date, staffing commitment, or approved budget.

## Current implementation status

The browser application in `apps/web`, built with TypeScript, React, Three.js, and Vite, renders a sourced downtown Toronto snapshot with building massing, street geometry, shoreline, parks, railways, and stylized landmarks. Seeded pedestrians follow connected outdoor routes. The browser provides camera compositions, orbit and zoom, resident inspection and follow, pause, speed, restart, and timeline seeking. Population settings are 200, 600, or 1,200 synthetic households, with 600 as the default; buildings and greenery remain visible, and lighting cycles automatically through day, golden hour, and night.

The browser can connect to a local Python Council service for exact Markdown intake, immutable revisions, explicit scope and plan review, deterministic advice, three reviewer decisions, and one supported six-hour municipal food-site scenario. The service stores versioned command receipts and immutable paired traces in SQLite and exposes them on loopback. Baseline and intervention are independent runs matched on population, seed, map, source snapshot, and simulator hash. The service is a bounded scenario workflow; it is not a persistent city or multi-day world, and it does not call external models or refresh evidence.

General conversational proposal intake, autonomous department agents, a persistent authoritative world, and durable multi-day state are not implemented. The Council's local proposal and run history is durable, but its paired scenario traces are bounded six-hour runs. Existing browser routes and the trace generator do not establish persistent movement across days. Current browser controls also do not establish performance on a declared target-device matrix.

## Product direction

Browser delivery is a product requirement. The TypeScript, React, Three.js, and Vite application is the presentation, proposal-review, command, and replay surface; the target architecture keeps authoritative world and economic state in a Python service.

The target experience has a side-panel Council chat that accepts Markdown proposals. Intake preserves source material and creates a reviewable, versioned record of requested changes, outcome measures, constraints, assumptions, and unknowns. The workflow supports clarification, revision history, and explicit review and approval states.

See the [agent planner plan](docs/agent-planner-plan.md) for planning roles, work packages, authority, approval, activation, and rollout states.

## Delivery gates

| Gate | Status | Work | Observable acceptance |
| --- | --- | --- | --- |
| 1. World and data foundation | Partial | Validate the existing downtown map, source attribution, coordinate transform, and walking graph. Record source coverage and synthetic geometry; choose browser and device targets, the next expansion area, and gates for broader licensed layers. | Active routes resolve to stable source features; coverage and synthetic content are explicit; expansion and data gates are documented. |
| 2. Proposal contract and Council chat | Partial | The local panel preserves exact Markdown and source spans, records recognized sections, assumptions and unknown text, and supports immutable revisions, explicit scope, typed plan, deterministic advice, and reviewer decisions. General conversational clarification, complete affected-party analysis, and consultation evidence workflows remain future work. | A proposal becomes a sourced, versioned, human-reviewable record; unsupported text and source limitations remain visible; no reviewer decision is inferred from proposal wording. |
| 3. Ongoing Python world simulation | Not started | Integrate the existing map and route information into an authoritative Python world. Add the persistent clock, synthetic population, schedules, mobility constraints, deterministic movement and rule choices, checkpoint, resume, branch, and replay. | The world advances across days and staged infrastructure events; checkpoint restart and headless replay reproduce authoritative state. |
| 4. Browser projection and service | Partial | A loopback stdlib HTTP service uses schema-versioned commands, expected revisions, request hashes, SQLite receipts, and stored snapshots/traces. The browser renders the bounded Council record and matched six-hour pair. General world snapshots, ordered live-world events, and reconnect recovery remain future work. | Duplicate and stale commands cannot settle twice; the exact stored trace can be reloaded and replayed. |
| 5. Expert agents and staged rollout | Partial | One explicit municipal food-site action has deterministic finance/readiness/supply/access advice and committed readiness, funding, delivery, commissioning, opening and closure events. These role notes are not LLM advisers and hold no command authority. Broader action catalog and ongoing staged world remain future work. | The bounded site uses finite resources, leaves capacity at zero until opening, records no-launch on failed prerequisites, and conserves kernel accounts and stock. |
| 6. Demonstration proposals and outcome tracking | Partial | One supported site proposal has a matched baseline/intervention pair and exact trace identity. The grocery, surplus-processing, and school-meal examples have not all been run through a generalized intake, and there is no multi-day outcome registry. | The bounded proposal reports its modeled access, service, household, and cost outcomes with source and assumption limits; broader proposals remain future work. |
| 7. Browser performance and recovery | Partial | Profile startup, frame time, memory, resize, WebGL failure or context loss, background-tab resume, and reconnect on the lowest-supported device. Keep usable non-3D controls available when WebGL fails. | Agreed performance targets pass on the declared browser and device matrix; recovery behavior is recorded. |

Each gate should end with an inspectable artifact and a recorded acceptance result before dependent work proceeds. Gate 1 reflects existing map and route work, with validation and expansion decisions still open. Gate 7 has browser controls to build on, but no target-device performance or recovery result is established. A prior prototype record reports a roughly 569 kB minified Three.js scene chunk; that bundle size is not a frame-rate or memory result. Measure download, rendering, and memory costs separately on the chosen devices.

## First implementation sequence

1. Validate the frozen Toronto source manifest, map coverage, coordinate systems, stable identifiers, route graph, and synthetic areas. Select the first active area and browser/device targets based on route and destination coverage, while preserving citywide context.
2. Expand the bounded Markdown intake into reusable proposal clarification and affected-party evidence workflows; the current exact-text revision and reviewer-defined scope are implemented.
3. Extend the Python simulation into a persistent world with shared pedestrian state, checkpoints, resume, branch, and replay. The current Council trace remains an independent six-hour scenario.
4. Extend the local versioned service contract to authoritative world snapshots, ordered events, and reconnect recovery. Council commands already use expected revision, idempotency receipts, and stored run traces.
5. Expand beyond the one municipal food-site action only with explicit plan schemas, finite prerequisites, kernel accounting, and matched-run verification.
6. Bring the grocery, surplus-processing, and school-food examples through the generalized intake and compare baseline, rollout, and adverse cases.
7. Profile the active area on the chosen device before increasing geometry detail, agent count, shadows, or continuous animation. Continue route review around crossings, waterfront paths, and the railway corridor; add landmark or Toronto massing detail only where it adds value, and expand the detailed area after navigation and performance are satisfactory.

## Scope and modeling boundaries

The first product release should connect Council chat and open proposal intake to the Toronto world, then run a persistent simulation where staged work changes infrastructure and proposal-specific outcomes are tracked. The grocery, surplus-food, and school-meal proposals are initial demonstration inputs, not a closed set of supported solution IDs. Their service rules and unresolved questions remain proposal-level unknowns until clarified. Delivery methods are modeled only when supported by proposal evidence and explicit scenario assumptions.

The project does not claim a complete digital twin, a calibrated citywide behavioral model, observed Toronto sentiment, unrestricted LLM autonomy, or real operational authority. Keep rules and simple baselines ahead of model complexity. Add small or LLM decisions only after observations, legal actions, replay, fallback behavior, and cost controls are defined.

No revised production schedule, budget, hosting topology, or device performance target is approved.
