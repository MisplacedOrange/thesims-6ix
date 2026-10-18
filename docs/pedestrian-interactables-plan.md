# Pedestrian Food Interactables: Food Metrics and Economic Tracking

## Status and purpose

Status: the first bounded implementation is available in [sim/interactables](../sim/interactables/README.md) and the browser. It provides the five interaction types below, deterministic rule decisions, kernel-settled accounting, supplier replenishment, an emergency-site scenario, and an event-driven dashboard. It replays one six-hour scenario day; it is not an ongoing simulation service. All household and site operating values are illustrative assumptions, not calibrated Toronto parameters. Organization behavior and dashboard measures beyond that documented implementation remain design recommendations.

This plan defines pedestrian access to food services and the food and economic outcomes those interactions change. It is a food-service measurement component of the wider Toronto simulation. Track household food flows and spending, site stock and service, supplier activity, and public costs from committed events; a mapped site alone does not establish its inventory or operating capacity.

The initial study should answer a bounded question: **when food availability, price, or service capacity changes, which households can reach food, what do they obtain, and how do households, businesses, and programs respond?**

## Current implementation boundary

The browser renders Python-generated household food journeys along the Toronto walking graph and replays their committed economic and interaction events. `sim/interactables` generates legal choices, applies a deterministic rule, and settles effects through `sim.core`; the existing draft behavior package remains a separate module. Household cash and pantry belong to the household; its pedestrian travels, attends service, shops under that mandate, queues, and returns food home. See the [implemented scenario contract](../sim/interactables/README.md), [architecture](architecture.md#pedestrian-decisions), and [integration status](integration.md). The browser does not yet run an ongoing policy service.

The data plan and `sim/data` pipeline currently support location-oriented City GIS sources, including food retailers, food-support sites, and education locations. They do not supply current site-level prices, inventories, daily service capacity, demand served, or school-meal reach. Those values must remain unknown until independently sourced, or be identified as scenario assumptions. See the [Toronto data plan](data-plan.md#evidence-states) and [data pipeline documentation](../sim/data/README.md).

## Modeling boundary

Represent three related but separate actors:

1. **Households and residents.** The household owns money, pantry inventory, food needs, and shopping constraints. One or more resident pedestrians carry out trips and attend services. The pedestrian's location and mobility affect access; they do not own a separate cash balance or create food.
2. **Food and service organizations.** Retailers, distributors, processors, school nutrition operators, and food-support organizations set or receive operational state such as inventory, prices, hours, delivery plans, funding, and service capacity.
3. **Public institutions.** City and other funders can activate a policy, provide a budget, or change a program's modeled capacity. Policy activation is a simulation event with a date, budget, and stated capacity effect.

The pedestrian selects from a finite set of feasible choices generated from current state. Python validates eligibility, opening hours, travel feasibility, available stock, price, and capacity. The economic kernel rechecks a selected purchase or service before committing its effects. Optional language models may rank legal choices only after the rule-based baseline and accounting invariants are established.

## Implemented interactables

The bounded scenario currently implements the following five interaction types. Map objects can be inspectable in the browser, while only sites with a defined state transition need to be operational interactables.

| Interactable | Pedestrian or household affordances | State changes and measures |
| --- | --- | --- |
| **Home and pantry** | Review household food on hand; prepare or consume available food according to the scenario's food-use rule | Pantry inventory, meals covered, food used, and modeled unmet food need |
| **Food retailer**: supermarket, grocery, convenience store, or market | Observe currently available prices and stock when visible; choose a feasible basket; substitute, buy less, queue, purchase, delay, or leave | Store inventory and sales; household cash and pantry; transaction price, basket size, stockout, and trip success |
| **Food-support site**: food bank, pantry, community food program, hub, or fridge | Travel to the site, wait, receive an available service or basket, or be unable to receive service | Site inventory and capacity; visits, people served, wait time, unmet service demand, and household food received |
| **School nutrition site** | Attend or miss a meal opportunity when eligible and when the program is operating | Meal availability and uptake; portions served; school stock and capacity; household food demand |
| **Walking network and crossings** | Travel to a site using the available route; experience a crossing delay, access barrier, closure, or disruption when represented | Travel time, feasible destinations, access failures, and time remaining for other activities |

Add a **temporary or mobile emergency food site** only when a scenario activates it as a policy intervention. Give it an activation date, location, supply, opening schedule, capacity, funding source, and shutdown condition. Add work schedules, earnings, and transit as later extensions when the study explicitly needs income timing or non-walking access; these require their own assumptions and data.

Keep single-store trips for the first behavior baseline. Multi-stop tours, restaurant meals, household-to-household food transfers, and social influence can be added when they are necessary for a stated hypothesis and have plausible calibration evidence.

## Organization-side behavior

Pedestrians should interact with a site's offered state rather than directly control the organization. Organization-side rules determine the conditions pedestrians face.

| Organization or stakeholder | Candidate state and decisions |
| --- | --- |
| **Retail operators** | Opening hours, product availability, posted prices, purchase limits, replenishment, and staffing or service limits when evidence supports them |
| **Suppliers, distributors, and processors** | Input availability, procurement, production limits, delivery quantities and delays, and costs where records or declared assumptions exist |
| **School nutrition operators** | Operating days, meal availability, menu or modeled food category, eligible reach, portions, service capacity, and procurement requirements |
| **Food-support organizations** | Operating hours, aggregate stock, service capacity, distribution rules, and funding constraints |
| **City and other funders** | Budgets, grants or subsidies, program expansions, site activation, and the intended timing of interventions |

Do not infer individual eligibility, daily capacity, inventory, or demand from a site's presence in a directory. Keep personal food-assistance records out of the synthetic household model.

### Organization actors and bounded decisions

Organizations can be represented as economic actors when their decisions change modeled resources or services. Give each actor only the state and actions supported by its role and by the evidence available for the scenario. For example, a retailer may set prices, hours, staffing, and replenishment; a supplier may accept or constrain orders and set delivery quantities or lead times; a processor may limit throughput; and a school or food-support operator may define service hours and capacity. These decisions should use explicit rules and parameter ranges. A model can recommend or rank legal options, but it cannot create stock, funding, staff, authority, or capacity by assertion.

When a proposal may affect incumbent businesses or partner organizations, include their relevant response mechanisms only when data support them or when the study declares them as sensitivity assumptions. Possible outcomes include changes in sales, prices, service, procurement, staffing, or operating viability. Keep revenue, operating cost, transfers, and profit distinct; sales revenue alone is not a measure of business viability. A directory location does not establish an organization's current operation or willingness to participate.

City departments and funders can be modeled as actors that propose or execute actions only within a recorded mandate, approved scope, budget, and schedule. Department-agent recommendations remain distinct from accepted commands and committed economic events. Partner-run organizations are not controlled by the simulated City unless the scenario records an applicable agreement, contract, or other authority.

### Stakeholder input and representation

For each proposal, identify affected population groups, organizations that control relevant resources or services, responsible public authorities, and stakeholder input needed to assess impacts. Synthetic households, and workers if represented, can support distributional analysis, but their generated choices or dialogue do not count as consultation or as the views of real people. Keep actual consultation, survey, and partner-submission records in a separate, source-linked evidence stream. Record the date, geography, method, population reached, consent or publication limits, and groups not reached where known. Preserve conflicting views and evidence gaps; simulated stakeholder or department roles must not claim to speak for real residents, businesses, or organizations.

## Interaction and event record

Record each attempted interaction, including unsuccessful attempts. A common event record should contain:

```text
event_id, simulation_time, resident_id, household_id
site_id, site_type, action, decision_id
route_id, travel_seconds, queue_seconds, service_seconds
product_or_service_id, quantity_grams, payment_cents
result, denial_or_failure_reason
evidence_state, source_id, scenario_parameter_id
```

Use integer cents, grams, and simulation seconds for committed economic quantities. Preserve the distinction between an option being offered, an option being chosen, and the service or transaction actually being completed. Record stockout, closure, inaccessible route, unaffordable basket, and capacity denial as distinct outcomes.

## Food metrics and economic outcomes

Food and economic metrics are primary outcomes of this interactables model. Each run should preserve the event-level record and report aggregates with units, geography, population, time window, evidence state, and source or scenario assumption.

| Measure group | Measures to report | Units and interpretation |
| --- | --- | --- |
| **Food supply and site stock** | Opening/current/terminal stock; inbound and received quantities; purchases, service quantities, stockouts, and delivery shortfalls by site | Integer grams by modeled product; prices and payments in integer cents |
| **Household food** | Purchased, received, carried, and consumed food; pantry remaining; pending and final unmet need | Integer grams; unmet need is the modeled produce component in the current scenario |
| **Household and retailer economy** | Household food expenditure, retailer revenue, and procurement spending | Integer cents; sales revenue is not profit or business margin |
| **Public and program economy** | Grants, program spending, public spending, service capacity, and uptake | Integer cents for money; distinguish transfers from resource costs and do not count a transfer twice |
| **Access and service** | Travel, queue, and service time; completed trips; visits or portions; capacity uptake; denials and other failures | Integer simulation seconds; site visits and school produce portions are different capacity units (school portions are 300 g each) |
| **Distribution** | Food, spending, access, and service outcomes by area, income band, household size, and mobility | Show group counts and denominators; current dashboard totals are unweighted |

The implemented six-hour dashboard reports current stock and prices, quantities purchased or received, pantry, food used, pending/final unmet need, completed trips, service timings and failures, program capacity and uptake, retailer revenue, procurement and public spending, and outcome groups with household counts. Compare baseline and emergency-site scenarios on the same seeded population, and show the event window so pre-opening and operating periods are not conflated.

Keep household purchases, retailer receipts, supplier payments, public grants, and public outlays as distinct measures. Do not infer profit, business margin, or full social resource cost from revenue or transfers alone.

Use **modeled unmet food need** for the simulation outcome unless the model has a validated, broader food-security measure. The current scenario reports a produce-component `unmet_grams` shortfall; it does not measure complete diet adequacy, observed hunger prevalence, or clinical outcomes. Do not label that value as those outcomes. The scenario does not model non-food spending, income timing, business margins, or a continuous multi-day economy. See [integration limitations](integration.md#connected-district-day) and the [implemented scenario evidence boundary](../sim/interactables/README.md#evidence-boundary).

## Toronto grounding and evidence states

The City of Toronto describes student nutrition programs as community-based and locally operated, with delivery shaped by local needs, resources, infrastructure, and demographics. This supports modeling school sites with distinct schedules and capacities when operator evidence is available. The City also reports program funding and related food-hub work; these are potential institutional and procurement stakeholders, not pedestrian attributes. See the [City's Student Nutrition Program page](https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/student-nutrition-program/).

For relevant locations and current services, use City and operator records with identifiers, source dates, and geography. Keep the following evidence states distinct:

- **Observed:** value directly present in a dated source or transaction record.
- **Announced:** future program or capacity stated by an organization, not yet observed as delivered.
- **Estimated:** derived using an explicit method from observed inputs.
- **Illustrative:** scenario parameter used because an observed value is unavailable.
- **Unknown:** missing information with a reason; never silently replace it with zero.

The Toronto food-access ABM literature provides a useful initial scope: the FAAMC model represents household location, income, vehicle ownership, and distance to food stores, then examines household food availability under changes such as store availability or income. This is a design precedent, not a Toronto calibration source. [FAAMC study](https://doi.org/10.1007/s12571-019-00900-7). A school meal stakeholder study also found that cafeteria characteristics and staff supervision can affect how stakeholders assess a meal simulation, supporting configurable school-site operations rather than one uniform school object. [MealSim stakeholder study](https://doi.org/10.1016/j.jneb.2024.02.008).

## Remaining measurement and model gates

1. **Preserve event-to-metric traceability.** Keep each dashboard quantity linked to committed ledger or interaction events, its unit, scenario assumption, and evidence state.
2. **Compare matched scenarios.** Use the same household roster and seed for baseline and emergency-site runs; report paired changes in food quantities, household spending, access, retailer revenue, procurement, and public spending.
3. **Ground site inputs.** Replace illustrative prices, opening stock, service capacity, and operating schedules only when dated site or operator evidence supports them; otherwise retain explicit scenario ranges or unknowns.
4. **Expand food measures carefully.** Add other food groups or nutritional measures only when product composition, preparation, storage, and household food-use rules support those units. The produce-only `unmet_grams` value is not diet adequacy or observed food insecurity.
5. **Extend the economic model with evidence.** Add income timing, non-food essentials, labor, rent, operating costs, or margins only when the scenario has defensible inputs and a clear accounting treatment.
6. **Extend beyond the six-hour day.** Add multi-day budgets, replenishment, schedules, and persistence before using this module to claim longer-term household or policy effects.

Keep deterministic rule choices as the baseline. Conservation of money and food, legal action generation, route feasibility, and repeated-run determinism are implementation checks, not evidence of real-world calibration. Add model-based choices only after the food/accounting measures and replay behavior are stable.
