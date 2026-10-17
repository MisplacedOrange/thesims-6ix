# Build a Toronto food-policy simulator

## What we are building

The October 17 revision adds an explicit infrastructure-planning agent and emphasizes current-world economic inputs, repeatable acquisition checkpoints, realistic rollout durations, and inspectable human responses. Keep the food-policy scope below. The planner must propose sourced sites, costs, dependencies, timing ranges, and capacity ramps for deterministic validation; it cannot create infrastructure by assertion. It is separate from household choice agents.

The consolidated implementation is an initial mechanism-integration milestone. It is not completion of the 16-week plan. [Integration status](docs/integration.md) records what runs and what remains, including current-data ingestion, infrastructure planning, multi-product adequacy, longer horizons, persistence, and the browser connection.

Build a stylized 3D Toronto neighbourhood with households, stores, schools, a food hub, processing equipment, vans, and optional delivery drones. Residents shop, travel, receive school meals, encounter shortages, change plans, and explain selected choices through bounded LLM agents. An analyst can change a policy and compare outcomes against the same neighbourhood without that change.

The central product question is concrete. Who gets more usable food, how much money and time do they save, who remains underserved, and what does the municipality pay?

The first release is an exploratory research prototype with an accessible visual demonstration. Its economic model is a neighbourhood partial-equilibrium model. It does not predict Toronto's entire economy. Simulated residents and their generated comments cannot establish actual public opinion.

The user supplied three Toronto initiatives and requested Meituan-style food delivery. Preserve all four workstreams:

| Workstream | Change represented | Main comparison |
| --- | --- | --- |
| Affordable municipal groceries | Four potential stores, location choices, procurement, overhead, pricing, and subsidy | Existing retail access against alternative sites and funding rules |
| Rescue and processing | Eligible surplus, pickup, cold storage, processing yields, and distribution | Existing rescue arrangements against additional usable capacity |
| School meals and shared purchasing | Program reach, meal uptake, menus, contracts, hubs, and distribution | Current provision against expansion, then separate against pooled procurement |
| Meituan-style drones | Fixed hub-to-locker routes, loading, flight, collection, and ground fallback | Ground delivery against explicitly hypothetical Toronto drone corridors |

The [policy evidence document](docs/policies-and-evidence.md) distinguishes adopted decisions, funding, announced reach, and measured operations. The project must preserve those distinctions when constructing a baseline.

## The first user experience

A visitor opens a Toronto district and sees a school morning. A household has a limited grocery budget and a child attending a school with a food program. A food hub loads a van. A processing facility accepts a batch of rescued produce. Every movement connects to a recorded transaction or logistics event.

The visitor selects a household and sees cash remaining, its food basket, travel time, known store prices, and the events behind its last decision. A short generated explanation might say that the household chose a familiar store because the cheaper one required an extra trip. The inspector labels that sentence as generated from the simulation.

The visitor pauses at a day boundary, adds a municipal store with a stated subsidy, and forks the run. A side-by-side comparison shows basket costs, unmet food needs, travel, stockouts, food waste, and municipal expenditure. The original run remains available. A policy that lowers prices but exhausts its subsidy must show both effects.

The analyst can run the same experiment headlessly, with graphics disabled and rule-based choices. They can download the manifest, assumptions, events, ledger, subgroup results, and decision records. A demo and an experiment use the same economic state.

## Product modes

| Mode | Agent policy | Clock | Purpose |
| --- | --- | --- | --- |
| Explore | Rules plus a bounded set of live LLM decisions | Pauses at decision barriers | Demonstrate individual choices and visible consequences |
| Experiment | Rules or a declared LLM study | Runs without rendering | Estimate model counterfactuals across seeds and assumptions |
| Replay | Recorded decisions and events | Scrub or play | Inspect a completed run without new provider calls |

The camera never selects which residents receive LLM decisions. The experiment configuration fixes that sample. Otherwise a visitor looking at one neighbourhood could change its measured behavior.

## Chosen system shape

Use a Python simulation process as the sole writer of a run's economic state. A browser client uses Three.js for 3D presentation and a conventional UI for controls, charts, and inspection. FastAPI exposes commands and projections. Start with SQLite for local runs and immutable files for input snapshots and exports.

One process owns one world. Run independent replications in separate processes. Add PostgreSQL and shared job scheduling only when concurrent use requires them. The initial design does not need a service per actor, a vector database, or a city-scale game engine.

LLMs return proposed choices from a list of legal options. They cannot transfer money, mutate inventory, move a vehicle, or invent a supply contract. Deterministic settlement validates and commits every action. Rendering consumes committed events and interpolates movement.

The [architecture specification](docs/architecture.md) defines ownership and proposed interfaces. The [decision record](docs/architecture-decision.md) compares this design with a Godot-authoritative native application. Python authority fits data analysis and repeated policy experiments. Browser delivery makes a demonstration easier to share.

## Geographic and population scope

Begin with a clearly labeled synthetic district inspired by Toronto. Build approximately 250 household records, one municipal-store candidate, existing retailers, several schools, one processor, and one hub. Use simplified geometry before importing a full 3D massing tile.

The next scope is a 1,000-household district with observed aggregate constraints and dated geographic data. Simulated households are individual economic units with resident members. A household can coordinate purchases across its members. A child sprite does not independently spend the household budget.

The four-store policy requires a later configuration covering all four Community Council districts. The first neighbourhood prototype cannot establish citywide effects or choose Toronto's final four sites. Treat candidate sites as a location-allocation study with travel, capacity, cost, and distributional constraints.

Do not scale by making one household carry a large arbitrary weight. That changes queue lengths, indivisible purchases, and vehicle utilization. If weighted cohorts become necessary, introduce an explicit aggregation model and validate its results against unweighted runs.

## What the model measures

Keep results in their original units. A single policy score would conceal tradeoffs.

| Outcome | Definition |
| --- | --- |
| Food affordability | Price of a fixed reference basket and actual household food expenditure, reported separately |
| Access | Network travel minutes, time spent collecting food, opening-hour compatibility, and unavailable options |
| Food sufficiency | Modeled basket shortfall and served meal equivalents under declared portion rules |
| Distribution | Outcomes by income group, household size, area, mobility constraints, and school eligibility |
| Fiscal cost | Capital cash outlay, recurring public expense, fee relief, and subsidy commitments |
| Store viability | Procurement, revenue, overhead, subsidy, waste, and cash runway |
| Rescue performance | Eligible collected mass, accepted mass, edible output, spoilage, and usable deliveries |
| School performance | Eligible students, uptake, meals served, kitchen throughput, and household substitution |
| Delivery performance | Completed orders, total door-to-collection time, failures, operating cost, and service exclusions |
| Human response | Observable modeled choices plus separately labeled stress, trust, and satisfaction proxies |

The model must show residents who lose access, encounter cultural or dietary mismatch, cannot reach a locker, or do not have time to use the cheaper store. Average savings alone are insufficient.

## The role of LLM agents

Start with a transparent utility model for routine choices. Add LLM decisions at defined opportunities such as an unfamiliar store opening, a shortage, a change in school meals, or a switch between ground and drone delivery. The model should work with the LLM gateway disabled.

Use a fixed, stratified panel of up to 40 focal households. Permit at most one LLM choice per focal household per simulated day. The proposed 30-day maximum is 1,200 requests, with 1,500 input tokens and 200 output tokens per request. A separate CAD 30 run ceiling can stop dispatch earlier. These are planning limits, not a provider quote or a cost forecast.

The scheduler reserves maximum configured charges before dispatch and records refusals, timeouts, invalid responses, and deterministic fallbacks. Freeze prompts, provider configuration, input observations, and decision receipts. A seed cannot reproduce a fresh live model response. Replay uses the recorded response.

Household feelings are latent model variables driven by food shortfall, financial strain, time pressure, and recorded experiences. LLM text can explain those variables. It cannot establish them as factual human emotions. Validate real attitudes through consented surveys or interviews if that becomes part of the research.

## Evidence and economic data

Freeze observations available by October 17, 2026. Maintain the observation period, release date, geography, units, source, and transformation for every input. Toronto City, Toronto CMA, Ontario, Canada, and food-bank network statistics are different populations.

Use current CPI as a time index, not as a local shelf-price list. Use Toronto's nutritious food basket as a reference household basket, not every household's spending. Use food-bank visits as service demand, not unique people or population prevalence. The [data plan](docs/data-plan.md) describes source acquisition and the synthetic population.

Unknown operating costs, processing yields, uptake, and household price responses remain explicit parameters. The application must distinguish evidence-backed values from illustrative defaults and researcher estimates. No generated figure becomes a verified input merely because an LLM wrote it.

## Estimate impacts through experiments

Compare baseline and treatment runs with matched household records, source snapshots, and named random streams. Begin with each policy alone. Then test combinations because school meals, rescued food, and cheaper stores can serve the same households and compete for the same food.

Run a 16-cell screening experiment across the four policy switches. This is a hypothetical mature-policy experiment. Separately run a dated rollout experiment that respects approvals, procurement, staffing, and capacity ramps. The two answer different questions.

Use at least 30 paired replications initially and expand based on a declared precision target. Report simulation variation, parameter uncertainty, and model limitations separately. A narrow Monte Carlo interval does not prove that the model matches Toronto.

Compare results with and without live LLM choice. Test whether generated decisions change the estimated policy effect and whether those changes remain within calibrated behavioral ranges. Treat a surprising LLM narrative as a hypothesis to investigate.

## Delivery strategy

Plan a 16-week research prototype beginning with a two-week demonstrator, measured from an agreed kickoff. The demonstrator covers one household shopping path, a visible transaction, and a replay. It does not cover all policy research.

Assume two full-time engineers, a half-time economic or operations analyst, a quarter-time 3D designer, and limited domain review. The 16-week prototype includes all four workstreams, bounded agents, exports, and validation fixtures. A research instrument suitable for consequential policy use needs additional data access, external review, and observed-outcome validation beyond this prototype.

The proposed labor allowance is CAD 206,400 before contingency, using explicit hypothetical hourly rates. A 20% contingency brings that to CAD 247,680. These figures are planning arithmetic, not supplier quotes. The [delivery document](docs/delivery.md) provides the calculation, milestones, and acceptance gates.

Real-world policy implementation is a separate schedule. A grocery strategy due in Q2 2027 does not imply stores open that quarter. The [policy timing table](docs/policies-and-evidence.md) identifies the operational dependencies and illustrative ranges.

## Decisions settled by this plan

- Keep one authoritative state owner per run and a separate presentation client.
- Conserve money and food through explicit ledgers and lot transformations.
- Treat LLM output as a bounded proposed choice with recorded fallback.
- Preserve observed facts, approved plans, assumptions, and hypothetical policies as different evidence states.
- Make the first neighbourhood small enough to inspect event by event.
- Deliver all four policy models before attempting citywide scale or detailed character gameplay.

## Questions for implementation kickoff

The plan proceeds with browser delivery, a research-prototype goal, synthetic households, and the staffing assumptions above. The following answers refine implementation without blocking this planning package:

- Which Toronto neighbourhood and community partners should anchor the first observed-data district?
- Can partners provide aggregate procurement prices, processing throughput, school uptake, and delivery records?
- Who will review the model equations and conclusions independently?
- What actual hardware, hosting allowance, and provider budget replace the proposed targets?
- Is a later public experience primarily educational, analytical, or a game?

The next build task is the literal food-and-money fixture described in [delivery](docs/delivery.md). It establishes the transaction path before more agents or graphics make errors harder to see.
