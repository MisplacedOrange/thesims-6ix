# The Sims 6ix

A browser 3D environment for exploring downtown Toronto and watching synthetic pedestrians move through its streets.

## Current implementation

The browser application in [apps/web](apps/web/) loads a frozen, attributed OpenStreetMap snapshot of downtown Toronto with building massing, landmarks, parks, streets, and household pedestrians. It now replays a Python-settled food-access day with home pantries, retail purchases, food support, school nutrition, crossing waits, supplier deliveries, and an optional emergency food site. Inspect residents and food-site markers, seek through the day, compare scenarios, and review or download event-based outcomes. Operating values are illustrative assumptions. See the [implemented interaction contract](sim/interactables/README.md). Proposal chat, uploaded-proposal intake, department agents, and an ongoing policy service remain planned.

Use Node.js 24 or newer and Python 3.10 or newer. Startup generates cached simulation traces:

    cd apps/web
    npm install
    npm run dev

Open the Local URL printed by Vite. See the [environment guide](apps/web/README.md) for controls, tests, data licensing, and limitations.

## Legacy economic fixture

This repository contains a headless Python research prototype. It runs one synthetic school day for up to 250 households and models one produce component. The run includes school meals, municipal groceries, food rescue and processing, procurement, and ground or hypothetical drone delivery.

The older `sim.integration` school-day fixture remains separate from the browser food-access scenario. It has no infrastructure rollout planner, API, durable run database, or live LLM connection. [Here is why that legacy fixture says school day](docs/integration.md#why-the-prototype-says-school-day).

## Product scope

The target product is an ongoing Toronto simulation with a side-panel chat for a simulated City Council session. A user can upload a Markdown proposal, discuss or amend its interpretation, and review a structured, sourced version with its goals, outcome measures, constraints, unknowns, and assumptions. A recorded simulated Council decision creates or updates a versioned policy; it does not authorize real City action.

Expert agents represent relevant municipal departments and delivery partners, such as public health, planning and construction, finance and procurement, food operators, and logistics. They coordinate work packages and stage changes in the simulated world. Python remains authoritative for time, budgets, physical capacities, economic transactions, and whether a stage can become active. The simulation continues over time as infrastructure is planned, delayed, reduced, opened, or operated. Proposal facts and metrics remain traceable to their sources and are tracked through the run.

The initial demo proposals are city-operated affordable grocery stores, rescue and processing of surplus food, and expanded school meals with shared food purchasing. They are example inputs, not a closed list of supported proposals. New Markdown proposals should use the same intake and validation flow without requiring a new hard-coded policy ID.

## Technology

TypeScript, React, Three.js, and Vite implement the browser. Python generates bounded deterministic food-access runs through the existing economic kernel; the browser samples routes and committed state at playback time. The target architecture adds proposal/chat and a Python-authoritative ongoing simulation service. See the [architecture decision](docs/architecture-decision.md).

Read [the product plan](PLAN.md) first. The [next steps](NEXT_STEPS.md) describe the staged path from the current visual foundation to proposal intake and ongoing simulation. The specifications cover world and state ownership in [architecture](docs/architecture.md), agent and outcome semantics in [simulation](docs/simulation.md), Toronto inputs in [the data plan](docs/data-plan.md), and study design in [experiments and validation](docs/experiments-and-validation.md).

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
| [Environment implementation](docs/environment-implementation.md) | Current scope, design choice, and acceptance criteria |
| [Product plan](PLAN.md) | Council chat, open proposal intake, pedestrian and department agents, ongoing rollout, and outcomes |
| [Next steps](NEXT_STEPS.md) | Staged path from the visual foundation to proposal intake and ongoing simulation |
| [System architecture](docs/architecture.md) | Proposal intake, world ownership, agent decisions, rollout, and persistent state |
| [Economic and agent model](docs/simulation.md) | Pedestrians, households, interventions, and modeled response |
| [Pedestrian food interactables](docs/pedestrian-interactables-plan.md) | Food flows, household spending, site economics, access, and outcome measures |
| [Implemented food-access scenario](sim/interactables/README.md) | Six-hour runner, committed events, dashboard metrics, and evidence limits |
| [Agent planner and rollout plan](docs/agent-planner-rollout-interface-plan.md) | Planner interface, human review, and time-based infrastructure stages |
| [Policies and evidence](docs/policies-and-evidence.md) | Existing Toronto policy evidence and limitations |
| [Data plan](docs/data-plan.md) | Toronto geometry, population, services, and provenance |
| [Experiments and validation](docs/experiments-and-validation.md) | Agent, rollout, economic, and response evaluation |
| [Delivery plan](docs/delivery.md) | Proposed milestones and acceptance gates |
| [Architecture decision](docs/architecture-decision.md) | Browser client proposal, state ownership, and open deployment choices |
| [Integration status](docs/integration.md) | What the current Python prototype implements |
| [Scenario catalog](planning/scenarios.json) | Initial demonstration fixtures and legacy economic aliases; not a closed proposal catalog |
| [Source register](planning/sources.json) | Primary sources and supported claims |
| [Decision trail](planning/decisions.tsv) | Planning decisions and their evidence |

The planning-package checker validates documents and planning manifests:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-plan.ps1

The simulator tests are a separate check. Current implementation limits and future acceptance gates are listed in the [integration status](docs/integration.md).
