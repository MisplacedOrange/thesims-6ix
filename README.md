# The Sims 6ix

A browser 3D environment for exploring downtown Toronto and watching synthetic pedestrians move through its streets.

## Active deliverable

The current milestone is the visual environment and pedestrian agents. Public solutions, infrastructure planning, and economic outcomes are deferred.

The application in [apps/web](apps/web/) loads a frozen, attributed OpenStreetMap snapshot of downtown Toronto. It includes building massing, stylized CN Tower and Rogers Centre models, parks, streets, the waterfront, moving pedestrians, resident inspection, camera compositions, lighting, layers, and playback controls. It runs independently of the Python economic fixture.

Use Node.js 24 or newer:

    cd apps/web
    npm install
    npm run dev

Open the Local URL printed by Vite. See the [environment guide](apps/web/README.md) for controls, tests, data licensing, and limitations.

## Legacy economic fixture

This repository contains a headless Python research prototype. It runs one synthetic school day for up to 250 households and models one produce component. The run includes school meals, municipal groceries, food rescue and processing, procurement, and ground or hypothetical drone delivery.

The Python fixture remains separate from the browser environment. It has no infrastructure rollout planner, API, durable run database, or live LLM connection. The existing school-day run is an economic integration fixture. [Here is why the current fixture says school day](docs/integration.md#why-the-prototype-says-school-day).

## Deferred research direction

The 3D Toronto environment is the primary experience. Residents move through a geospatial city model as pedestrian agents. A separate infrastructure planner proposes sourced, staged rollouts for three public solutions. The simulation validates each stage and records economic outcomes and clearly labeled modeled human responses.

The existing documents point to three Toronto solutions: municipal groceries, food rescue and processing, and expanded school meals. The school proposal may include unlimited lunches, but its service rules need definition. Meituan-style drones remain a delivery scenario rather than a fourth policy solution unless the team decides otherwise.

## Technology

TypeScript, React, Three.js, and Vite implement the current environment. A pure pedestrian module generates seeded itineraries on the connected map and samples them at simulation time. The browser owns this visual timeline. There is no service or provider dependency. The Python-authoritative service and storage architecture in the earlier [architecture decision](docs/architecture-decision.md) remains a future proposal.

Read [the revised product plan](PLAN.md) first. The [next steps](NEXT_STEPS.md) prioritize the Toronto world and pedestrian agents. The specifications cover the world and state ownership in [architecture](docs/architecture.md), agent and outcome semantics in [simulation](docs/simulation.md), Toronto inputs in [the data plan](docs/data-plan.md), and study design in [experiments and validation](docs/experiments-and-validation.md).

The research documents describe a broader future product. The active scope above governs current implementation.

## Run the current prototype

Install Python 3.10 or newer and the optional test dependencies:

    python -m pip install -e ".[test]"

Run the existing paired grocery comparison:

    python -m sim.integration paired --households 250 --seeds 17 18 --policies groceries --out outputs/grocery-pair

The output directory must be new. Completed runs contain hashed inputs, economic events, terminal state, decisions, household results, logistics, and journey references. This command runs the existing food-policy prototype, not the planned Toronto 3D environment.

## Project documents

| Document | Purpose |
| --- | --- |
| [Environment guide](apps/web/README.md) | Run and explore the current visual environment |
| [Environment implementation](docs/environment-implementation.md) | Current scope, design choice, and acceptance criteria |
| [Product plan](PLAN.md) | Product goal, three solutions, pedestrian agents, and rollout planner |
| [Next steps](NEXT_STEPS.md) | Toronto 3D-first implementation sequence |
| [System architecture](docs/architecture.md) | World ownership, agent decisions, planner, and economic state |
| [Economic and agent model](docs/simulation.md) | Pedestrians, households, interventions, and modeled response |
| [Policies and evidence](docs/policies-and-evidence.md) | Existing Toronto policy evidence and limitations |
| [Data plan](docs/data-plan.md) | Toronto geometry, population, services, and provenance |
| [Experiments and validation](docs/experiments-and-validation.md) | Agent, rollout, economic, and response evaluation |
| [Delivery plan](docs/delivery.md) | Proposed milestones and acceptance gates |
| [Architecture decision](docs/architecture-decision.md) | Browser client proposal, state ownership, and open deployment choices |
| [Integration status](docs/integration.md) | What the current Python prototype implements |
| [Scenario catalog](planning/scenarios.json) | Three solution IDs, delivery enablers, and legacy fixture aliases |
| [Source register](planning/sources.json) | Primary sources and supported claims |
| [Decision trail](planning/decisions.tsv) | Planning decisions and their evidence |

The planning-package checker validates documents and planning manifests:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-plan.ps1

The simulator tests are a separate check. Current implementation limits and future acceptance gates are listed in the [integration status](docs/integration.md).
