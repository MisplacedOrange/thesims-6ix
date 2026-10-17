# System architecture

## Status and product boundary

The current visual milestone is implemented in apps/web as a standalone browser environment. It loads sourced Toronto geometry and generates seeded outdoor pedestrian itineraries. The browser samples that visual timeline directly. Public solutions, economic integration, and the Python service described below are deferred. See the [environment implementation](environment-implementation.md) for the current design.

The rest of this document proposes the broader service architecture for a Toronto 3D pedestrian simulation. The current browser environment is independent of the limited headless Python economic prototype described in [integration status](integration.md).

The product should open on a recognizable Toronto 3D context, then focus on active areas where geography, routes, pedestrians, services, and outcomes are modeled in detail. The first planner demonstration may stage the school-meal proposal, but schools do not define the city or the simulation clock.

## Caller experience

An analyst opens the browser app, loads a Toronto snapshot, selects a scenario, requests a rollout proposal, reviews the validated plan, runs a baseline and treatment, compares outcomes, and replays the result. The Python service executes both browser-visible and headless runs through the same authoritative code. The browser can also inspect a completed run without an active live session.

The following calls are sketches; they do not exist in the repository:

```text
sim6ix world inspect toronto-snapshot
sim6ix plan propose school-meals --horizon 10y
sim6ix plan validate plan.json
sim6ix run scenario.json --seed 17 --mode visible
sim6ix compare runs/base runs/rollout --by area,income
sim6ix replay runs/rollout
```

Plan drafts are not runnable until deterministic checks pass and the review record is attached. A run pins its map, population, policy, agent policy, model configuration, and code versions. The commands below are CLI sketches; the browser uses the same versioned service boundary.

## State ownership and flow

Licensed Toronto sources feed versioned geodata and evidence snapshots, which are assembled into a validated world package and scenario. The Python simulation service advances world time, pedestrian movement, decisions, policy events, and the economic kernel. It writes ordered run events and snapshots to the run archive. The browser receives snapshots and sequenced events, renders the 3D projection, and submits typed commands. Rules, optional small models, and bounded LLM calls run behind Python-side gateways. The rollout planner returns a structured draft that passes deterministic checks and recorded review before it can enter a scenario.

Python is the sole authority for logical time, positions, routes, physical activity, vehicle state, economic transactions, and policy activation. The browser owns presentation state only: camera, selection, labels, cosmetic interpolation, and unsent form drafts. It never settles purchases or advances policy capacity.

| State | Sole writer | Browser boundary |
| --- | --- | --- |
| Logical world clock, pedestrian and vehicle positions, active paths, physical activities | Python simulation service | Read-only snapshots and ordered events |
| Cash, food, reservations, transactions, public costs, modeled response variables | Python economic kernel through the service | Committed receipts and read-only projections |
| Scenario and approved rollout | Python study coordinator | Immutable, versioned package ID |
| Planner draft | Python planner adapter, then deterministic validator and reviewer | Draft and validation status; drafts cannot activate a stage |
| Run archive | Python run coordinator | Run metadata, snapshots, event sequence, hashes |
| Camera, selection, labels, temporary UI drafts | Browser client | Local presentation state; never canonical run state |

Commands carry a schema version, run ID, command ID/idempotency key, expected revision, and typed payload. The service rejects stale or invalid commands without partial state change and returns a committed receipt or explicit rejection. Live updates carry a schema version, run ID, monotonically increasing sequence, simulation time, revision, event type, and payload. If a client detects a sequence gap or reconnects, it requests a snapshot and resumes from the returned sequence. The browser shows an economic or rollout change only after the corresponding committed event or receipt arrives. Interpolation may smooth positions between authoritative samples but cannot change their endpoint values.

## Pedestrian decisions

People are embodied pedestrian agents; a household remains the owner of money and pantry state. A person may walk, attend a service, shop under a household mandate, or wait. The Python side creates a finite set of legal intents from the current observation. Rules handle routine decisions; small models or a fixed, budgeted LLM panel can select among those options. An LLM response cannot spend money, create food, move a person off-network, or invent a destination.

The study fixes which agents receive model calls before the run. Camera location does not affect selection. Invalid, late, unavailable, or unaffordable responses use a recorded deterministic fallback. The gateway receives no unrestricted database tools or credentials from the world process.

## Rollout planning and activation

The infrastructure planner works on a slower policy timescale than pedestrian movement. It receives a frozen map and evidence snapshot, selected solution IDs, available funds, current capacity, constraints, and a planning horizon. It returns a structured draft with candidate sites, dependencies, staffing or equipment needs, cost estimates or explicit unknowns, stage windows, capacity ramps, risks, source IDs, and stop conditions.

A deterministic validator checks source references, units, site eligibility, costs, dependencies, timing, and capacity. Review and approval are recorded against the plan hash. During a run, the world can show a planned stage, but Python checks prerequisites and funds and commits the activation before the stage becomes operational or changes economic capacity. Rejected, delayed, reduced, and canceled stages remain visible in the event history.

## Proposed technology map

| Component | Proposed technology | Current status |
| --- | --- | --- |
| Browser UI and 3D scene | TypeScript, React, Three.js, Vite | Local prototype with one synthetic recording; no live service |
| World simulation and agent movement | Python 3.10+ service using the existing simulation code as a base | World clock, pedestrian graph, and movement are not implemented |
| Economic and policy kernel | Existing Python packages | Limited headless prototype |
| Browser/API boundary | Versioned HTTP commands and snapshots; WebSocket event updates; FastAPI is a candidate | Not implemented |
| Resident decision policies | Python rules first; optional small model and bounded LLM adapter | Rules exist for household choices; pedestrian policies do not |
| Infrastructure planner | Python planner boundary with structured LLM output and deterministic validator | Not implemented |
| Run archive and replay | SQLite transactions plus immutable, content-hashed files for local runs | Terminal exports exist; durable live-run storage does not |
| Toronto data ingestion | Python geospatial pipeline; library and asset formats follow source audit | Not implemented; source layers are not ingested |
| Deployment | Static frontend plus local or hosted Python service | Topology, access control, and hosting are open decisions |

This is the proposed stack, not a complete implementation. The browser prototype currently uses TypeScript, React, Three.js, and Vite but only reads a fixed synthetic recording. Python remains responsible for the authoritative world and economic simulation in the proposed design. The exact GIS libraries, model runtimes, hosting mode, and browser/device matrix remain open.

## Time, replay, and persistence

The Python service advances logical simulation time to the next decision or physical event boundary, not once per rendered frame. Store integer seconds against a UTC scenario epoch and use `America/Toronto` for schedules and display. School calendars are one input among many local schedules; the clock spans the scenario horizon. Browser playback speed controls how quickly recorded time is presented; they do not alter server time or event ordering.

Seed independent random streams by resident or household, day, decision opportunity, and purpose. A change in policy-dependent event counts must not shift unrelated weather or income draws. Save algorithm versions and counters.

For a local run, use one Python archive writer and transactional SQLite records for metadata, world events, economic events, decision receipts, planner approvals, and checkpoint pointers. Keep source data and exports immutable with content hashes. A checkpoint includes both world and economic revisions, the pending queue, random counters, source references, and budget reservations.

Replay makes no model calls. It uses recorded decisions, service receipts, events, and pinned versions. A new live-model run gets a new run ID. Compare separate world and economic hashes; exclude camera position, cosmetic animation, and frame rate.

## Browser performance and device support

The 3D client can become GPU-bound from drawing resolution, shadows, geometry, and overdraw, or CPU-bound from many separate scene objects, labels, and per-frame UI updates. The local prototype's Three.js scene chunk is about 569 kB minified (143 kB gzip); this is a download-size warning, not evidence of slow rendering or acceptable device performance. Profile startup/download cost separately from steady-state frame time and memory.

Load detailed geometry only for the active area and use simplified citywide context. For repeated buildings, trees, or pedestrians, profile draw calls and use instancing or merged static geometry where individual movement is unnecessary. Use distance-based detail and frustum culling, limit shadows and pixel ratio on constrained devices, and avoid continuously rendering a static paused scene. The Three.js manuals describe [on-demand rendering](https://threejs.org/manual/pages/rendering-on-demand.html), [optimizing many objects](https://threejs.org/manual/pages/optimize-lots-of-objects.html), and [capping drawing-buffer resolution](https://threejs.org/manual/pages/responsive.html). These are options to validate against this scene, not optimizations already completed.

Before choosing a supported browser/device matrix, measure scene load time, p50/p95 frame time during camera motion and agent movement, peak memory, context-loss recovery, and behavior after a background-tab pause. Test on the lowest-powered intended device, including integrated graphics or mobile hardware if those are in scope. A candidate acceptance target is a stable 30 frames per second during ordinary interaction on the lowest-supported device, but no target is approved until that device and scene scale are specified. Preserve an accessible list/table fallback when WebGL is unavailable.

## Safety, failure, and acceptance

| Failure | Required behavior |
| --- | --- |
| Stale revision or invalid API command | Reject without partial state change |
| Economic invariant failure | Stop the run and mark affected results invalid |
| Planner source, geography, cost, or dependency failure | Reject or request revision; never activate from text alone |
| Model timeout, refusal, invalid intent, or budget exhaustion | Record the reason and use the configured rule fallback |
| Browser disconnect, background-tab pause, or event-sequence gap | Keep server simulation authoritative; recover from a current snapshot and continue from its sequence |
| Runtime or service restart | Preserve committed state and resume from a compatible checkpoint |
| Partial export or unsupported replay version | Reject downstream use with an actionable diagnostic |

The first technical gate is one synthetic resident moving on a Toronto pedestrian graph in the Python service, with a browser client rendering timestamped positions and submitting one legal economic action. Verify the same recorded run headlessly and through the browser produces matching authoritative world and economic hashes. Establish device performance targets after the active-area scale and supported hardware are specified.
