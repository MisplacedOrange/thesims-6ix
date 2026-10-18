# The Sims 6ix: focused simulation plan

Updated October 18, 2026. This plan is limited to the current priorities: completing the Council flow, modeling bounded organization decisions, recording actual stakeholder evidence, and building a persistent simulation with traceable evidence. The [active roadmap](NEXT_STEPS.md) defines delivery gates and current status.

## Current implementation boundary

The browser shows a frozen downtown Toronto scene and replays a deterministic six-hour food-access scenario. The Python Council service supports exact Markdown revisions, scopes, typed plans, explicit review decisions, and matched traces for one hypothetical municipal food-site action. In the current working tree, the browser Council panel exposes proposal submission and revision inspection; scope, plan, decision, and run controls remain to be restored or redesigned. The current scenario is illustrative, and the world does not persist across days.

The food scenario has basic state for households, retailers, a supplier, schools, food-support sites, and a temporary municipal site. These are not general business agents. Their operating values are not evidence that a mapped organization is active or willing to participate. There is no actual consultation record workflow yet.

## Product goal

Use the Council workflow to turn a proposal into a sourced, human-reviewed simulation plan. Represent the organizations whose resources and services matter to that proposal, record actual stakeholder input separately from synthetic behavior, and follow outcomes through a persistent run. The Python service remains the authority for time, resources, and committed events; the browser displays and reviews those records. Simulated decisions do not authorize real City action or claim to speak for real organizations or people.

## First integrated proof

Start with the existing `establish_service_site` action unless scope review selects a better-supported proposal. Include the incumbent retailer, relevant supplier, hypothetical municipal operator, affected population groups, and responsible public authority only where they affect the proposal.

The proof should:

1. Preserve and version the submitted proposal, references, unknowns, and assumptions.
2. Create an impact and actor map: affected groups, resource-controlling organizations, responsible authorities, required evidence, likely business or access effects, and unresolved questions.
3. Record consultation and partner evidence as dated, source-linked records with geography, method, groups reached, consent limits, disagreements, and known representation gaps.
4. Let a reviewer define scope, choose a typed action, review assumptions and evidence, and explicitly approve, request revision, or reject the exact plan revision.
5. Run matched baseline and intervention scenarios from the same pinned initial state. The horizon must cover the proposal's relevant rollout and operating cycles; rollout dates and repeated daily schedules are separate concepts.
6. Report household access and distribution, organization activity and costs, public spending, service capacity, delivery or opening delays, and no-launch outcomes only where the model has supported measures.
7. Preserve event history and source, code, scenario, and random-seed identity so the result can be restarted, branched, and replayed.

## Organization decisions

Start with bounded operational decisions that have clear resource effects: supplier order acceptance and delivery timing; site inventory, hours, and service capacity; and authorized municipal funding or activation. Record each decision's actor, authority, evidence state, applicable limits, and committed consequences. Add staffing, rent, business margins, competition, or strategic price responses only when their mechanisms and inputs are supported. Use explicit sensitivity cases where values remain assumptions. Revenue alone does not establish business viability.

Use deterministic rules as the first organization policy. Department-style notes may explain constraints, but cannot approve a plan or spend resources. Autonomous LLM or reinforcement-learning decisions are outside this plan's active scope.

## Stakeholders and evidence

Use synthetic households to examine modeled outcomes across stated groups. Do not treat generated choices, dialogue, or expert-role notes as consultation or public opinion. Keep real resident, worker, business, community, and partner input in a separate evidence stream. Preserve consent and publication limits, contradictory views, and groups that were not reached. Report modeled effects and consultation evidence side by side without merging their meanings.

Pin every run to immutable source snapshots and record observation, publication, retrieval, and refresh-check dates separately. Label evidence as observed, announced, estimated, illustrative, or unknown. Missing operating status, inventory, prices, capacity, authority, cost, or consultation remains unknown until evidence or an explicit scenario assumption supplies it.

## Evaluation boundaries

Keep household spending, business receipts, procurement, wages, operating costs, grants, public cash outlay, and resource costs distinct. Report group counts and denominators, paired baseline/intervention differences, assumption sensitivity, and adverse or no-launch cases. Conservation, legal actions, idempotency, and replay establish implementation invariants; they do not establish calibration, causal effects, representativeness, or a Toronto forecast. Stronger empirical claims require compatible independent observations and held-out validation.

## Deferred scope

The existing 3D scene remains the presentation context. Citywide map expansion, new traffic or transit behavior, drone delivery, visual polish, additional food-policy demonstrations, a broad action catalog, autonomous department or company agents, LLM choices, reinforcement learning, and performance optimization are deferred unless required by the selected proposal. Detailed historical and implementation notes remain in the relevant subsystem documents; the [roadmap](NEXT_STEPS.md) controls active commitments.
