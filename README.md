# The Sims 6ix

A browser 3D environment for exploring downtown Toronto and watching synthetic pedestrians move through its streets.

## Current implementation

The browser application in [apps/web](apps/web/) loads a frozen, attributed OpenStreetMap snapshot of downtown Toronto and replays a Python-settled six-hour food-access scenario. The local Council API stores exact Markdown revisions, scope, plan, reviewer decisions, and a paired run for one hypothetical municipal food site. In the current working tree, the browser panel exposes proposal intake and revision inspection; scope, plan, decision, and run controls remain unfinished in the UI. Operating values are illustrative assumptions. The active roadmap focuses on completing this Council flow, adding bounded organization decisions and actual stakeholder evidence, and extending the authoritative simulation across operating days. See the [implemented interaction contract](sim/interactables/README.md) and [active roadmap](NEXT_STEPS.md).

Use Node.js 24 or newer and Python 3.10 or newer. From the repository root, start the browser and its local Council service together:

    cd apps/web
    npm install
    npm run dev

The development command serves Vite and starts the Council API bound only to `127.0.0.1:8765`; Ctrl+C stops both. Static production hosting includes the cached preset traces but does not provide the Council API. Open the Local URL printed by Vite. See the [environment guide](apps/web/README.md) for controls, tests, data licensing, and limitations.

## Legacy economic fixture

This repository contains a headless Python research prototype. It runs one synthetic school day for up to 250 households and models one produce component. The run includes school meals, municipal groceries, food rescue and processing, procurement, and ground or hypothetical drone delivery.

The older `sim.integration` school-day fixture remains separate from the browser food-access scenario. It has no API, durable run database, or live LLM connection. [Here is why that legacy fixture says school day](docs/integration.md#why-the-prototype-says-school-day).

## Active scope

The current priorities are: complete the human-reviewed Council proposal flow; model bounded economic decisions by relevant organizations; record actual stakeholder input separately from synthetic household behavior; and build a persistent simulation with pinned, traceable evidence. The existing site action is a starting point for an integrated proof. Broader policy catalogs and other model features are deferred unless the selected proposal requires them. No simulated decision authorizes real City action.

See [the focused product plan](PLAN.md), [the active roadmap](NEXT_STEPS.md), and the [agent planner plan](docs/agent-planner-plan.md) for scope, authority boundaries, and acceptance gates.

## Technology

TypeScript, React, Three.js, and Vite implement the browser. Python generates bounded deterministic food-access runs through the existing economic kernel and owns the local Council records and paired traces; the browser displays committed projections. The active architecture extends this path with proposal-specific organization decisions, separate stakeholder evidence, and persistent runs. See the [system architecture](docs/architecture.md).

Read [the focused product plan](PLAN.md) and [active roadmap](NEXT_STEPS.md) first. Supporting specifications cover state ownership and persistence in [architecture](docs/architecture.md), organization and stakeholder semantics in [simulation](docs/simulation.md) and [pedestrian interactables](docs/pedestrian-interactables-plan.md), Toronto inputs in [the data plan](docs/data-plan.md), and evaluation boundaries in [experiments and validation](docs/experiments-and-validation.md). Those subsystem documents retain implementation details; the active roadmap controls current commitments.

The product scope describes the intended system. The status of each implemented component is recorded separately in the implementation and integration documents.

## Run the current prototype

Install Python 3.10 or newer and the optional test dependencies:

    python -m pip install -e ".[test]"

Run the existing paired grocery comparison:

    python -m sim.integration paired --households 250 --seeds 17 18 --policies groceries --out outputs/grocery-pair

The output directory must be new. Completed runs contain hashed inputs, economic events, terminal state, decisions, household results, logistics, and journey references. This command runs the separate legacy `sim.integration` fixture, not the browser-replayed six-hour food-access scenario or an ongoing Toronto simulation.

## Project documents

| Document | Purpose |
| --- | --- |
| [Environment guide](apps/web/README.md) | Run and explore the current visual environment |
| [Product plan](PLAN.md) | Council chat, open proposal intake, pedestrian and department agents, ongoing rollout, and outcomes |
| [Next steps and delivery plan](NEXT_STEPS.md) | Staged roadmap with implementation status, delivery gates, and acceptance criteria |
| [System architecture](docs/architecture.md) | Browser client, Python authority, proposal intake, state ownership, rollout, replay, and open deployment choices |
| [Economic and agent model](docs/simulation.md) | Pedestrians, households, interventions, and modeled response |
| [Pedestrian food interactables](docs/pedestrian-interactables-plan.md) | Food flows, household spending, site economics, access, and outcome measures |
| [Implemented food-access scenario](sim/interactables/README.md) | Six-hour runner, committed events, dashboard metrics, and evidence limits |
| [Agent planner and rollout plan](docs/agent-planner-plan.md) | Proposal evidence, planner authority, supported actions, staged rollout, review, and evaluation |
| [Policies and evidence](docs/policies-and-evidence.md) | Existing Toronto policy evidence and limitations |
| [Data plan](docs/data-plan.md) | Toronto geometry, population, services, and provenance |
| [Experiments and validation](docs/experiments-and-validation.md) | Agent, rollout, economic, and response evaluation |
| [Integration status](docs/integration.md) | What the current Python prototype implements |
| [Scenario catalog](planning/scenarios.json) | Initial demonstration fixtures and legacy economic aliases; not a closed proposal catalog |
| [Source register](planning/sources.json) | Primary sources and supported claims |
| [Decision trail](planning/decisions.tsv) | Planning decisions and their evidence |

The planning-package checker validates documents and planning manifests:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-plan.ps1

The simulator tests are a separate check. Current implementation limits and future acceptance gates are listed in the [integration status](docs/integration.md).
