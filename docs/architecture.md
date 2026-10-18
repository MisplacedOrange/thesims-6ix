# System architecture

## Status and product boundary

The implemented foundation is apps/web: a standalone browser environment with sourced Toronto geometry, seeded outdoor pedestrian itineraries, and playback for a bounded six-hour food-access scenario. Python generates and settles those scenario traces, which the browser replays without a live service. This is separate from the older `sim.integration` fixture. Proposal chat, department agents, persistent world simulation, and ongoing policy rollout remain unimplemented. See the [environment implementation](environment-implementation.md) for the visual foundation and [integration status](integration.md) for current simulation boundaries.

This document specifies the proposed ongoing architecture. The current recommendation is a TypeScript/React/Three.js browser client backed by a Python-authoritative simulation service. This meets the browser-delivery requirement while reusing the Python economic code and keeping one authoritative event and replay path. It is an architecture judgment, not a performance benchmark. The main risks are rendering scale on lower-powered devices and keeping the client projection synchronized after dropped connections. API ownership, hosting, and the supported browser/device matrix remain open.

The product opens on a recognizable Toronto 3D context, with a Council chat beside the evolving city. The user can upload a Markdown proposal, clarify its interpretation, and review a sourced record of requested changes, outcomes, constraints, assumptions, and unknowns. Simulated expert roles coordinate work packages, and a validated, approved rollout changes the simulated city over time. The initial grocery, food processing, and school-food proposals are examples for the common intake path, not a closed catalog.

## Caller experience

The user opens the browser app, reviews the ongoing Toronto world, and uploads a Markdown proposal in the side-panel Council chat, which serves as the simulated Council's working session. The chat helps clarify and version the proposal; it retains sources and extracts proposed changes, outcome measures, constraints, assumptions, and unknowns. The user reviews the structured record and simulated expert-agent work packages, then records the simulated Council decision. Once approved and validated, stages enter the ongoing simulation, where the city continues running and records outcomes, delays, and state changes. Users can inspect checkpoints, compare a baseline with rollout branches, and replay recorded runs. The Python service executes visible and headless runs through the same authoritative code. The decision procedure remains an open design choice; no decision authorizes real City action.

The following calls are sketches; they do not exist in the repository:

```text
sim6ix world inspect toronto-snapshot
sim6ix proposal import proposal.md
sim6ix proposal review proposal.json
sim6ix plan validate plan.json
sim6ix run scenario.json --seed 17 --mode visible
sim6ix compare runs/base runs/rollout --by area,income
sim6ix replay runs/rollout
```

These calls are interface sketches, not implemented commands. Proposal interpretation and department recommendations remain drafts until sources, measures, unknowns, feasibility checks, and the human review record are attached. No stage activates from text alone. A run pins its map, population, proposal, policy, agent policy, model configuration, and code versions. The browser uses the same versioned service boundary.

## State ownership and flow

Licensed Toronto sources and proposal references feed versioned evidence records and a validated world package. Proposal intake preserves the uploaded Markdown and produces a reviewable structured record; it must expose unsupported claims and missing values as unknowns. Simulated expert agents for relevant roles (for example public health, planning and construction, finance and procurement, food operations, and logistics) propose coordinated work packages and record disagreements. The Python simulation service advances world time, pedestrian movement, decisions, policy events, and the economic kernel. It writes ordered run events and snapshots to a persistent archive so an ongoing world can checkpoint, resume, branch, and replay. The browser receives snapshots and sequenced events, renders the 3D projection, and submits typed commands. Rules, optional small models, and bounded LLM calls run behind Python-side gateways.

Python is the sole authority for logical time, positions, routes, physical activity, vehicle state, economic transactions, and policy activation. The browser owns presentation state only: camera, selection, labels, cosmetic interpolation, and unsent form drafts. It never settles purchases or advances policy capacity.

| State | Sole writer | Browser boundary |
| --- | --- | --- |
| Logical world clock, pedestrian and vehicle positions, active paths, physical activities | Python simulation service | Read-only snapshots and ordered events |
| Cash, food, reservations, transactions, public costs, modeled response variables | Python economic kernel through the service | Committed receipts and read-only projections |
| Proposal decision and approved rollout | Python simulation coordinator | Immutable, versioned proposal and rollout IDs |
| Uploaded proposal, source links, measures, unknowns, and revisions | Python proposal coordinator; user edits/reviews in Council chat | Versioned proposal record; Markdown source remains traceable |
| Planner draft | Python planner adapter, then deterministic validator and reviewer | Draft and validation status; drafts cannot activate a stage |
| Department work packages and disagreements | Python coordinator records bounded expert-agent outputs | Proposed work, dependencies, evidence, and unresolved items; recommendations do not directly mutate the world |
| Run archive | Python run coordinator | Run metadata, snapshots, event sequence, hashes |
| Camera, selection, labels, temporary UI drafts | Browser client | Local presentation state; never canonical run state |

Commands carry a schema version, run ID, command ID/idempotency key, expected revision, and typed payload. The service rejects stale or invalid commands without partial state change and returns a committed receipt or explicit rejection. Live updates carry a schema version, run ID, monotonically increasing sequence, simulation time, revision, event type, and payload. If a client detects a sequence gap or reconnects, it requests a snapshot and resumes from the returned sequence. The browser shows an economic or rollout change only after the corresponding committed event or receipt arrives. Interpolation may smooth positions between authoritative samples but cannot change their endpoint values.

## Pedestrian decisions

People are embodied pedestrian agents; a household remains the owner of money and pantry state. A person may walk, attend a service, shop under a household mandate, or wait. The Python side creates a finite set of legal intents from the current observation. Rules handle routine decisions; small models or a fixed, budgeted LLM panel can select among those options. An LLM response cannot spend money, create food, move a person off-network, or invent a destination.

The study fixes which agents receive model calls before the run. Camera location does not affect selection. Invalid, late, unavailable, or unaffordable responses use a recorded deterministic fallback. The gateway receives no unrestricted database tools or credentials from the world process.

## Proposal intake and department planning

The Council chat is the proposal intake and review surface, not a source of authoritative facts. It accepts Markdown, preserves the uploaded version, and helps the user resolve ambiguous goals or metrics. Each extracted outcome measure records its definition, unit, population/geography, time window, evidence source, and whether it is observed, proposed, or modeled. Missing values and contested evidence remain explicit unknowns; amendments create a new version rather than rewriting the history.

Expert agents represent simulated responsibilities of relevant municipal departments and delivery partners. They work from the approved proposal, frozen evidence, current world state, and explicit budgets and constraints. For example, public health can review service and safety assumptions, planning/construction can identify site and readiness dependencies, finance/procurement can identify funding and contracts, and food/logistics roles can model supply and delivery. Their outputs are recommendations and work packages; they do not have real department authority or unrestricted tools.

Each proposal version should also carry an impact and actor map: affected population groups; businesses and organizations that control relevant sites, services, labor, supply, or delivery; responsible public authorities; likely direct and spillover effects; available evidence; and unresolved gaps. Economic organizations may receive bounded state and decision rules when evidence supports a mechanism such as pricing, inventory, staffing, procurement, or service capacity. Their actions must remain inside scenario contracts and budgets, and must be committed through the authoritative economic interface. A mapped business or simulated company agent does not establish a real operator's current status, incentives, or consent.

Record resident, worker, business, and community input as dated, source-linked consultation or survey evidence, separate from synthetic agent behavior and simulated expert recommendations. Preserve geography, method, population reached, consent or publication limits, disagreement, and known representation gaps. Neither generated dialogue nor a simulated stakeholder role is evidence of what a real group believes or a claim that the group was consulted.

## Rollout planning and activation

The coordinated planning team works on a slower policy timescale than pedestrian movement. It receives the approved proposal and version, frozen map and evidence snapshot, available funds, current capacity, constraints, and a planning horizon. It returns structured work packages with candidate sites, dependencies, staffing or equipment needs, cost estimates or explicit unknowns, stage windows, capacity ramps, proposal-linked outcome measures, risks, source IDs, and stop conditions. Conflicting recommendations and unresolved assumptions remain visible for review.

A deterministic validator checks source references, units, site eligibility, costs, dependencies, timing, capacity, and metric definitions. Review and approval are recorded against the proposal and plan versions. During an ongoing run, the world can show a planned stage, but Python checks prerequisites and funds and commits activation before it becomes operational or changes economic capacity. Rejected, delayed, reduced, and canceled stages remain visible in the event history. Proposal-specific outcome measures are recorded at declared intervals and linked to the relevant stages; unknown or unavailable measures are marked as such rather than filled by generated text.

## Proposed technology map

| Component | Proposed technology | Current status |
| --- | --- | --- |
| Browser UI and 3D scene | TypeScript, React, Three.js, Vite | Local visual prototype with seeded itineraries and bounded food-access trace playback; no persistent live service |
| World simulation and agent movement | Python 3.10+ service using the existing simulation code as a base | Bounded six-hour routes and choices are generated for playback; persistent world clock and ongoing agent movement service are not implemented |
| Economic and policy kernel | Existing Python packages | Bounded food-access runner and separate legacy headless district fixture; no persistent policy-run service |
| Browser/API boundary | Versioned HTTP commands and snapshots; WebSocket event updates; FastAPI is a candidate | Not implemented |
| Resident decision policies | Python rules first; optional small model and bounded LLM adapter | Deterministic rules exist in the bounded food-access scenario; persistent pedestrian policies and LLM calls are not implemented |
| Infrastructure planner | Python planner boundary with structured LLM output and deterministic validator | Not implemented |
| Council chat and proposal intake | Browser side panel, versioned Markdown record, source and metric extraction | Not implemented |
| Department expert roles | Coordinated, bounded role agents with recorded recommendations and disagreements | Not implemented |
| Run archive and replay | SQLite transactions plus immutable, content-hashed files for local runs | Terminal exports exist; durable live-run storage does not |
| Toronto spatial data | Frozen, attributed Toronto geometry and a walking graph are used by the browser and bounded food-access traces | Expand source coverage and connect validated map assets to a persistent world package |
| Deployment | Static frontend plus local or hosted Python service | Topology, access control, and hosting are open decisions |

This is the proposed stack, not a complete implementation. The browser prototype currently uses TypeScript, React, Three.js, and Vite to render the Toronto environment and seeded pedestrian itineraries on a connected map. It has no live Python service. Python remains responsible for the authoritative world and economic simulation in the proposed design. The exact GIS libraries, model runtimes, hosting mode, and browser/device matrix remain open.

## Time, replay, and persistence

The Python service advances logical simulation time to the next decision or physical event boundary, not once per rendered frame. Store integer seconds against a UTC scenario epoch and use `America/Toronto` for schedules and display. School calendars are one input among many local schedules; the clock spans the scenario horizon. Browser playback speed controls how quickly recorded time is presented; they do not alter server time or event ordering.

Seed independent random streams by resident or household, day, decision opportunity, and purpose. A change in policy-dependent event counts must not shift unrelated weather or income draws. Save algorithm versions and counters.

For an ongoing local run, use one Python archive writer and transactional SQLite records for metadata, world events, economic events, decision receipts, proposal versions, outcome measurements, department work packages, planner approvals, and checkpoint pointers. Keep proposal Markdown, source data, and exports immutable with content hashes. A checkpoint includes world and economic revisions, current infrastructure stages, the pending queue, random counters, source references, and budget reservations so the run can resume or fork without losing its audit trail.

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

## First end-to-end proof

Build the smallest runnable slice before expanding the city:

1. Reuse the frozen Toronto map and source-feature IDs in both the browser and Python world package; validate the shared coordinate transform and walking graph.
2. Advance one synthetic resident on a valid pedestrian graph in the Python service, both with the browser connected and headlessly.
3. Submit one legal trip or purchase command with a stable command ID and expected revision.
4. Receive one committed Python economic receipt and show its effect only after acceptance.
5. Replay the same recorded inputs and compare authoritative world and economic hashes; frame rate and camera state must not affect them.
6. Measure frame time, memory, load time, and reconnect recovery on the selected lowest-supported device.

If this proof cannot preserve ordering and replay, reconsider the API and run-coordinator boundaries before adding population or policy complexity. Do not increase scene detail or agent counts until the lowest-supported device passes the agreed performance gate.

Three.js is distributed as browser JavaScript and its official guide recommends npm with a build tool such as Vite for most projects: [Three.js installation](https://threejs.org/manual/pages/installation.html).
