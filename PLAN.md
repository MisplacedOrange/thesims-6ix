# The Sims 6ix: a 3D Toronto pedestrian simulation

## Active implementation scope

The current deliverable is a polished browser 3D Toronto environment with synthetic pedestrian agents. The implementation in apps/web focuses on geography, landmarks, movement, camera controls, lighting, and inspection. Public solutions, infrastructure planning, and economic outcomes are deferred. The broader research plan below describes future work and does not authorize those features in this milestone.

## Product goal

Build a 3D simulation of Toronto where pedestrians move through a recognizable city environment, public solutions roll out over time, and the simulation records changes in access, household economics, public cost, and modeled human response.

Make the Toronto world the first product milestone. Treat food programs as scenarios inside that world. The current school-day prototype remains useful for testing food accounting, but it does not set the shape or time horizon of the product.

The project has four linked goals:

1. Build a geospatial 3D Toronto environment from dated, licensed city data.
2. Populate active areas with pedestrian agents using rule policies, small models, and a bounded number of LLM decisions.
3. Use a separate LLM planner to propose infrastructure and staged rollout plans for three public solutions.
4. Compare baseline and rollout outcomes by neighborhood and population group, including economic measures and labeled modeled response.

This is an exploratory planning and research tool. It does not predict Toronto's entire economy or establish actual public opinion.

## The three solutions

The current project documents identify three Toronto policy initiatives:

| Solution | Simulation role | First planning questions |
| --- | --- | --- |
| Affordable municipal groceries | Sites, procurement, operating model, prices, and subsidy | Which locations improve access? What staffing, funding, supplier, and capacity conditions affect opening? |
| Food rescue and processing | Collection, cold storage, processing, and distribution capacity | Where are facilities useful? Which supply, equipment, labor, and buyer constraints limit output? |
| Expanded school meals, including the proposed unlimited-lunch option | School kitchens, food storage, menus, staffing, procurement, and delivery | Which schools can serve more students? What equipment, workers, food volumes, funding, and rollout stages are required? |

The existing planning package also includes Meituan-style drone delivery. Treat drones as a delivery scenario that can support a solution, not as a fourth public solution. Ground delivery remains a comparison. The exact eligibility, participation, menu, and service promise for the unlimited-lunch proposal still needs a policy definition.

This mapping follows the three Toronto initiatives identified in the existing plan. Confirm the names and boundaries before treating them as settled policy requirements.

## Toronto is the primary environment

Build a 3D Toronto base from licensed building massing, street geometry, and other verified geographic layers. Use a citywide visual overview with lower detail outside the active simulation areas. Give selected neighborhoods detailed routes, people, destinations, and policy infrastructure first.

A visible building does not imply that the model knows its rent, capacity, ownership, or activity. Keep geometry and economic attributes as separate evidence-bearing data. Use stable feature IDs to connect the scene, pedestrian network, public services, and rollout proposals.

The first environment should include homes, streets, sidewalks or walkable links, transit access where data support it, schools, food retailers, community food services, and candidate infrastructure sites. Do not make school buildings the organizing frame for the city.

The first working district can have fewer active agents than the citywide scene. Expand behavioral and economic coverage after the coordinate system, feature IDs, routes, and data provenance work end to end.

## Pedestrian agents

Represent people as moving agents with a current place, destination, activity, mobility needs, schedule, known information, and recorded choices. Use synthetic records built from aggregate controls. Do not assign real identities or infer personal routines from area averages.

Use deterministic rules or small models for routine actions and navigation. Use LLMs for selected choices that benefit from richer context, such as service uptake, a response to a closure, or a change in travel mode. Freeze the LLM panel and decision opportunities before a run. The camera must not decide which people receive model calls.

An agent proposes a legal intent, such as travel to a school, shop, or service. The Python simulation service checks that a route exists and advances movement. The economic model checks budgets, stock, and policy eligibility before recording purchases or service. A model cannot directly move a person, create food, spend money, or invent capacity.

A household remains the shared financial unit when its members pool food and money. Individual residents can have their own locations, schedules, mobility, and service experiences. The model must state who controls a household purchase and record which resident carried it out.

## Infrastructure rollout planner

Build a planner that proposes how to phase each solution into Toronto. Its first demonstration can plan the school meal expansion described above, but the city simulation must remain useful when that scenario is off.

The LLM planner receives a declared goal, a frozen map and evidence snapshot, current infrastructure, budgets, and rollout constraints. It returns a structured proposal with candidate sites, required equipment, staffing, storage, procurement and delivery dependencies, capital and operating costs, time ranges, capacity ramps, uncertainties, and stop conditions. Each sourced claim includes source IDs. Unknown values stay unknown.

A deterministic validator checks source references, site eligibility, units, budgets, dependencies, timing, and capacity consistency. A reviewer accepts or rejects the validated plan. The simulation activates only accepted milestones, and it records each delayed, reduced, or canceled stage. The planner cannot create infrastructure by assertion.

The planner operates on a slower schedule than pedestrian choices. It can propose a multi-year rollout while daily agents move, attend services, shop, and respond to changes. A change in the rollout creates a new scenario or a fork at a recorded boundary.

## Economic and human outcomes

Use the existing ledger approach to record money and food. Extend it to the selected Toronto services and infrastructure rather than replacing it with generated narrative.

Report outcomes in their original units. Include public capital and operating costs, household spending, travel time and distance, service reach, capacity, unmet need, delivery reliability, and impacts by neighborhood, income, household type, and mobility constraint. Keep costs, transfers, and resource use distinct.

Track behavior separately from modeled response and from measured survey evidence. A modeled response may include perceived access, trust, stress, or satisfaction when its drivers and limits are explicit. Record its model version and causal events. Generated dialogue does not count as sentiment data.

If the project later collects consented survey responses, store them as a separate evidence stream and compare them with model outputs. Do not present simulated sentiment as the opinion of Toronto residents.

## Product modes

| Mode | World | Agent behavior | Purpose |
| --- | --- | --- | --- |
| Explore | 3D world with staged time controls | Rules and selected bounded model decisions | Inspect pedestrian activity and infrastructure changes |
| Plan | Frozen evidence and infrastructure snapshot | LLM proposes, deterministic checks validate | Compare feasible rollout options before a simulation run |
| Experiment | Headless or rendered replicated runs | Declared rule, small-model, or recorded policy | Compare economic and modeled response outcomes |
| Replay | Recorded world and economic events | No new model calls | Inspect a completed run and its causes |

A visible run and its headless counterpart use the same decisions and economic events. Rendering does not change results.

## Proposed architecture direction

The simulation must be available as a browser app. Use a TypeScript and React client with Three.js for the Toronto scene, camera, controls, selection, and interpolation; Vite is the current prototype's development/build tool. Keep the browser as a renderer and command surface; it must not own authoritative simulation state. A Python simulation service advances logical world time, resident movement, policy events, and economic settlement. The existing Python economic kernel remains the only writer of money, food, reservations, and settled policy transactions. A versioned API accepts legal intents and rollout commands and returns committed events or receipts before the client displays economic changes.

Use the same Python simulation path for rendered, headless, and replay runs. Logical simulation time and event ordering must not depend on browser frame rate, dropped frames, or camera position. The vertical slice must load a Toronto map, move one synthetic pedestrian, settle one economic action, and replay the same recorded events in the browser and headlessly. This browser-first direction reflects the direct-browser delivery requirement.

Use immutable snapshots for source data, scenarios, planner proposals, and completed runs. Add durable storage and recovery before enabling long live sessions or provider calls. Do not create a service per pedestrian. Keep the browser rendering only the active area at full detail and use simpler citywide context; establish device and performance targets through measurement on the lowest supported hardware.

## First release and boundaries

The first release should show a real Toronto 3D context and one selected active area. It should move a small synthetic pedestrian population along a sourced or clearly labeled pedestrian network. It should compare a baseline with a validated, staged school meal rollout and report the economic and modeled response changes.

Keep all three solutions in the scenario registry from the start. The school meal rollout can be the first end-to-end planner demonstration; extend the same staged-planning contract to groceries and processing after that slice works. Expand active geography and agent population after data and replay are stable. Detailed character customization, residential interiors, social relationships, photorealistic assets, and operational drone dispatch are outside the first release.

## Open decisions

- Confirm the names and rules for the three solutions. The school proposal needs an exact definition of "unlimited lunches."
- Select the first active Toronto area and confirm which source data and licenses support it.
- Select the first supported browsers and device classes, and decide whether the Python service is local to one user's machine or hosted for shared access.
- Define which pedestrian decisions use rules, small models, or LLMs and set a run-level cost and latency limit.
- Choose the first economic and modeled-response outcomes with domain reviewers.
- Set staffing, schedule, hardware, and operating budgets for the revised scope. Existing estimates describe the earlier food-policy prototype and do not price this product.
