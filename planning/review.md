# Scope revision review

## Product direction

The current target is a Toronto simulation with a side-panel Council chat that accepts Markdown proposals. The user can deliberate, clarify, amend, and record a decision on a proposal; its source material, requested changes, outcome measures, constraints, assumptions, unknowns, and versions remain reviewable. Simulated expert roles representing relevant departments and delivery partners coordinate staged work. A deterministic simulation controls funding, capacity, and activation, while the world continues running and tracking proposal measures over time. This does not authorize real City action.

The grocery, food rescue/processing, and school-food statements are initial demonstration inputs, not a closed set of supported interventions. New Markdown proposals should use the same intake and review path without requiring a hard-coded solution ID. The fixed entries in `planning/scenarios.json` remain study fixtures for the current food examples, not an intake allowlist. Proposal-specific service definitions and measures remain open where the source material does not specify them.

The October 17 scope and architecture reviews below are historical context. The open proposal intake and Council-chat workflow supersede their fixed three-solution framing.

## Why the school-day phrase appeared

The school-day language comes from the existing `sim.integration` prototype. Its run label says “one synthetic school day; produce component only.” `sim/integration/__main__.py` sets the observation window to one synthetic school day; `sim/integration/scenario.py` uses fixed meal, shopping, and consumption times; and `sim/integration/export.py` repeats the limit in run metadata. The earlier planning documents then used that fixture as their first demonstration. Those facts explain the wording, but they do not support making a school day the product's central simulation. The trace is documented in [integration status](../docs/integration.md#why-the-prototype-says-school-day).

## Architecture direction

The earlier scope review favored a separate world/movement runtime with Python retaining economic authority. Browser delivery is now a product requirement, and the current proposed direction is a TypeScript/React/Three.js client with Python as the sole world and economic authority. The frontend prototype in apps/web uses a frozen Toronto map, seeded pedestrian itineraries, and bounded six-hour food-access trace playback; it is not connected to an ongoing simulation service. The updated recommendation and its tradeoffs are recorded in [system architecture](../docs/architecture.md).

The Python world clock, pedestrian movement, versioned API, durable run archive, and target-device performance are still unimplemented. The first vertical slice must prove authoritative replay and profile the browser projection on the lowest-supported device.

## Document and planning changes

- Put Toronto 3D and pedestrian agents first in README.md, PLAN.md, and NEXT_STEPS.md.
- The previous revision proposed separate world and economic ownership; the browser requirement now supersedes that change.
- Promoted Toronto massing, streets, coordinate systems, and pedestrian links to the first data gate.
- Reframed studies around geographic validation, pedestrian movement, staged planning, and economic outcomes.
- Updated the planning catalog and checker so the old four-switch screen and household LLM limits are explicitly marked superseded or removed from current plan checks.
- Kept the current school-day integration code documented as a legacy economic fixture.

## Verification boundary

The planning-package checker was run for the earlier scope revision and is recorded in [verification output](verification.txt). It checks document links and consistency, evidence metadata, source IDs, solution coverage, product-scope fields, and decision pointers. It does not validate browser rendering, attribution or coverage of the frozen Toronto map, City GIS acquisition outputs, pedestrian behavior, planner quality, performance, calibration, or real policy outcomes.

Simulator tests were not run for this documentation scope revision.
