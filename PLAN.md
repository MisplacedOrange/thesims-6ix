# The Sims 6ix: a 3D Toronto pedestrian simulation

## Current implementation status

The browser app in apps/web provides the visual foundation: a sourced downtown Toronto scene, seeded pedestrian itineraries, camera and layer controls, and resident inspection. It is not yet connected to a proposal chat, department agents, or an ongoing policy simulation. This plan describes the target product and a staged path toward it; it does not claim those components are implemented.

## Product scope

Build an ongoing Toronto simulation that lets a user bring real-world policy proposals into a Council-style chat, have expert agents translate them into feasible staged work, and observe their modeled effects over time. The chat accepts uploaded Markdown proposals and supports clarification, amendment, review, and approval. The system preserves the proposal's source material, goals, outcome measures, constraints, unknowns, and assumptions as versioned data.

Municipal department and delivery-partner agents represent roles such as public health, planning and construction, finance and procurement, food program operations, and logistics. They plan and coordinate simulated work. A deterministic simulation service remains authoritative for the world clock, budgets, routes, inventories, capacities, economic transactions, and stage activation. Simulated approvals or actions never become real City decisions, permits, purchases, or construction.

The city continues running as policies move through planning, approval, procurement, construction or readiness, operation, delay, reduction, or cancellation. Proposal-specific outcome measures and important unknowns stay visible and are tracked over the life of the simulation. The initial demonstration proposals are examples for an open proposal-intake system, not a fixed product catalog.

## Product goal

Build a 3D simulation of Toronto where pedestrians move through a recognizable city environment, public solutions roll out over time, and the simulation records changes in access, household economics, public cost, and modeled human response.

Make the Toronto world the first product milestone. Treat food programs as scenarios inside that world. The current school-day prototype remains useful for testing food accounting, but it does not set the shape or time horizon of the product.

The project has five linked goals:

1. Maintain a geospatial 3D Toronto environment from dated, licensed city data.
2. Accept and version new Markdown policy proposals through a Council-style chat without requiring proposal-specific code.
3. Simulate pedestrian residents and relevant municipal or delivery-partner expert roles with clear authority boundaries.
4. Coordinate feasible, staged infrastructure work and continue the world simulation as changes become operational.
5. Track proposal-defined and standard outcomes by area and population group, including economic measures and clearly labeled modeled response.

This is an exploratory planning and research tool. It does not predict Toronto's entire economy or establish actual public opinion.

## Initial demonstration proposals

The first demonstration uses three sourced Toronto proposals. They are fixtures for proving the shared intake and simulation workflow, not an exhaustive set of supported interventions.

| Demonstration proposal | Simulation role | First planning questions |
| --- | --- | --- |
| Affordable municipal groceries | Sites, procurement, operating model, prices, and subsidy | Which locations improve access? What staffing, funding, supplier, and capacity conditions affect opening? |
| Food rescue and processing | Collection, cold storage, processing, and distribution capacity | Where are facilities useful? Which supply, equipment, labor, and buyer constraints limit output? |
| Expanded school meals, including the proposed unlimited-lunch option | School kitchens, food storage, menus, staffing, procurement, and delivery | Which schools can serve more students? What equipment, workers, food volumes, funding, and rollout stages are required? |

The exact eligibility, participation, menu, and service promise for the unlimited-lunch proposal still need definition. Drone delivery can be added as a logistics proposal when supported by an uploaded problem statement and relevant evidence; it is not a special hard-coded exception.

## Toronto is the primary environment

Maintain and expand the existing frozen downtown Toronto scene using licensed building massing, street geometry, and other verified geographic layers. Use a citywide visual overview with lower detail outside the active simulation areas. Give selected neighborhoods detailed routes, people, destinations, and policy infrastructure first.

A visible building does not imply that the model knows its rent, capacity, ownership, or activity. Keep geometry and economic attributes as separate evidence-bearing data. Use stable feature IDs to connect the scene, pedestrian network, public services, and rollout proposals.

## Council chat and proposal intake

The side-panel chat is the working session for a simulated City Council. The user can upload a Markdown proposal, deliberate on its goals, ask for departmental analysis, amend interpretation, inspect sources, and record a versioned Council decision. The intake agent extracts named actors, requested changes, geographic and service constraints, outcome measures, timelines, funding, unknowns, and assumptions. It preserves citations and quotes for review; it does not turn unsupported claims into facts or silently fill missing values. The decision and approval rules for the demo remain open, and nothing authorizes real City action.

For each proposal, intake should also map affected population groups, businesses and organizations that control relevant resources or services, responsible public authorities, and likely spillover effects. Keep actual resident, worker, business, and community input as dated, source-linked evidence, separate from synthetic household behavior and simulated department or stakeholder recommendations. Record known gaps in who was reached; generated dialogue must not imply real consultation, endorsement, or representation.

The initial three proposals should be loaded through this same path. A new proposal must be representable without adding a new product-specific solution ID or code branch. When a proposal omits a required value, the system records an unknown, offers explicit scenario ranges where appropriate, or asks the user to clarify.

The first environment should include homes, streets, sidewalks or walkable links, transit access where data support it, schools, food retailers, community food services, and candidate infrastructure sites. Do not make school buildings the organizing frame for the city.

The first working district can have fewer active agents than the citywide scene. Expand behavioral and economic coverage after the coordinate system, feature IDs, routes, and data provenance work end to end.

## Pedestrian agents

Represent people as moving agents with a current place, destination, activity, mobility needs, schedule, known information, and recorded choices. Use synthetic records built from aggregate controls. Do not assign real identities or infer personal routines from area averages.

Use deterministic rules or small models for routine actions and navigation. Use LLMs for selected choices that benefit from richer context, such as service uptake, a response to a closure, or a change in travel mode. Freeze the LLM panel and decision opportunities before a run. The camera must not decide which people receive model calls.

An agent proposes a legal intent, such as travel to a school, shop, or service. The Python simulation service checks that a route exists and advances movement. The economic model checks budgets, stock, and policy eligibility before recording purchases or service. A model cannot directly move a person, create food, spend money, or invent capacity.

A household remains the shared financial unit when its members pool food and money. Individual residents can have their own locations, schedules, mobility, and service experiences. The model must state who controls a household purchase and record which resident carried it out.

## Infrastructure rollout planner

Build a coordinated team of simulated expert agents that proposes how to phase each uploaded proposal into Toronto. Department roles can cover public health, planning and construction, finance, procurement, food operations, and logistics. The team works from the approved proposal, frozen evidence snapshot, current infrastructure, available budgets, and rollout constraints. It can identify dependencies and disagreements, but cannot invent authority, funding, or capacity.

The agents return structured work packages with candidate sites, required equipment, staffing, storage, procurement and delivery dependencies, capital and operating costs, time ranges, capacity ramps, uncertainties, outcome measures, and stop conditions. Each sourced claim includes source IDs. Unknown values stay unknown. Council approval is recorded separately from departmental recommendations.

A deterministic validator checks source references, site eligibility, units, budgets, dependencies, timing, and capacity consistency. A reviewer accepts or rejects the validated plan. The simulation activates only accepted milestones, and it records each delayed, reduced, or canceled stage. The planner cannot create infrastructure by assertion.

Department planning operates on a slower schedule than pedestrian choices. It can propose a multi-year rollout while daily agents move, attend services, shop, and respond to changes. The world persists across rollout stages and records the policy, source, approval, and outcome events that change its state. A deliberate alternative plan creates a versioned branch at a recorded boundary.

## Economic and human outcomes

Use the existing ledger approach to record money and food. Extend it to the selected Toronto services and infrastructure rather than replacing it with generated narrative.

Report outcomes in their original units. Include public capital and operating costs, household spending, travel time and distance, service reach, capacity, unmet need, delivery reliability, and impacts by neighborhood, income, household type, and mobility constraint. Keep costs, transfers, and resource use distinct.

Track behavior separately from modeled response and from measured survey evidence. A modeled response may include perceived access, trust, stress, or satisfaction when its drivers and limits are explicit. Record its model version and causal events. Generated dialogue does not count as sentiment data.

If the project later collects consented survey responses, store them as a separate evidence stream and compare them with model outputs. Do not present simulated sentiment as the opinion of Toronto residents.

## Product modes

| Mode | World | Agent behavior | Purpose |
| --- | --- | --- | --- |
| Explore | 3D world with staged time controls | Rules and selected bounded model decisions | Inspect pedestrian activity and infrastructure changes |
| Council | Uploaded proposal and evolving simulation | Chat supports simulated deliberation; human records the decision | Turn a sourced proposal into an explicit, versioned simulation decision |
| Plan | Current world and approved proposal | Department agents propose work packages; deterministic checks validate | Coordinate feasible rollout stages and surface conflicts or unknowns |
| Experiment | Headless or rendered replicated runs | Declared rule, small-model, or recorded policy | Compare economic and modeled response outcomes |
| Replay | Recorded world and economic events | No new model calls | Inspect a completed run and its causes |

A visible run and its headless counterpart use the same decisions and economic events. Rendering does not change results.

## Proposed architecture direction

The simulation must be available as a browser app. Use a TypeScript and React client with Three.js for the Toronto scene, camera, controls, selection, and interpolation; Vite is the current prototype's development/build tool. Keep the browser as a renderer and command surface; it must not own authoritative simulation state. A Python simulation service advances logical world time, resident movement, policy events, and economic settlement. The existing Python economic kernel remains the only writer of money, food, reservations, and settled policy transactions. A versioned API accepts legal intents and rollout commands and returns committed events or receipts before the client displays economic changes.

Use the same Python simulation path for rendered, headless, and replay runs. Logical simulation time and event ordering must not depend on browser frame rate, dropped frames, or camera position. The vertical slice must load a Toronto map, move one synthetic pedestrian, settle one economic action, and replay the same recorded events in the browser and headlessly. This browser-first direction reflects the direct-browser delivery requirement.

Use immutable snapshots for source data, scenarios, planner proposals, and completed runs. Add durable storage and recovery before enabling long live sessions or provider calls. Do not create a service per pedestrian. Keep the browser rendering only the active area at full detail and use simpler citywide context; establish device and performance targets through measurement on the lowest supported hardware.

## First release and boundaries

The first release should preserve the Toronto 3D environment, add the Council chat and proposal intake, and run an ongoing authoritative simulation for a selected area. The demo should load the grocery, surplus-processing, and school-food Markdown proposals through the shared intake path and show proposal-specific metrics, unknowns, expert work packages, staged simulated changes, and a replayable event history. New proposals should follow the same flow without code changes.

Keep the first active geography and population small enough to validate data, replay, department coordination, and performance. Detailed character customization, residential interiors, photorealistic assets, and real-world operational authority are outside the first release.

## Open decisions

- Define which decisions the Council chat records as human-approved and which work packages department agents can resolve within approved limits.
- Define the reusable Markdown proposal contract, source extraction, unknown handling, outcome metrics, and version lifecycle.
- Map simulated expert roles to real department responsibilities without implying official City participation or authority.
- Specify how an ongoing simulation is checkpointed, paused, resumed, forked, and replayed.
- Define how the first three demonstration proposals represent open questions such as grocery sites and school meal service rules.
- Validate the current active Toronto area and its source data and licenses; select the next area for expansion.
- Select the first supported browsers and device classes, and decide whether the Python service is local to one user's machine or hosted for shared access.
- Define which pedestrian and department decisions use rules, small models, or LLMs and set run-level cost, latency, and audit limits.
- Choose the first economic and modeled-response outcomes with domain reviewers.
