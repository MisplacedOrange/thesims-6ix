# Next steps for The Sims 6ix

Updated October 17, 2026. This roadmap reflects the revised product priority: establish the Toronto 3D world first, then add pedestrian agents, infrastructure rollouts, and outcome tracking. The current Python food-policy prototype remains a source of economic mechanisms and test fixtures.

## Current state

The repository contains a headless Python prototype. It models one synthetic school day, up to 250 unweighted households, and one produce component. It can compare grocery, processing, school, and delivery scenarios through a shared economic kernel.

The repository does not contain the Toronto 3D world, autonomous pedestrian agents, the infrastructure planner, durable live-run storage, a connected UI, or live model transport. Existing household choices use deterministic rules. See the [integration status](docs/integration.md).

## Build order

### 1. Establish Toronto in 3D

Choose an initial geographic snapshot and verify Toronto building massing, street geometry, coordinate systems, licenses, and data vintages. Render a browser scene with citywide context and stable feature IDs. Identify one active area for detailed routes and agents. Keep synthetic or missing data visibly labeled. Decide which desktop browsers and devices the first slice must support.

Complete this step when the scene opens at Toronto scale, the active area aligns with source geography, and a selected building or street can be traced to its source feature.

### 2. Move pedestrian agents

Add a pedestrian network and a small synthetic population in the active area. Give each person a position, destination, schedule, mobility profile, and current activity. Advance movement and rule policies in the Python simulation service; send timestamped positions and events to the browser for rendering. Add a small-model interface and a fixed, bounded LLM panel for selected decisions after legal options and replay records exist.

Complete this step when a resident follows a valid path between two Toronto destinations, and replay produces the same positions and choices from recorded inputs.

### 3. Connect the existing economics

Connect one pedestrian trip to the Python economic kernel. Use one existing purchase or school-service transaction to verify that the browser scene, route, household account, food stock, and event record agree. The person may carry out a household purchase while the household remains the account owner. The browser sends commands and displays server-confirmed events; it does not settle the transaction.

Complete this step when the server commits the economic receipt before the browser displays a purchase or service as complete. Browser rendering and a headless run with the same inputs must produce matching world and economic hashes.

### 4. Plan and stage the school rollout

Give the infrastructure planner the frozen Toronto snapshot, candidate schools, current capacity, evidence sources, budgets, and rollout horizon. Ask it to propose kitchens, cold storage, staffing, procurement, delivery, phases, cost ranges, and capacity ramps for the unlimited-lunch proposal.

Run the proposal through deterministic geography, budget, dependency, source, and capacity checks. Record review and approval before scheduling milestones. Treat delayed, reduced, and no-launch cases as valid outcomes.

Complete this step when a rejected proposal cannot change the world, an accepted schedule can activate a stage only after its prerequisites hold, and each activation has a source and economic event.

### 5. Measure changes

Compare a baseline with each validated rollout using matched populations and assumptions. Report money, food access, service reach, travel, capacity, and public spending by area and population group.

Track modeled perceptions separately from observed survey evidence. Start with a documented proxy such as perceived access or trust, and do not label synthetic agent responses as actual Toronto sentiment. Use consented survey data only under a separate approved collection plan.

Complete this step when every reported measure has a unit, provenance, population scope, and clear observed, estimated, or modeled label.

## Decisions before expanding

- Confirm the exact three solutions. Existing documents point to groceries, rescue and processing, and school meals. Meituan-style drones are treated here as a delivery scenario.
- Choose the first supported browsers and device classes, and decide whether the Python simulation service is local or hosted. The proposed browser renderer is Three.js; test it against the first Toronto area before scaling the scene.
- Choose the first active Toronto area and the public data layers it requires.
- Define the unlimited-lunch service before estimating infrastructure or sentiment effects.
- Set model-call limits, persistence, staffing, budget, and schedule after the first vertical slice.

The former 16-week plan and CAD estimate covered a food-policy research prototype with a visual demonstration. They do not estimate the revised Toronto 3D product.
