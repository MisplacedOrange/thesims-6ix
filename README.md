# The Sims 6ix

A Toronto food-policy simulator where a 3D neighbourhood makes household choices, food flows, and public costs visible.

This repository contains the system plan and a runnable, connected Python research prototype assembled from PRs #1 through #4. The planning cutoff is October 17, 2026. The requested drone scenario is Meituan-style food delivery.

The implemented comparison covers one synthetic school day, 250 unweighted household records, and one produce component. School provision, procurement, rescue processing, municipal-store funding, household choices, and ground/drone logistics share one kernel. Inputs and feelings remain illustrative. This is not a calibrated model of current Toronto or a complete Sims-like game.

Install and check the simulator with Python 3.10 or newer:

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
python -m sim.integration paired --households 250 --seeds 17 18 --policies groceries --out outputs/grocery-pair
```

The output directory must be new. Completed runs contain hashed inputs, economic events, terminal state, decisions, household results, logistics, and presentation references. See [integration and current limitations](docs/integration.md) for selection decisions, commands, interpretation, and remaining work.

Start with [the product and build plan](PLAN.md), then read the specifications relevant to your work.

| Document | Purpose |
| --- | --- |
| [Next steps](NEXT_STEPS.md) | Immediate 3D milestone, backend ownership, data acquisition, model expansion, and live LLM integration |
| [System architecture](docs/architecture.md) | Authority, modules, interfaces, event flow, persistence, and 3D synchronization |
| [Economic and agent model](docs/simulation.md) | Food, money, households, behavior, LLM decisions, and modeled feelings |
| [Policies and evidence](docs/policies-and-evidence.md) | Verified Toronto status, baseline economic context, and policy timing |
| [Data plan](docs/data-plan.md) | Datasets, provenance, synthetic population, ingestion, and missing measurements |
| [Experiments and validation](docs/experiments-and-validation.md) | Counterfactuals, uncertainty, acceptance gates, and real-world evaluation |
| [Delivery and costs](docs/delivery.md) | Milestones, backlog, staffing, proposed budgets, and first tasks |
| [Architecture decision](docs/architecture-decision.md) | Orange-skills candidate comparison, chosen base, and tradeoffs |
| [Integration status](docs/integration.md) | Selected PR components, current contracts, validation, and revision priorities |
| [Source register](planning/sources.json) | Primary URLs and the claims they support |
| [Scenario catalog](planning/scenarios.json) | Machine-readable planning scenarios and LLM limits |
| [Decision trail](planning/decisions.tsv) | Evidence behind the planning decisions |

Run the planning-package checks from this folder in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-plan.ps1
```

This checks documents and planning manifests. The simulator tests run separately with pytest. Remaining simulation and research gates are recorded in the integration status document.
