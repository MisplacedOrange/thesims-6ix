# The Sims 6ix

A Toronto food-policy simulator where a 3D neighbourhood makes household choices, food flows, and public costs visible.

This repository currently contains an in-depth system plan. It does not yet contain a running simulator. The planning cutoff is October 17, 2026. The requested drone scenario is Meituan-style food delivery.

Start with [the product and build plan](PLAN.md), then read the specifications relevant to your work.

| Document | Purpose |
| --- | --- |
| [System architecture](docs/architecture.md) | Authority, modules, interfaces, event flow, persistence, and 3D synchronization |
| [Economic and agent model](docs/simulation.md) | Food, money, households, behavior, LLM decisions, and modeled feelings |
| [Policies and evidence](docs/policies-and-evidence.md) | Verified Toronto status, baseline economic context, and policy timing |
| [Data plan](docs/data-plan.md) | Datasets, provenance, synthetic population, ingestion, and missing measurements |
| [Experiments and validation](docs/experiments-and-validation.md) | Counterfactuals, uncertainty, acceptance gates, and real-world evaluation |
| [Delivery and costs](docs/delivery.md) | Milestones, backlog, staffing, proposed budgets, and first tasks |
| [Architecture decision](docs/architecture-decision.md) | Orange-skills candidate comparison, chosen base, and tradeoffs |
| [Source register](planning/sources.json) | Primary URLs and the claims they support |
| [Scenario catalog](planning/scenarios.json) | Machine-readable planning scenarios and LLM limits |
| [Decision trail](planning/decisions.tsv) | Evidence behind the planning decisions |

Run the planning-package checks from this folder in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-plan.ps1
```

This checks the delivered documents and planning manifests. Simulation acceptance tests are specified in the validation document and remain implementation work.
