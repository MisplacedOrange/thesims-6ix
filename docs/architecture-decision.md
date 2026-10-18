# Architecture decision: browser simulation client

## Decision status

The implemented milestone is a TypeScript, React, and Three.js environment in apps/web with bounded pedestrian food interactions. Python exports deterministic six-hour runs, settling cash, food, and service through the existing kernel; the browser replays routes and committed projections without a persistent Python service. See the [implemented interaction contract](../sim/interactables/README.md). The product target includes Council chat for Markdown proposals, department expert agents, and an ongoing Python-authoritative city simulation. Those target capabilities remain planned.

Browser delivery is a product requirement. The browser prototype in apps/web renders the frozen Toronto map, seeded pedestrian itineraries, and bounded food-access trace playback; it does not connect to an ongoing authoritative simulation service.

The proposed production direction is a **browser client in TypeScript/React and Three.js, backed by a Python-authoritative simulation service**. The browser presents the city and Council chat, accepts Markdown proposals and typed user commands, and interpolates committed state updates. Bounded expert agents produce reviewable work packages; Python advances logical time and resident movement and remains the only writer of infrastructure and economic state. The simulation runs continuously through staged changes, with durable checkpoints and replay. This architecture is not implemented; API ownership, hosting, and the supported browser/device matrix remain open.

## Alternatives

| Option | Strength for this product | Main cost or risk |
| --- | --- | --- |
| Python-authoritative simulation + browser Three.js client | Direct browser access, one authoritative event/replay path, and reuse of Python economics | Large scenes and agent counts need profiling and level-of-detail controls; service deployment and reconnection must be designed |

The browser-native option is the current recommendation because it serves the product requirement while keeping the existing Python economic code on the authoritative path. This is an architecture judgment, not a performance benchmark. The highest risks are rendering scale on lower-powered devices and keeping the client projection synchronized after dropped connections.

## Ownership rule

| State or behavior | Authority |
| --- | --- |
| Simulation clock, pedestrian and vehicle positions, paths, activities, and policy-event ordering | Python simulation service |
| Money, food, household accounts, procurement, public costs, budgets, and settled service outcomes | Existing Python economic kernel, called by the simulation service |
| Plan drafts, source references, deterministic validation, review records, and scenario definitions | Python coordinator |
| Proposal versions, outcome definitions, unknowns, and department recommendations | Python proposal/planning coordinator; user review through Council chat |
| Durable ordered run archive and comparison export | Python run coordinator |
| Meshes, camera, selection, labels, and cosmetic interpolation | Browser client |

Every command carries a run ID, command ID/idempotency key, expected revision, and typed payload. The service validates and commits it, then returns a receipt. The browser displays a purchase or rollout activation only after receiving the committed result. Live event messages carry a schema version, run ID, sequence number, logical time, and revision. On a sequence gap or reconnect, the client requests a current snapshot and resumes from its sequence. Pedestrian movement and visual interpolation never settle economic transactions.

## Proposed stack

- **Browser app:** TypeScript and React for accessible controls and views; Three.js for the 3D scene; Vite for development and production bundling. This matches the local frontend prototype, not a completed simulator client.
- **Simulation and economics:** existing Python 3.10+ code, extended so one Python service owns logical world state, agent movement, economics, and run orchestration.
- **API:** a versioned HTTP command/snapshot interface plus WebSocket event updates is a candidate. FastAPI is a candidate Python framework, not a fixed dependency. Commands need idempotency and expected-revision checks; event streams need sequence numbers and snapshot recovery.
- **Local persistence:** SQLite transactional archive with immutable, content-hashed input and result files. Hosted storage is not selected.
- **Geospatial inputs:** The browser and bounded food-access traces use frozen, attributed downtown OpenStreetMap geometry and a walking graph. `sim/data` also supports a narrow City GIS candidate acquisition flow; broader layer coverage, CRS and licensing audits, and integration into a validated world package remain open.
- **Models:** deterministic rules for routine behavior and authoritative checks; optional small-model or bounded server-side LLM adapters for pedestrian choices and department recommendations after replay, source grounding, validation, and budgets exist.
- **Deployment:** static browser assets and the Python service may be local or hosted; select this after deciding whether the first release is single-user or shared.

The existing Python code includes a headless economic prototype and a bounded food-access trace generator; apps/web replays the resulting routes and committed event projections without a persistent service. The repository has no authoritative ongoing pedestrian world, live API, durable run archive, infrastructure planner, or pedestrian model calls. Browser performance and supported devices have not been measured.

## First proof

Build the smallest runnable slice before expanding the city:

1. Reuse the frozen Toronto map and source-feature IDs in both the browser and the Python world package, validating the shared coordinate transform and walking graph.
2. Advance one synthetic resident on a valid pedestrian graph in the Python service, both with the browser connected and headlessly.
3. Submit one legal trip or purchase command with a stable command ID and expected revision.
4. Receive one committed Python economic receipt and show its effect only after acceptance.
5. Replay the same recorded inputs and compare authoritative world and economic hashes; frame rate and camera state must not affect them.
6. Measure frame time, memory, load time, and reconnect recovery on the selected lowest-supported device.

If this proof cannot preserve ordering and replay, reconsider the API and run-coordinator boundaries before adding population or policy complexity. Do not increase scene detail or agent counts until the lowest-supported device passes the agreed performance gate.

Three.js is distributed as browser JavaScript and its official guide recommends npm with a build tool such as Vite for most projects: [Three.js installation](https://threejs.org/manual/pages/installation.html).

## Scope implications

The city scene and evolving infrastructure are the primary environment. A school meal expansion is one initial demonstration proposal alongside municipal groceries and food rescue/processing; none defines a closed catalog or the simulation horizon. All three should enter through the same Markdown intake and review flow. The planner may design the relevant sites, staffing, procurement, service, and delivery stages once their rules and unknowns are defined. Delivery technologies are options raised by a proposal, not special product modes.

No replacement schedule or budget is approved in this document. The browser client and Python simulation service still need an agreed local-versus-hosted deployment model and browser/device support matrix.
