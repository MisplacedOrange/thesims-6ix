# Household behaviour

This package is the weeks 12–13 behaviour work for the neighbourhood food model. It builds legal choice offers, applies household knowledge, scores a rule baseline, selects the fixed LLM panel, and compares rule choices with generated choices.

It does not settle cash or food, store runs, render a scene, or call a model provider. `sim/core` is the economic authority. Person 2 owns the API, persistence, replay, UI, and the provider gateway.

The choice records are draft `0-draft`, marked `DRAFT_JOINT_REVIEW_PERSON_2`. See [CHOICE_FORMAT.md](CHOICE_FORMAT.md).

## What a caller does

1. Core fills a `DecisionContext` at a decision barrier. Prices are integer cents, masses are integer grams, and times are integer seconds.
2. `build_choice_offer` drops anything the household is not allowed to know and keeps only legal options, including delay and no purchase.
3. `resolve_barrier` either scores the rule utility or asks `ChoiceGateway` for the predeclared subset.
4. Core settles the returned option id. If cash or stock no longer covers it, core asks `rule_fallback_receipt` and does not invent a new provider call.
5. Core allocates contested lots in `admission_order`. That order is a seeded rank. It is not household-id order and it is not provider arrival order.

A rule study leaves `gateway_enabled` false. `DisabledGateway` raises if something dispatches anyway. Live studies with the gateway disabled still return a legal rule choice and record `gateway_disabled`.

## Rule score

```text
utility = preference_fit + habit_value + known_quality
          - price_sensitivity_per_dollar * (cents / 100)
          - time_sensitivity_per_minute * (seconds / 60)
          - stockout_penalty - uncertainty_penalty
          + seeded_choice_noise
```

`price_sensitivity_per_dollar` is utility per Canadian dollar. It is not applied to raw cents. Noise uses stream algorithm `sha256-unit-v1`, keyed by seed, household, option, day, and purpose `choice_noise`. The policy is not part of the key. Equal scores break toward the smaller option id.

Coefficients are illustrative. The October 17, 2026 context snapshot is not a calibration set. Income does not change the price coefficient unless a study supplies an explicit table.

A trip is at least one second. Basket grams that do not divide the reference household size use a largest-remainder split. A school-meal option has a household payment of zero. A drone option exists only when the scenario route record says the corridor is eligible. That flag is a modeling condition, not flight permission.

## Knowledge and panel

Default knowledge is the household's own cash, pantry, time, habits, visible events, and stores it has already learned or that are publicly known. Other balances and tomorrow's stock stay off the offer unless `knowledge_grants` names `other_balances` or `tomorrow_stock`. Granted facts are labeled `scenario_grant`.

The focal panel is chosen before the run, at most 40 households, stratified with a guaranteed seat for each occupied stratum when the seat count allows. Each barrier then admits at most four households by a rotation of day and opportunity. Routine shopping stays on the rule. One household can be dispatched at most once per simulated day. The run also stops at 1,200 attempts or CAD 30, whichever binds first. A price that cannot bound a positive charge cannot dispatch. There are no automatic retries.

## Latent proxies

`update_latent` moves illustrative stress, trust, and satisfaction proxies from shortfall, unpaid essentials, time overrun, fulfillment, and service gap. The values are clamped to [0, 1]. They are not clinical measures and they are not survey results.

## ODD sketch for this submodel

ODD here is a description of this submodel, not a validation certificate.

- Purpose: choose a legal household action and record whether it came from the rule, a bounded provider call, a frozen receipt, or a fallback.
- Entities: households, known stores, school meals, delivery modes, and the fixed focal panel.
- Process: filter knowledge, build legal options, score the rule, dispatch at most four predeclared live choices, then fall back to the rule.
- Initialization: coefficients, panel seed, and gateway flag come from the study. They are fixed before the first barrier.
- Inputs: a core snapshot in cents, grams, and seconds, plus any scenario knowledge grants.
- Submodels: discrete-choice score, latent strain update, and the descriptive behaviour comparison.

## Tests

From the repository root:

```bash
python -m pytest sim/behavior/tests sim/experiments/tests
```

Determinism tests repeat offers, receipts, panel draws, and seeded noise. Gateway-disabled tests use a gateway object that raises if it is called.

## Integration assumptions

These are the assumptions `sim/core` and Person 2 need to share. They are also listed on the pull request.

1. Core constructs `DecisionContext` at each decision barrier and is the only writer of cash, lots, reservations, and journeys. This package never posts a journal.
2. Shelf quotes are one row per store and product, already net of reservations. Prices are integer cents per catalog unit. Grams and seconds are integers. A non-integer is rejected.
3. Mobility fills `RouteInfo.total_seconds` for the whole collection, including access, waiting, service, and return. Behaviour rounds a positive trip up to at least one second and drops routes the household cannot use.
4. An offer is feasible at observation time only. Core checks the option again at settlement. An unaffordable or out-of-stock option becomes `rule_fallback_receipt` with reason `unaffordable`.
5. Core allocates contested stock in `BarrierResolution.admission_order`. Response arrival order and raw household-id order are not admission rules.
6. Named streams are `sha256-unit-v1`. Keys contain seed, actor, day, purpose, and draw index. They do not contain the policy. Core should use different purpose strings for weather and income so choice noise does not consume those draws.
7. The focal panel is fixed from the study roster and seed before the run. Camera, inspector, and UI selection do not change it. Core passes the same `FocalPanel` into every barrier.
8. Core passes `used_live_today` and `attempts_used`, and the same `ChargeReservation` ledger, across barriers in one run. This package reserves a maximum and does not release it after fallback. Person 2 persists and reconciles the reservation.
9. Person 2 implements `ChoiceGateway.dispatch_barrier`, starts the whole batch together, enforces the barrier deadline, and does not retry. Behaviour maps status `timeout` to fallback reason `late`.
10. A missing token price, or a price that does not bound a positive CAD amount, disables live dispatch with reason `unbounded_charges`. The CAD 30 ceiling, 1,200 attempt cap, 1,500 input tokens, 200 output tokens, and four live choices per barrier are hard caps in this package.
11. Gateway-disabled and rule-policy runs must not call the provider. `llm_dispatch_count` stays zero. `not_selected_for_live_barrier` is a rule outcome, not a timeout.
12. Replay passes `RecordedChoice` with the original observation hash. A hash mismatch or an option that is no longer legal is reason `stale`, and the rule choice is used. A receipt from another policy is not reused.
13. Household ids use the `hh-` prefix and visible event ids use the `evt-` prefix so the grounding check can recognize them. Generated text is untrusted. Person 2 shows `synthetic_label` and does not execute explanation text.
14. The draft schema version is `0-draft`. Person 2 should not treat stored receipts as a stable replay format until the joint review changes this status.
15. Subgroup fields on household results are income band, household size, area, mobility, and school eligibility. Households stay unweighted.
16. Outcome values stay in the units the executor reports. Basket costs in this package's own tests are cents. Nothing here divides cents by 100 except the utility score.
