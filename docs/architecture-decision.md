# Architecture decision: browser simulation client

## Decision status

The active visual milestone is a standalone TypeScript, React, and Three.js environment in apps/web. Seeded pedestrian itineraries run in the browser without a Python service. The user has deferred public solutions and economic outcomes. The Python-authoritative service design below is a future proposal, not a dependency of this milestone.

Browser delivery is now a product requirement. The browser prototype in apps/web demonstrates UI, a simple Three.js scene, and playback of one fixed synthetic recording; it does not execute or connect to the simulation.

The proposed production direction is a **browser client in TypeScript/React and Three.js, backed by a Python-authoritative simulation service**. The browser renders a Toronto scene, accepts user commands, and interpolates committed state updates. Python advances logical time and resident movement and remains the only writer of economic state. This architecture is not implemented; API ownership, hosting, and the supported browser/device matrix remain open.

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
| Durable ordered run archive and comparison export | Python run coordinator |
| Meshes, camera, selection, labels, and cosmetic interpolation | Browser client |

Every command carries a run ID, command ID/idempotency key, expected revision, and typed payload. The service validates and commits it, then returns a receipt. The browser displays a purchase or rollout activation only after receiving the committed result. Live event messages carry a schema version, run ID, sequence number, logical time, and revision. On a sequence gap or reconnect, the client requests a current snapshot and resumes from its sequence. Pedestrian movement and visual interpolation never settle economic transactions.

## Proposed stack

- **Browser app:** TypeScript and React for accessible controls and views; Three.js for the 3D scene; Vite for development and production bundling. This matches the local frontend prototype, not a completed simulator client.
- **Simulation and economics:** existing Python 3.10+ code, extended so one Python service owns logical world state, agent movement, economics, and run orchestration.
- **API:** a versioned HTTP command/snapshot interface plus WebSocket event updates is a candidate. FastAPI is a candidate Python framework, not a fixed dependency. Commands need idempotency and expected-revision checks; event streams need sequence numbers and snapshot recovery.
- **Local persistence:** SQLite transactional archive with immutable, content-hashed input and result files. Hosted storage is not selected.
- **Geospatial ingestion:** Python pipeline; GIS libraries and exact Toronto layers are selected after auditing download formats, CRS, licensing, and coverage.
- **Models:** deterministic rules first; optional small-model runtime and bounded server-side LLM adapter after replay and budgets exist.
- **Deployment:** static browser assets and the Python service may be local or hosted; select this after deciding whether the first release is single-user or shared.

The existing simulation implementation remains a headless Python economic prototype. The local apps/web prototype uses fixed synthetic snapshots and has no simulation API. The repository has no authoritative pedestrian world, live API, durable run archive, Toronto map ingestion, planner, or pedestrian model calls. Browser performance and supported devices have not been measured.

## First proof

Build the smallest runnable slice before expanding the city:

1. Load one frozen Toronto map area and source-feature IDs in the browser.
2. Advance one synthetic resident on a valid pedestrian graph in the Python service, both with the browser connected and headlessly.
3. Submit one legal trip or purchase command with a stable command ID and expected revision.
4. Receive one committed Python economic receipt and show its effect only after acceptance.
5. Replay the same recorded inputs and compare authoritative world and economic hashes; frame rate and camera state must not affect them.
6. Measure frame time, memory, load time, and reconnect recovery on the selected lowest-supported device.

If this proof cannot preserve ordering and replay, reconsider the API and run-coordinator boundaries before adding population or policy complexity. Do not increase scene detail or agent counts until the lowest-supported device passes the agreed performance gate.

Three.js is distributed as browser JavaScript and its official guide recommends npm with a build tool such as Vite for most projects: [Three.js installation](https://threejs.org/manual/pages/installation.html).

## Scope implications

The city scene is the primary environment. A school meal expansion can demonstrate infrastructure planning, but a school calendar does not define the simulation horizon. The planner may design kitchen, storage, staffing, procurement, and delivery stages for that case after the service rules are defined. Municipal groceries and food rescue/processing remain separate solution entries. Drone delivery is an optional logistics comparison.

The prior 16-week plan and CAD 252,480 illustrative budget are superseded. No replacement schedule or budget is approved in this document. The browser client and Python simulation service still need an agreed local-versus-hosted deployment model and browser/device support matrix.
