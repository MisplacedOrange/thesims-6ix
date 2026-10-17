# The Sims 6ix

A Toronto 3D pedestrian simulation for exploring public food solutions, infrastructure rollouts, and their economic and human effects.

## Current state

This repository contains a headless Python research prototype. It runs one synthetic school day for up to 250 households and models one produce component. The run includes school meals, municipal groceries, food rescue and processing, procurement, and ground or hypothetical drone delivery.

The Python simulator has no Toronto 3D scene, autonomous pedestrian population, infrastructure rollout planner, API, durable run database, or live LLM connection. A separate browser demonstration in apps/web renders a synthetic scene and playback but is not connected to the simulator. The existing school-day run is an economic integration fixture. It is not the product's main environment or time horizon. [Here is why the current fixture says school day](docs/integration.md#why-the-prototype-says-school-day).

## Target product

The 3D Toronto environment is the primary experience. Residents move through a geospatial city model as pedestrian agents. A separate infrastructure planner proposes sourced, staged rollouts for three public solutions. The simulation validates each stage and records economic outcomes and clearly labeled modeled human responses.

The existing documents point to three Toronto solutions: municipal groceries, food rescue and processing, and expanded school meals. The school proposal may include unlimited lunches, but its service rules need definition. Meituan-style drones remain a delivery scenario rather than a fourth policy solution unless the team decides otherwise.

## Proposed technology

Browser delivery is a product requirement. A local frontend prototype exists in [apps/web](apps/web/): TypeScript, React, Three.js, and Vite display and replay one fixed synthetic recording. It has no live simulation connection. The simulator itself remains a headless Python economic prototype. The proposed production design keeps world simulation, pedestrian state, and economic settlement authoritative in Python, with a versioned API to the browser; FastAPI with HTTP commands and WebSocket event updates is a candidate. SQLite and immutable, content-hashed files are proposed for local run storage. The deployment topology and target browser/device range still need decisions. See the [architecture decision](docs/architecture-decision.md).

Read [the revised product plan](PLAN.md) first. The [next steps](NEXT_STEPS.md) prioritize the Toronto world and pedestrian agents. The specifications cover the world and state ownership in [architecture](docs/architecture.md), agent and outcome semantics in [simulation](docs/simulation.md), Toronto inputs in [the data plan](docs/data-plan.md), and study design in [experiments and validation](docs/experiments-and-validation.md).

## Run the current prototype

Install Python 3.10 or newer and the optional test dependencies:

    python -m pip install -e ".[test]"

Run the existing paired grocery comparison:

    python -m sim.integration paired --households 250 --seeds 17 18 --policies groceries --out outputs/grocery-pair

The output directory must be new. Completed runs contain hashed inputs, economic events, terminal state, decisions, household results, logistics, and journey references. This command runs the existing food-policy prototype, not the planned Toronto 3D environment.

## Project documents

| Document | Purpose |
| --- | --- |
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
