# Scope revision review

## Product direction

The October 17 clarification makes Toronto's 3D environment the first product milestone, with embodied pedestrian agents, a separate planner for staged rollouts of three solutions, and economic plus labeled modeled-response outcomes. The school meal idea is a rollout scenario inside the Toronto world. It does not set the world, schedule, or time horizon.

The working solution mapping from the existing project documents is municipal groceries, food rescue and processing, and expanded school meals. Drone delivery is classified as an optional logistics enabler. The unlimited-lunch service definition and exact solution boundaries remain open.

## Why the school-day phrase appeared

The school-day language comes from the existing `sim.integration` prototype. Its run label says “one synthetic school day; produce component only.” `sim/integration/__main__.py` sets the observation window to one synthetic school day; `sim/integration/scenario.py` uses fixed meal, shopping, and consumption times; and `sim/integration/export.py` repeats the limit in run metadata. The earlier planning documents then used that fixture as their first demonstration. Those facts explain the wording, but they do not support making a school day the product's central simulation. The trace is documented in [integration status](../docs/integration.md#why-the-prototype-says-school-day).

## Architecture direction

Two architecture candidates were compared: Python as world authority with browser Three.js, and Godot as the world/movement runtime with Python retaining economic authority. The clarified priority favors the latter because resident movement and a navigable 3D Toronto world are core behavior. The design review's recommendation is recorded in [the architecture decision](../docs/architecture-decision.md).

Godot 4 .NET/C# is the lead runtime, not an irreversible selection. The visible and headless vertical slice must prove synchronized world time, pedestrian movement, Python economic receipts, and replay. Browser delivery remains open. The current repository still implements only the Python economic prototype.

## Document and planning changes

- Put Toronto 3D and pedestrian agents first in README.md, PLAN.md, and NEXT_STEPS.md.
- Replaced the Python-world/Three.js architecture as the default proposal with Godot world ownership and Python economic ownership.
- Promoted Toronto massing, streets, coordinate systems, and pedestrian links to the first data gate.
- Reframed studies around geographic validation, pedestrian movement, staged planning, and economic outcomes.
- Replaced the old 16-week food-policy estimate and illustrative CAD 252,480 budget with dependency-based gates and no schedule or budget claim.
- Updated the planning catalog and checker so the old four-switch screen, household LLM limits, and budget are explicitly marked superseded or removed from current plan checks.
- Kept the current school-day integration code documented as a legacy economic fixture.

## Verification boundary

The planning-package checker is run after these revisions and recorded in [verification output](verification.txt). It checks document links and consistency, evidence metadata, source IDs, solution coverage, product-scope fields, and decision pointers. It does not verify a running Godot project, a Toronto data ingestion, pedestrian behavior, planner quality, performance, calibration, or real policy outcomes.

Simulator tests were not run for this documentation scope revision.
