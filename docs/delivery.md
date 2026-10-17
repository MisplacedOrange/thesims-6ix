# Delivery plan

## Current planning status

This roadmap sequences work by evidence and dependencies. It does not set a delivery date, staffing commitment, or approved budget. The earlier 16-week food-policy prototype and its illustrative CAD 252,480 envelope are superseded; they did not estimate a Toronto-first 3D simulation.

The proposed stack is Godot 4 .NET/C# for the world and movement runtime, with the existing Python economic kernel and a versioned local bridge. The engine remains a lead candidate until the visible and headless vertical slice proves that movement, economic receipts, and replay agree. See [system architecture](architecture.md).

## Delivery gates

| Gate | Work | Observable result |
| --- | --- | --- |
| 1. Toronto world slice | Audit licenses and vintages, freeze massing and street inputs, confirm coordinate transform, render city context and one active area | A selected building, street, and destination resolve to stable source features; unsupported geometry is labeled |
| 2. Pedestrian slice | Add a walkable graph, a small synthetic population, schedules, mobility constraints, deterministic movement, and rule choices | One resident follows a feasible Toronto route in visible and headless modes with repeatable positions and choices |
| 3. Economic bridge | Connect one resident trip to an existing household purchase or service transaction; record revisions and receipts | A committed Python receipt drives the visible economic change; duplicate or stale commands cannot settle twice |
| 4. Planner and rollout | Define the three solution IDs, evidence snapshot, stage format, deterministic validator, review record, and activation rules; use the school meal plan as an initial case if its service definition is agreed | A validated school rollout includes candidate infrastructure and prerequisites; rejected or unfunded stages never change the running world |
| 5. Outcomes and evaluation | Compare baseline, staged treatment, and adverse rollout cases; label data and modeled response | Results report economic outcomes, reach, movement, public cost, uncertainty, and modeled response by supported groups |

Each gate should end in an inspectable artifact and a recorded acceptance result before the next depends on it. Numeric performance targets follow measurement of the first active area; do not carry forward targets from the earlier food-economy plan.

## First implementation work

1. Inspect Toronto building massing and Centreline downloads, metadata, coverage, licenses, coordinate systems, and stable identifiers.
2. Select an initial active area based on the availability of routes and destinations, while preserving citywide context in the scene.
3. Build a Godot headless/live test scene and exercise one resident on the same graph.
4. Define the Python bridge envelope: run ID, timestamp, world and economic revisions, idempotency key, intent, receipt, and failure behavior.
5. Connect one receipt from the existing economic kernel and verify visible/headless replay parity.
6. Freeze the source manifest and record what remains synthetic before adding more pedestrians, destinations, or policy detail.

## Scope boundary

The first deliverable establishes Toronto as the primary 3D environment, supports pedestrian agents, and demonstrates one sourced infrastructure rollout plan. It does not claim a complete digital twin, calibrated citywide behavioral model, observed Toronto sentiment, unrestricted LLM autonomy, or real operational authority.

School meals, including the proposed unlimited-lunch option, are one rollout scenario. The exact eligibility, participation, service days, menu, and meaning of “unlimited” remain to be specified. Municipal groceries and food rescue/processing remain the other two solution entries indicated in the current planning documents. Drone delivery remains an optional logistics case, not a core solution ID.

The planner can recommend candidate sites, equipment, staffing, procurement, storage, and delivery stages. A deterministic validator and recorded review control whether a proposed schedule can enter a simulation. Actual project funding, permits, and real-world implementation decisions remain outside the simulator.
