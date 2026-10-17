# Choice offer and receipt format

Status: DRAFT_JOINT_REVIEW_PERSON_2

Schema version: 0-draft

This file is the draft contract for backend/frontend integration review. It is not a stable wire format. `sim/behavior` owns the economic meaning of these records. Transport, charge persistence, prompt assembly, and durable replay require an explicitly assigned backend owner. `sim/core` owns settlement and must validate the chosen option again at commit time.

Schema ids:

| Record | Schema id |
| --- | --- |
| Offer | `sim6ix.choice_offer` |
| Gateway observation | `sim6ix.choice_observation` |
| Receipt | `sim6ix.choice_receipt` |

Every offer and receipt carries `review_status = DRAFT_JOINT_REVIEW_PERSON_2` and `schema_version = 0-draft`.

## Gateway observation

The observation is the only payload sent to the provider. Its SHA-256 canonical JSON is `observation_hash`. Canonical JSON sorts keys, uses compact separators, and writes scores as `.12g` strings. Money stays in integer cents.

Fields:

- `decision_id`, `household_id`, `revision`, `sim_second`, `day_index`, `opportunity`
- `known_facts`: facts the knowledge rules released
- `recent_event_ids`: events the household may cite
- `options`: legal options, each with `option_id`, `kind`, `store_id`, basket lines (`product_id`, `grams`, `price_cents`), `expected_payment_cents`, `total_seconds`, score parts, and attributes

The observation does not include other households' balances, tomorrow's stock, the focal-panel schedule, the camera, or provider credentials. A scenario grant can add a fact with `source = scenario_grant`.

## Gateway request and response

Person 2 implements `ChoiceGateway.dispatch_barrier`. One call contains every request that was predeclared for that barrier. The deadline covers the whole barrier and is at most 10 seconds. There are no automatic retries.

Request fields beyond the observation: `max_input_tokens` (at most 1,500), `max_output_tokens` (at most 200), and `reserved_charge_cad`.

Response fields: `decision_id`, `option_id`, `explanation`, `status` (`ok`, `refused`, `invalid`, `timeout`, `error`, `unaffordable`), `prompt_version`, `model_configuration`, `raw_response`, token counts, `actual_charge_cad`, `latency_seconds`, and the revision the response was built against.

`explanation` and `raw_response` are untrusted display data. They are not commands and they do not post journals.

## Receipt

`origin` is `rule`, `llm`, `recorded`, or `fallback`.

`selection_reason` records why the household was or was not dispatched. Households outside the predeclared four-household subset use `not_selected_for_live_barrier`. That reason is not a provider timeout. Timeouts use fallback reason `late`.

Fallback reasons for a planned live choice that did not commit an LLM option include `gateway_disabled`, `unbounded_charges`, `budget_exhausted`, `attempt_ceiling`, `missing`, `refused`, `invalid`, `late`, `stale`, and `unaffordable`.

`rule_option_id` is the deterministic rule choice for the same offer, including when the committed option came from the provider. `utility` is the score of the committed option under the rule formula, with seeded noise.

`synthetic_label` is either `rule explanation from the simulation` or `generated from the simulation`. Person 2's inspector shows that label. Generated text that cites an unknown event, another household id, or a cent amount that is not on the offer is replaced by the rule explanation.

## Open questions for Person 2

- Confirm the canonical JSON and hash before any receipt is stored as replay input.
- Confirm where the charge reservation is persisted. Behaviour calls `ChargeReservation.reserve_maximum` and does not release it after a fallback.
- Confirm the provider status strings above. Behaviour maps `timeout` to fallback reason `late`.
- Synthetic ids are recognized by the grounding check when household ids use the `hh-` prefix and event ids use the `evt-` prefix.
