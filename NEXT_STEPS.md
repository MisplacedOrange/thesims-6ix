# Next steps for The Sims 6ix

Updated October 17, 2026. The implemented work includes the browser-based Toronto visual foundation and a bounded six-hour food-access scenario replayed from Python-generated traces. The product target is a Council-style proposal workflow connected to an ongoing simulation; the chat, proposal intake, department agents, persistent world service, and staged policy rollout are not implemented yet.

## Implemented browser and food-access environment

The browser application in apps/web displays a sourced downtown Toronto snapshot with building massing, street geometry, shoreline, parks, railways, and stylized landmark models. Seeded pedestrians walk connected outdoor routes, rest at destinations, and repeat their journeys. It also replays a bounded six-hour food-access scenario with Python-generated routes, rule-based choices, kernel-settled transactions, service events, and food/economic measures.

Camera presets, orbit and zoom, resident inspection and follow, population density, daylight settings, layer controls, pause, speed, and reset are implemented. The app needs no live Python service or model API; development scripts use Python to regenerate cached traces. The environment guide records source attribution and approximation limits.

## Product direction and next steps

The target experience has a side-panel Council chat that accepts Markdown proposals. It preserves source material and turns each proposal into a reviewable, versioned record of requested changes, outcome measures, constraints, assumptions, and unknowns. Simulated expert roles for relevant departments and delivery partners coordinate feasible work packages. The user reviews the proposal and plan; only validated and approved stages can change the simulated city.

The simulation continues across planning, procurement, readiness or construction, operation, delay, reduction, and cancellation. It records proposal-specific measures and standard city outcomes over time, with source and assumption traceability. This does not authorize real City spending, permits, or construction.

Move toward that target in dependency order:

1. Validate the Toronto map, route network, visual controls, and bounded food-access outputs; record data coverage and device limits.
2. Define a reusable proposal schema and Markdown intake that preserves evidence, captures outcomes and unknowns, and supports clarification and version history.
3. Add a persistent, deterministic Python world service and run archive so the simulation can advance, pause, checkpoint, resume, and replay.
4. Add simulated department roles, a coordinated planner, deterministic feasibility checks, review/approval records, and staged activation.
5. Track proposal-defined measures alongside standard outcomes through ongoing runs; compare baseline, rollout, delay, reduced-capacity, and no-launch cases.
6. Load the three food-policy examples through the same open intake path, then demonstrate that a new proposal does not need a hard-coded policy ID.

Keep rules and simple baselines ahead of model complexity. Add small or LLM decisions only after the relevant observations, legal actions, replay, fallback, and cost controls are defined.

## Visual foundation work

Continue route review around crossings, waterfront paths, and the railway corridor. Profile scene load, frame time, and memory on the lowest-powered intended device. Improve landmark or Toronto massing detail only where it adds value, and expand the detailed active area after navigation and performance are satisfactory.

No revised production schedule, budget, hosting topology, or device performance target is approved.
