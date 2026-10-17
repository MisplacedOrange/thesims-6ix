# Delivery and costs

## Staffing and delivery assumption

The proposed 16-week prototype assumes two full-time engineers, a half-time economist or operations analyst, a quarter-time 3D designer, and limited food-system or community review. One engineer leads simulation and data. The other leads the service, 3D client, and agent gateway. Both review settlement and replay.

The schedule begins at an agreed kickoff. It is not a commitment from Toronto or any partner. Missing data access can extend calibration while the synthetic demonstrator continues.

## Milestones with observable results

| Weeks | Deliverable | Acceptance gate |
| --- | --- | --- |
| 1 to 2 | Synthetic transaction path, literal accounting fixture, simple 3D purchase, recorded replay | Exact expected cents and grams, visible event inspection, no browser-owned economic state |
| 3 to 5 | 250-household baseline, network travel, store inventory, household and school assignments, source snapshots | Reproducible rule-based runs, no overspending or duplicate food, baseline quality report |
| 6 to 8 | Grocery, processing, school meals, and procurement policies | Each policy changes declared mechanisms, exposes cost, and passes adverse scenarios |
| 9 to 11 | District 3D, queues, vans, processor, charts, comparison, fork and reconnect | Headless and visible economic hashes match, every displayed economic action traces to an event |
| 12 to 13 | Bounded LLM panel, grounded explanations, budget and failure controls | Gateway-disabled run works, fault injection respects call and spending limits |
| 14 to 16 | Hypothetical drones, 1,000-household performance run, study exports, sensitivity analysis, independent review | All four workstreams present, no-approval drone branch, complete replay and documented model limits |

The two-week demonstrator is part of the 16-week prototype, not an additional project. It is deliberately narrow. It proves a visible economic path while the broader food-system work develops.

A more credible observed-data research release may need 24 weeks or more, depending on partner access, calibration, and review. No amount of rendering work substitutes for missing operating data.

## Ordered implementation backlog

| ID | Owner | Work | Depends on | Done when |
| --- | --- | --- | --- | --- |
| D01 | Analyst | Confirm district, questions, evidence states, and primary outcomes | None | Signed-off study brief and unknown-input register exist |
| D02 | Simulation engineer | Units, lots, accounts, balanced transactions | D01 | Literal fixture passes with exact final values |
| D03 | Simulation engineer | Clock, complete event reducer, checkpoints, recovery | D02 | Crash and duplicate-command fixture reproduces state |
| D04 | Data lead | Source snapshots, transforms, synthetic population, geography | D01 | Manifest and aggregate quality report reproduce inputs |
| D05 | Simulation engineer | Households, pupils, baseline shopping, food use | D03, D04 | Spending, school assignment, stock, and travel reconcile |
| D06 | Simulation engineer | Stores, processor, meals, pooled procurement | D05 | Separate and combined policies pass mechanism fixtures |
| D07 | Client engineer | Scene protocol, inspector, accessible results table | D03 | Transaction path and reconnect work from real events |
| D08 | Client engineer and designer | District scene, queues, carriers, replay and comparison | D06, D07 | Renderer-independent runs and traceable animations pass |
| D09 | Client engineer | LLM offers, receipts, charge reservation, fallback | D05, D07 | Invalid, late, refused, and uncertain requests behave correctly |
| D10 | Simulation engineer | Drone corridors, handoff, battery, downtime, ground fallback | D06, D08 | No-approval and failed-handoff cases export correctly |
| D11 | Analyst | Replicated studies, sensitivity, held-out calibration | D06, D09, D10 | Model report separates uncertainty and observed evidence |
| D12 | Team and reviewer | Performance, recovery, source audit, documentation | D08, D11 | Acceptance record identifies passed gates and remaining limits |

D01 and D04 can continue while D02 and D03 establish the kernel. D07 can start with the narrow fixture before the full neighbourhood exists. Keep each implementation unit reviewable and verified before expanding its population.

## First ten working days

1. Confirm a synthetic district and freeze the first product catalog and source register.
2. Implement money and food quantities plus balanced journal entries.
3. Implement the literal purchase, consumption, and processing fixture.
4. Add reservations, cancellation, and duplicate command IDs.
5. Add ordered events and a complete replay reducer.
6. Persist commits and checkpoints. Inject a crash around settlement.
7. Expose one immutable scene snapshot and event projection.
8. Animate a resident along a recorded journey and open the purchase inspector.
9. Fork a subsidy treatment and export the paired difference.
10. Run the demonstrator end to end and record which acceptance gates remain.

These are build tasks, not work already completed by this planning package.

## Proposed labor budget

The rates below are hypothetical planning inputs in Canadian dollars. Replace them with actual internal costs or quotes before budgeting. A 16-week full-time role has 640 hours at 40 hours per week.

| Role | Hours | Assumed CAD per hour | Amount |
| --- | --- | --- | --- |
| Two engineers | 1,280 | 120 | CAD 153,600 |
| Half-time analyst | 320 | 100 | CAD 32,000 |
| Quarter-time 3D designer | 160 | 90 | CAD 14,400 |
| Domain and community review | 64 | 100 | CAD 6,400 |
| Total labor | 1,824 | | CAD 206,400 |
| Contingency, 20% | | | CAD 41,280 |
| Labor including contingency | | | CAD 247,680 |

The first two weeks account for approximately CAD 25,800 of the base labor under the same staffing proportions. That amount is included above. Founder-built or student work may spend less cash but still incurs time and review requirements.

Add an illustrative hosting allowance of CAD 500 monthly and an LLM experimentation allowance of CAD 300 monthly for six months, totaling CAD 4,800. Combined with contingency labor, the example envelope is CAD 252,480 before taxes, partner charges, special hardware, fieldwork, or real drone operations. This is a spending allowance, not current cloud or model pricing.

## LLM cost control

For configured rates per million tokens:

```text
estimated_CAD = FX_to_CAD * (
    input_tokens * input_rate / 1_000_000
    + output_tokens * output_rate / 1_000_000
    + other_billable_usage_and_fees
)
```

Reserve the maximum cost before dispatch and reconcile actual usage. Stop new requests if a ceiling would be exceeded. Include uncertain requests conservatively. Provider limits and token accounting must be checked when selecting an adapter.

A run's CAD 30 ceiling is independent of its 1,200-call maximum. Either can stop live decisions first. Ten runs at the ceiling exhaust the CAD 300 monthly example allowance. The 480-run screening study therefore defaults to rule-based agents. A fully live study needs a separate approved research budget and a defined sampling design.

Generated explanations can use templates for routine events. Reserve model calls for decisions or comparisons that add information. Evaluate quality before choosing a larger or more expensive model.

## Scope boundaries and dependencies

The prototype includes all four policy models, simple 3D actors, bounded LLM choice, replay, exports, and validation fixtures. Detailed interiors, character customization, social relationships, citywide populations, photorealism, and operational drone dispatch are later work.

Partner data, local price audits, actual school participation, facility yields, and externally reviewed behavior remain dependencies. Continue with clearly marked synthetic assumptions while access is pending. Do not convert missing data into invented facts to preserve the schedule.

## Conditions for a broader release

Before presenting the system as evidence for consequential policy choices, obtain independent review of the economic mechanisms, compatible observed-data calibration, held-out validation, documented sensitivities, and a clear interpretation of uncertainty.

A public demonstration can ship earlier if it identifies synthetic inputs and exploratory results visibly. The release checklist must state which gates passed and which claims remain unsupported. Publishing or hosting is a later explicit action, not part of this plan creation.
