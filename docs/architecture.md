# System architecture

## Status and product boundary

The browser foundation renders sourced Toronto geometry, seeded pedestrian itineraries, and preset playback for a bounded six-hour food-access scenario. The Python code provides a local Council workflow in `sim/council.py`: exact Markdown revisions, proposal-linked organization and stakeholder-input records, explicit scope and plan records, reviewer decisions, an immutable SQLite receipt history, and paired baseline/intervention traces for one hypothetical municipal food site. The browser can create those records and inspect their links on saved rollout events; scope, plan, decision, and run controls are not currently exposed. Organization references are review context, not proposal-responsive behavior, and stakeholder records are user-entered evidence, not outreach. The feature is a bounded scenario service; it does not create a persistent multi-day world or claim real City authority. This remains separate from the older `sim.integration` fixture. See the [environment guide](../apps/web/README.md) and [integration status](integration.md).

The active architecture work supports four priorities: the complete Council flow, bounded organization decisions, source-linked stakeholder evidence, and persistent multi-day state. The current TypeScript/React/Three.js client remains the review and replay surface; Python owns time, resources, and committed events. The existing browser scene is retained as context. City expansion, rendering-performance work, hosting, and device-matrix decisions are deferred from the active roadmap.

The active workflow starts with a Markdown proposal and creates a reviewable record of requested changes, outcomes, constraints, assumptions, and unknowns. It adds an impact and actor map, attaches actual stakeholder evidence separately from synthetic behavior, and proceeds through typed planning, explicit human review, a persistent run, and traceable results. The first supported site action is a pilot, not a commitment to a general action catalog.

## Caller experience

The user submits and versions a Markdown proposal, adds source-labeled organization and stakeholder-input records, reviews the evidence and impact map, defines the evaluated scope, and records a decision on the exact typed plan. The Python service executes a matched baseline and intervention and persists receipts and traces; multi-day checkpoints are not implemented. The browser displays proposal, actor, and input records, while scope, plan, decision, and run controls remain active implementation work. No decision authorizes real City action.

The following broader world and proposal commands are sketches; they do not exist in the repository:

```text
sim6ix world inspect toronto-snapshot
sim6ix proposal import proposal.md
sim6ix proposal review proposal.json
sim6ix run scenario.json --seed 17 --mode visible
sim6ix compare runs/base runs/rollout --by area,income
sim6ix replay runs/rollout
```

The `sim6ix` calls above remain design sketches. The local Council service has a narrower implemented HTTP boundary: `GET /api/council`, `POST /api/council/{proposals,scopes,plans,decisions,runs}`, and `GET /api/council/runs/{run_id}/traces/{arm}`. Mutations require schema version 1, the expected Council revision, and an idempotency key. Its detailed contract lives with the local app guide and Python implementation.

## State ownership and flow

Licensed Toronto sources, proposal references, organization records, and actual stakeholder submissions feed versioned evidence. Proposal intake preserves the uploaded Markdown and exposes unsupported claims and missing values as unknowns. The planned Python simulation service advances world time, pedestrian movement, organization decisions, policy events, and economic settlement, then writes ordered events and snapshots so a run can checkpoint, resume, branch, and replay. The browser receives snapshots, renders the projection, and submits typed commands. The active pilot uses deterministic rules and human review; small models and LLM calls are deferred.

Python is the sole authority for logical time, pedestrian positions and routes, organization resources, economic transactions, and policy activation. The browser owns presentation state only: camera, selection, labels, cosmetic interpolation, and unsent form drafts. It never settles purchases or advances policy capacity. Traffic and vehicle behavior are outside the active model scope.

| State | Sole writer | Browser boundary |
| --- | --- | --- |
| Logical world clock, pedestrian and vehicle positions, active paths, physical activities | Python simulation service | Read-only snapshots and ordered events |
| Cash, food, reservations, transactions, public costs, modeled response variables | Python economic kernel through the service | Committed receipts and read-only projections |
| Uploaded proposal, source links, measures, unknowns, and revisions | Python proposal coordinator; user edits/reviews in Council chat | Versioned proposal record; Markdown source remains traceable |
| Stakeholder submissions and consultation evidence | Versioned evidence records with access and consent limits | Source-linked consultation/partner records, separate from synthetic agents |
| Run archive | Python run coordinator | Run metadata, snapshots, event sequence, hashes |
| Camera, selection, labels, temporary UI drafts | Browser client | Local presentation state; never canonical run state |

The local Council mutation boundary currently requires schema version 1, an expected session revision, an idempotency key, and a typed body. It rejects stale or invalid commands without partial database mutation and returns a stored receipt or explicit error. Future world commands also need run IDs and ordered event sequences; snapshots, reconnect recovery, and the live world event stream remain design requirements. The browser shows a Council effect only from a stored trace and its committed rollout events. Interpolation may smooth pedestrian positions between authoritative samples but cannot change their endpoint values.

## Pedestrian decisions

People are synthetic pedestrian agents; a household remains the owner of money and pantry state. A person may walk, attend a service, shop under a household mandate, or wait. The Python side creates legal options from the current observation and the bounded food-access scenario uses deterministic rules. Model-based or LLM decisions are deferred from the active scope. Synthetic behavior supports impact analysis and does not represent consultation or the views of real people.

The study fixes which agents receive model calls before the run. Camera location does not affect selection. Invalid, late, unavailable, or unaffordable responses use a recorded deterministic fallback. The gateway receives no unrestricted database tools or credentials from the world process.

## Proposal intake

The Council panel is the proposal and evidence-recording surface, not a source of authoritative facts. The service preserves submitted Markdown exactly, classifies only explicit `## Constraints`, `## Measures`, `## Assumptions`, `## Goals`, `## Changes`, and `## Unknowns` headings, and keeps other text unclassified. Source links are marked unverified; no retrieval or LLM interpretation occurs. Organization and stakeholder-input records are versioned separately from proposal text; they do not verify sources, conduct consultation, or generate organizational decisions. The remaining UI work is an impact map, reviewer-defined scope, typed plan, explicit decision, and stored-run access. Proposal revisions do not rewrite earlier text. Synthetic dialogue is not public input.

## Agent planning and rollout

See the [agent planner plan](agent-planner-plan.md) for the planner contract, action catalog, milestone scheduler, authority checks, and acceptance gates.

## Proposed technology map

| Component | Proposed technology | Current status |
| --- | --- | --- |
| Browser UI and 3D scene | TypeScript, React, Three.js, Vite | Local visual prototype; Council UI supports proposal, organization, and stakeholder-input records, but not scope, plan, decision, or run controls |
| World simulation and agent movement | Python 3.10+ service using the existing simulation code as a base | Bounded six-hour routes and choices are generated for playback; persistent world clock and ongoing agent movement service are not implemented |
| Organization decisions | Python rules and the economic kernel | Basic stock, prices, delivery, and service state exist; proposal-responsive organization decisions are not generally implemented |
| Stakeholder evidence | Versioned source-linked records | Manual group-level input records are implemented; outreach, verification, and representativeness review are not |
| Economic and policy kernel | Existing Python packages | Bounded food-access runner and separate legacy headless district fixture; no persistent policy-run service |
| Browser/API boundary | Versioned HTTP commands and snapshots; WebSocket event updates; FastAPI is a candidate | Local Council HTTP commands use schema 1, SQLite receipts, revision checks, and idempotency; ongoing-world snapshots and event streams are not implemented |
| Resident and organization decisions | Python deterministic rules and typed actions | Deterministic household rules exist in the bounded food-access scenario; proposal-responsive organization decisions and persistent policies are not implemented |
| Council chat and proposal intake | Browser side panel, versioned Markdown and actor/input records | Python service stores scope/plan/decisions and paired traces; browser scope, plan, decision, and run controls remain to implement |
| Run archive and replay | SQLite transactions plus immutable, content-hashed files for local runs | Council command receipts and paired traces survive service restart; persistent world state, checkpoints, and multi-day replay are not implemented |
| Toronto spatial data | Frozen, attributed Toronto geometry and a walking graph are used by the browser and bounded food-access traces | Expand source coverage and connect validated map assets to a persistent world package |
| Deployment | Static frontend plus local or hosted Python service | Topology, access control, and hosting are open decisions |

This is the proposed stack, not a complete implementation. The browser prototype uses TypeScript, React, Three.js, and Vite to render the Toronto environment and seeded pedestrian itineraries on a connected map. The local Council API is a Python development service for one bounded plan and paired trace; it does not advance a durable world clock. Python remains responsible for the authoritative world and economic simulation in the broader design. GIS libraries, model runtimes, hosting mode, and browser/device matrix remain open.

## Time, replay, and persistence

The Python service advances logical simulation time to the next decision or physical event boundary, not once per rendered frame. Store integer seconds against a UTC scenario epoch and use `America/Toronto` for schedules and display. School calendars are one input among many local schedules; the clock spans the scenario horizon. Browser playback speed controls how quickly recorded time is presented; they do not alter server time or event ordering.

Seed independent random streams by resident or household, day, decision opportunity, and purpose. A change in policy-dependent event counts must not shift unrelated weather or income draws. Save algorithm versions and counters.

For an ongoing local run, use one Python archive writer and transactional SQLite records for metadata, world events, economic events, decision receipts, proposal versions, outcome measurements, and checkpoint pointers. Keep proposal Markdown, source data, and exports immutable with content hashes. A checkpoint pins world and economic revisions, random counters, and source references so the run can resume or fork without losing its audit trail.

Replay makes no model calls. It uses recorded decisions, service receipts, events, and pinned versions. A new live-model run gets a new run ID. Compare separate world and economic hashes; exclude camera position, cosmetic animation, and frame rate.

## Deferred: browser performance and device support

This work is not an active roadmap gate while effort is focused on Council, organization, stakeholder-evidence, and persistent-simulation behavior. Retain the notes below for a later release decision.

The 3D client can become GPU-bound from drawing resolution, shadows, geometry, and overdraw, or CPU-bound from many separate scene objects, labels, and per-frame UI updates. The local prototype's Three.js scene chunk is about 569 kB minified (143 kB gzip); this is a download-size warning, not evidence of slow rendering or acceptable device performance. Profile startup/download cost separately from steady-state frame time and memory.

Load detailed geometry only for the active area and use simplified citywide context. For repeated buildings, trees, or pedestrians, profile draw calls and use instancing or merged static geometry where individual movement is unnecessary. Use distance-based detail and frustum culling, limit shadows and pixel ratio on constrained devices, and avoid continuously rendering a static paused scene. The Three.js manuals describe [on-demand rendering](https://threejs.org/manual/pages/rendering-on-demand.html), [optimizing many objects](https://threejs.org/manual/pages/optimize-lots-of-objects.html), and [capping drawing-buffer resolution](https://threejs.org/manual/pages/responsive.html). These are options to validate against this scene, not optimizations already completed.

Before choosing a supported browser/device matrix, measure scene load time, p50/p95 frame time during camera motion and agent movement, peak memory, context-loss recovery, and behavior after a background-tab pause. Test on the lowest-powered intended device, including integrated graphics or mobile hardware if those are in scope. A candidate acceptance target is a stable 30 frames per second during ordinary interaction on the lowest-supported device, but no target is approved until that device and scene scale are specified. Preserve an accessible list/table fallback when WebGL is unavailable.

## Safety, failure, and acceptance

| Failure | Required behavior |
| --- | --- |
| Stale revision or invalid API command | Reject without partial state change |
| Economic invariant failure | Stop the run and mark affected results invalid |
| Model timeout, refusal, invalid intent, or budget exhaustion | Record the reason and use the configured rule fallback |
| Browser disconnect, background-tab pause, or event-sequence gap | Keep server simulation authoritative; recover from a current snapshot and continue from its sequence |
| Runtime or service restart | Preserve committed state and resume from a compatible checkpoint |
| Partial export or unsupported replay version | Reject downstream use with an actionable diagnostic |

## First end-to-end proof for the active scope

Build the smallest proposal-to-outcome slice before expanding the model:

1. Submit and preserve one proposal revision, then produce its impact and actor map with source and unknown labels.
2. Save actual consultation evidence separately from synthetic households and model recommendations.
3. Create one typed plan with bounded organization/resource decisions and an explicit human review decision.
4. Run matched baseline and intervention branches across the proposal's rollout and repeated operating schedule.
5. Persist, resume, and replay the run; compare authoritative state and event hashes.
6. Report household, organization, and public outcomes with denominators, assumptions, sensitivity cases, and evidence limits.

If this proof cannot preserve evidence lineage, resource accounting, and replay, fix those boundaries before adding organization types or broader policy coverage.

Three.js is distributed as browser JavaScript and its official guide recommends npm with a build tool such as Vite for most projects: [Three.js installation](https://threejs.org/manual/pages/installation.html).
