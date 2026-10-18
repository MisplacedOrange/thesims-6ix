# The Sims 6ix

A browser 3D environment for exploring downtown Toronto and watching synthetic pedestrians move through its streets.

## Current implementation

The browser application in [apps/web](apps/web/) loads a frozen, attributed OpenStreetMap snapshot of downtown Toronto with building massing, landmarks, parks, streets, and household pedestrians. It replays a Python-settled food-access day with home pantries, retail purchases, food support, school nutrition, supplier deliveries, and an optional emergency food site. A local Council workflow also accepts exact Markdown revisions, records explicit scope, plan and reviewer decisions, and runs one hypothetical municipal food site against a same-seed baseline. Operating values are illustrative assumptions. The bounded local feature does not create an ongoing city simulation or grant real City authority. See the [implemented interaction contract](sim/interactables/README.md) and [planner plan](docs/agent-planner-plan.md).

Use Node.js 24 or newer and Python 3.10 or newer. From the repository root, start the browser and its local Council service together:

    cd apps/web
    npm install
    npm run dev

The development command serves Vite and starts the Council API bound only to `127.0.0.1:8765`; Ctrl+C stops both. Static production hosting includes the cached preset traces but does not provide the Council API. Open the Local URL printed by Vite. See the [environment guide](apps/web/README.md) for controls, tests, data licensing, and limitations.

## Legacy economic fixture

This repository contains a headless Python research prototype. It runs one synthetic school day for up to 250 households and models one produce component. The run includes school meals, municipal groceries, food rescue and processing, procurement, and ground or hypothetical drone delivery.

The older `sim.integration` school-day fixture remains separate from the browser food-access scenario. It has no API, durable run database, or live LLM connection. [Here is why that legacy fixture says school day](docs/integration.md#why-the-prototype-says-school-day).

## Product scope

The target product is an ongoing Toronto simulation with a side-panel Council workflow. The current bounded implementation preserves Markdown and source spans, keeps unknown content visible, and asks the reviewer to choose one supported action and labeled parameters. It does not interpret proposals through a conversational model or refresh external evidence. A recorded simulated decision applies only to a six-hour scenario; it does not authorize real City action.

See the [agent planner plan](docs/agent-planner-plan.md) for the planner's roles, authority boundaries, work packages, and rollout behavior.

The initial demo proposals are city-operated affordable grocery stores, rescue and processing of surplus food, and expanded school meals with shared food purchasing. They are example inputs, not a closed list of supported proposals. New Markdown proposals should use the same intake and validation flow without requiring a new hard-coded policy ID.

## Technology

TypeScript, React, Three.js, and Vite implement the browser. Python generates bounded deterministic food-access runs through the existing economic kernel and owns the local Council records and paired traces; the browser displays committed projections. The target architecture adds a persistent Python world service, general action catalog, and broader evidence and agent workflows. See the [system architecture](docs/architecture.md).

Read [the product plan](PLAN.md) first. The [next steps](NEXT_STEPS.md) separate the bounded Council proof from the future ongoing simulation. The specifications cover world and state ownership in [architecture](docs/architecture.md), agent and outcome semantics in [simulation](docs/simulation.md), Toronto inputs in [the data plan](docs/data-plan.md), and study design in [experiments and validation](docs/experiments-and-validation.md).

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
