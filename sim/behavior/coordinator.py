"""Resolve one decision barrier.

Rule runs never call the gateway. A live study with the gateway disabled still
returns a legal rule choice and records ``gateway_disabled``. Households outside
the predeclared four-household subset record ``not_selected_for_live_barrier``
and are not described as timeouts.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.behavior.adapters import ChoiceGateway
from sim.behavior.budget import (
    MAX_ATTEMPTS,
    MAX_INPUT_TOKENS,
    MAX_OUTPUT_TOKENS,
    RUN_BUDGET_CAD,
    ChargeReservation,
    TokenPrice,
    estimate_max_request_cad,
)
from sim.behavior.determinism import STREAM_ALGORITHM, admission_rank
from sim.behavior.draft import (
    CHOICE_FORMAT_STATUS,
    LABEL_GENERATED,
    LABEL_RULE,
    RECEIPT_SCHEMA_ID,
    SCHEMA_VERSION,
    ChoiceOffer,
    ChoiceReceipt,
    FeasibleOption,
    GatewayRequest,
    GatewayResponse,
    ORIGIN_FALLBACK,
    ORIGIN_LLM,
    ORIGIN_RECORDED,
    ORIGIN_RULE,
)
from sim.behavior.errors import BehaviorError
from sim.behavior.explain import cited_event_ids, ground_explanation, rule_explanation
from sim.behavior.offers import build_choice_offer
from sim.behavior.panel import MAX_LIVE_PER_BARRIER, FocalPanel, live_rotation_order
from sim.behavior.snapshot import LIVE_OPPORTUNITIES, DecisionContext
from sim.behavior.utility import UtilityCoefficients, choose_rule, utility_of, validate_coefficients

POLICY_RULES = "rules"
POLICY_LIVE = "live_llm"
POLICY_FROZEN = "frozen_receipts"
POLICIES = (POLICY_RULES, POLICY_LIVE, POLICY_FROZEN)

REASON_RULE_POLICY = "rule_policy"
REASON_NOT_LIVE = "not_a_live_opportunity"
REASON_NOT_PANEL = "not_in_focal_panel"
REASON_NOT_SELECTED = "not_selected_for_live_barrier"
REASON_DAILY_CAP = "daily_household_cap"
REASON_GATEWAY_DISABLED = "gateway_disabled"
REASON_UNBOUNDED = "unbounded_charges"
REASON_BUDGET = "budget_exhausted"
REASON_ATTEMPT_CAP = "attempt_ceiling"
REASON_DISPATCHED = "dispatched"
REASON_FROZEN = "frozen_receipt"
REASON_MISSING = "missing"
REASON_REFUSED = "refused"
REASON_INVALID = "invalid"
REASON_LATE = "late"
REASON_STALE = "stale"
REASON_UNAFFORDABLE = "unaffordable"

_FALLBACK_FROM_STATUS = {
    "timeout": REASON_LATE,
    "refused": REASON_REFUSED,
    "invalid": REASON_INVALID,
    "error": REASON_MISSING,
    "unaffordable": REASON_UNAFFORDABLE,
    "missing": REASON_MISSING,
}


@dataclass(frozen=True)
class BehaviorConfig:
    agent_policy: str = POLICY_RULES
    gateway_enabled: bool = False
    max_live_per_barrier: int = MAX_LIVE_PER_BARRIER
    max_attempts: int = MAX_ATTEMPTS
    max_input_tokens: int = MAX_INPUT_TOKENS
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    barrier_deadline_seconds: float = 10.0
    run_budget_cad: object = RUN_BUDGET_CAD
    automatic_retries: int = 0
    coefficients: UtilityCoefficients = UtilityCoefficients()
    token_price: TokenPrice | None = None


@dataclass(frozen=True)
class RecordedChoice:
    decision_id: str
    option_id: str
    observation_hash: str
    explanation: str | None = None
    prompt_version: str | None = None
    model_configuration: str | None = None


@dataclass(frozen=True)
class BarrierResolution:
    receipts: tuple[ChoiceReceipt, ...]
    admission_order: tuple[str, ...]
    dispatched_decision_ids: tuple[str, ...]
    gateway_dispatch_calls: int
    attempts_consumed: int


def validate_config(config: BehaviorConfig) -> None:
    if config.agent_policy not in POLICIES:
        raise BehaviorError(f"unknown agent policy {config.agent_policy}")
    if config.automatic_retries != 0:
        raise BehaviorError("automatic retries are disabled")
    if config.max_live_per_barrier < 0 or config.max_live_per_barrier > MAX_LIVE_PER_BARRIER:
        raise BehaviorError("a barrier admits at most 4 live choices")
    if config.max_attempts < 0 or config.max_attempts > MAX_ATTEMPTS:
        raise BehaviorError("live attempts cannot exceed 1200")
    if config.max_input_tokens < 1 or config.max_input_tokens > MAX_INPUT_TOKENS:
        raise BehaviorError("input token cap cannot exceed 1500")
    if config.max_output_tokens < 1 or config.max_output_tokens > MAX_OUTPUT_TOKENS:
        raise BehaviorError("output token cap cannot exceed 200")
    if config.barrier_deadline_seconds <= 0 or config.barrier_deadline_seconds > 10:
        raise BehaviorError("the barrier deadline cannot exceed 10 seconds")
    from decimal import Decimal

    budget = config.run_budget_cad if isinstance(config.run_budget_cad, Decimal) else Decimal(str(config.run_budget_cad))
    if budget <= 0 or budget > RUN_BUDGET_CAD:
        raise BehaviorError("run budget cannot exceed CAD 30")
    validate_coefficients(config.coefficients)


def resolve_barrier(
    contexts: tuple[DecisionContext, ...] | list[DecisionContext],
    *,
    config: BehaviorConfig,
    panel: FocalPanel,
    master_seed: int,
    gateway: ChoiceGateway | None = None,
    budget: ChargeReservation | None = None,
    recorded: tuple[RecordedChoice, ...] = (),
    used_live_today: frozenset[str] = frozenset(),
    attempts_used: int = 0,
) -> BarrierResolution:
    validate_config(config)
    if type(master_seed) is not int or master_seed < 0:
        raise BehaviorError("master_seed must be a non-negative int")
    if type(attempts_used) is not int or attempts_used < 0:
        raise BehaviorError("attempts_used must be a non-negative int")
    contexts = tuple(contexts)
    _unique_contexts(contexts)
    offers = tuple(build_choice_offer(ctx, config.coefficients) for ctx in contexts)
    by_household = {offer.household_id: offer for offer in offers}
    plan = _selection_plan(
        offers,
        config=config,
        panel=panel,
        budget=budget,
        used_live_today=used_live_today,
        attempts_used=attempts_used,
    )
    responses: dict[str, GatewayResponse | None] = {}
    dispatch_calls = 0
    if plan.dispatched:
        if gateway is None or not config.gateway_enabled:
            raise BehaviorError("dispatched choices require an enabled gateway")
        requests = tuple(_request(by_household[household_id], config, plan.reserved_cad) for household_id in plan.dispatched)
        batch = gateway.dispatch_barrier(requests, deadline_seconds=config.barrier_deadline_seconds)
        dispatch_calls = 1
        responses = _align(batch, requests)
    recorded_by_id = {item.decision_id: item for item in recorded}
    if len(recorded_by_id) != len(recorded):
        raise BehaviorError("duplicate recorded decision id")
    receipts = tuple(
        _receipt_for(
            offer,
            config=config,
            master_seed=master_seed,
            selection_reason=plan.reasons[offer.household_id],
            response=responses.get(offer.household_id),
            recorded=recorded_by_id.get(offer.decision_id),
            reserved_cad=plan.reserved_cad if offer.household_id in plan.dispatched else None,
        )
        for offer in offers
    )
    return BarrierResolution(
        receipts=receipts,
        admission_order=_admission_order(offers, master_seed),
        dispatched_decision_ids=tuple(by_household[household_id].decision_id for household_id in plan.dispatched),
        gateway_dispatch_calls=dispatch_calls,
        attempts_consumed=len(plan.dispatched),
    )


def rule_fallback_receipt(
    offer: ChoiceOffer,
    *,
    reason: str,
    master_seed: int,
    coefficients: UtilityCoefficients | None = None,
    selection_reason: str = REASON_UNAFFORDABLE,
) -> ChoiceReceipt:
    """Build the deterministic rule receipt core uses when settlement rejects an option."""

    coeffs = coefficients or UtilityCoefficients()
    return _rule_receipt(
        offer,
        master_seed=master_seed,
        coefficients=coeffs,
        origin=ORIGIN_FALLBACK,
        selection_reason=selection_reason,
        fallback_reason=reason,
        reserved_cad=None,
    )


@dataclass(frozen=True)
class _Plan:
    reasons: dict[str, str]
    dispatched: tuple[str, ...]
    reserved_cad: str | None


def _selection_plan(
    offers: tuple[ChoiceOffer, ...],
    *,
    config: BehaviorConfig,
    panel: FocalPanel,
    budget: ChargeReservation | None,
    used_live_today: frozenset[str],
    attempts_used: int,
) -> _Plan:
    reasons = {offer.household_id: REASON_RULE_POLICY for offer in offers}
    if config.agent_policy == POLICY_FROZEN:
        return _Plan({offer.household_id: REASON_FROZEN for offer in offers}, (), None)
    if config.agent_policy != POLICY_LIVE:
        return _Plan(reasons, (), None)

    ordered = _barrier_order(offers, panel, used_live_today)
    for offer in offers:
        if offer.opportunity not in LIVE_OPPORTUNITIES:
            reasons[offer.household_id] = REASON_NOT_LIVE
        elif offer.household_id not in panel.ids:
            reasons[offer.household_id] = REASON_NOT_PANEL
        elif offer.household_id in used_live_today:
            reasons[offer.household_id] = REASON_DAILY_CAP
    proposed = ordered[: config.max_live_per_barrier]
    for household_id in ordered[config.max_live_per_barrier :]:
        reasons[household_id] = REASON_NOT_SELECTED
    for household_id in proposed:
        reasons[household_id] = REASON_DISPATCHED

    if not config.gateway_enabled:
        for household_id in proposed:
            reasons[household_id] = REASON_GATEWAY_DISABLED
        return _Plan(reasons, (), None)
    if config.token_price is None:
        for household_id in proposed:
            reasons[household_id] = REASON_UNBOUNDED
        return _Plan(reasons, (), None)

    if budget is None:
        raise BehaviorError("live dispatch requires a charge reservation ledger")
    cost = estimate_max_request_cad(
        config.token_price,
        input_tokens=config.max_input_tokens,
        output_tokens=config.max_output_tokens,
    )
    room = config.max_attempts - attempts_used
    admitted = proposed[: max(room, 0)]
    for household_id in proposed[max(room, 0) :]:
        reasons[household_id] = REASON_ATTEMPT_CAP
    remaining = budget.remaining_cad()
    affordable = int(remaining // cost)
    dispatched: list[str] = []
    for index, household_id in enumerate(admitted):
        if index >= affordable:
            reasons[household_id] = REASON_BUDGET
            continue
        offer = next(offer for offer in offers if offer.household_id == household_id)
        if budget is not None and not budget.reserve_maximum(offer.decision_id, cost):
            reasons[household_id] = REASON_BUDGET
            continue
        dispatched.append(household_id)
        reasons[household_id] = REASON_DISPATCHED
    reserved = format(cost, "f") if dispatched else None
    return _Plan(reasons, tuple(dispatched), reserved)


def _barrier_order(
    offers: tuple[ChoiceOffer, ...],
    panel: FocalPanel,
    blocked: frozenset[str],
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for opportunity in LIVE_OPPORTUNITIES:
        facing = tuple(offer.household_id for offer in offers if offer.opportunity == opportunity)
        subset = live_rotation_order(
            panel,
            day_index=offers[0].day_index if offers else 0,
            opportunity=opportunity,
            candidates=facing,
            blocked=blocked,
        )
        for household_id in subset:
            if household_id not in seen:
                ordered.append(household_id)
                seen.add(household_id)
    return tuple(ordered)


def _receipt_for(
    offer: ChoiceOffer,
    *,
    config: BehaviorConfig,
    master_seed: int,
    selection_reason: str,
    response: GatewayResponse | None,
    recorded: RecordedChoice | None,
    reserved_cad: str | None,
) -> ChoiceReceipt:
    if config.agent_policy == POLICY_FROZEN:
        return _from_recorded(offer, recorded, master_seed, config.coefficients)
    if selection_reason == REASON_DISPATCHED:
        return _from_gateway(offer, response, master_seed, config, reserved_cad)
    fallback = selection_reason in {REASON_GATEWAY_DISABLED, REASON_UNBOUNDED, REASON_BUDGET, REASON_ATTEMPT_CAP}
    return _rule_receipt(
        offer,
        master_seed=master_seed,
        coefficients=config.coefficients,
        origin=ORIGIN_FALLBACK if fallback else ORIGIN_RULE,
        selection_reason=selection_reason,
        fallback_reason=selection_reason if fallback else None,
        reserved_cad=None,
    )


def _from_recorded(
    offer: ChoiceOffer,
    recorded: RecordedChoice | None,
    master_seed: int,
    coefficients: UtilityCoefficients,
) -> ChoiceReceipt:
    legal_ids = {option.option_id for option in offer.options}
    if (
        recorded is None
        or recorded.observation_hash != offer.gateway_observation().content_hash()
        or recorded.option_id not in legal_ids
    ):
        return _rule_receipt(
            offer,
            master_seed=master_seed,
            coefficients=coefficients,
            origin=ORIGIN_FALLBACK,
            selection_reason=REASON_FROZEN,
            fallback_reason=REASON_STALE,
            reserved_cad=None,
        )
    option = _option(offer, recorded.option_id)
    rule_id, utility = _scored_choice(offer, option.option_id, master_seed, coefficients)
    explanation = recorded.explanation or rule_explanation(offer, option)
    return _base_receipt(
        offer,
        option_id=recorded.option_id,
        rule_option_id=rule_id,
        origin=ORIGIN_RECORDED,
        selection_reason=REASON_FROZEN,
        fallback_reason=None,
        explanation=explanation,
        explanation_origin="recorded",
        synthetic_label=LABEL_GENERATED if recorded.explanation else LABEL_RULE,
        cited=cited_event_ids(explanation, offer),
        prompt_version=recorded.prompt_version,
        model_configuration=recorded.model_configuration,
        raw_response=None,
        input_tokens=0,
        output_tokens=0,
        reserved_cad=None,
        actual_cad=None,
        latency=None,
        utility=utility,
    )


def _from_gateway(
    offer: ChoiceOffer,
    response: GatewayResponse | None,
    master_seed: int,
    config: BehaviorConfig,
    reserved_cad: str | None,
) -> ChoiceReceipt:
    if response is None:
        return _rule_receipt(
            offer,
            master_seed=master_seed,
            coefficients=config.coefficients,
            origin=ORIGIN_FALLBACK,
            selection_reason=REASON_DISPATCHED,
            fallback_reason=REASON_MISSING,
            reserved_cad=reserved_cad,
        )
    status_reason = _FALLBACK_FROM_STATUS.get(response.status)
    revision = offer.revision if response.revision is None else response.revision
    legal = response.option_id in {option.option_id for option in offer.options}
    over_cap = (
        response.input_tokens > config.max_input_tokens or response.output_tokens > config.max_output_tokens
    )
    if (
        response.status != "ok"
        or status_reason is not None
        or not legal
        or revision != offer.revision
        or not response.prompt_version
        or not response.model_configuration
        or over_cap
    ):
        if response.status == "ok" and revision != offer.revision:
            reason = REASON_STALE
        elif response.status == "ok" and not legal:
            reason = REASON_INVALID
        elif response.status == "ok" and (not response.prompt_version or not response.model_configuration or over_cap):
            reason = REASON_INVALID
        else:
            reason = status_reason or REASON_INVALID
        return _rule_receipt(
            offer,
            master_seed=master_seed,
            coefficients=config.coefficients,
            origin=ORIGIN_FALLBACK,
            selection_reason=REASON_DISPATCHED,
            fallback_reason=reason,
            reserved_cad=reserved_cad,
            response=response,
        )
    option = _option(offer, response.option_id or "")
    rule_id, utility = _scored_choice(offer, option.option_id, master_seed, config.coefficients)
    explanation, explanation_origin, cited = ground_explanation(response.explanation, offer, option)
    return _base_receipt(
        offer,
        option_id=option.option_id,
        rule_option_id=rule_id,
        origin=ORIGIN_LLM,
        selection_reason=REASON_DISPATCHED,
        fallback_reason=None,
        explanation=explanation,
        explanation_origin=explanation_origin,
        synthetic_label=LABEL_GENERATED if explanation_origin == "llm_grounded" else LABEL_RULE,
        cited=cited,
        prompt_version=response.prompt_version,
        model_configuration=response.model_configuration,
        raw_response=response.raw_response,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        reserved_cad=reserved_cad,
        actual_cad=response.actual_charge_cad,
        latency=response.latency_seconds,
        utility=utility,
    )


def _rule_receipt(
    offer: ChoiceOffer,
    *,
    master_seed: int,
    coefficients: UtilityCoefficients,
    origin: str,
    selection_reason: str,
    fallback_reason: str | None,
    reserved_cad: str | None,
    response: GatewayResponse | None = None,
) -> ChoiceReceipt:
    rule_id, utility = choose_rule(
        offer.options,
        master_seed=master_seed,
        household_id=offer.household_id,
        day_index=offer.day_index,
        income_band=offer.stratum,
        coefficients=coefficients,
    )
    option = _option(offer, rule_id)
    explanation = rule_explanation(offer, option)
    return _base_receipt(
        offer,
        option_id=rule_id,
        rule_option_id=rule_id,
        origin=origin,
        selection_reason=selection_reason,
        fallback_reason=fallback_reason,
        explanation=explanation,
        explanation_origin="rule_template",
        synthetic_label=LABEL_RULE,
        cited=cited_event_ids(explanation, offer),
        prompt_version=None if response is None else response.prompt_version or None,
        model_configuration=None if response is None else response.model_configuration or None,
        raw_response=None if response is None else response.raw_response or None,
        input_tokens=0 if response is None else response.input_tokens,
        output_tokens=0 if response is None else response.output_tokens,
        reserved_cad=reserved_cad,
        actual_cad=None if response is None else response.actual_charge_cad or None,
        latency=None if response is None else response.latency_seconds,
        utility=utility,
    )


def _base_receipt(offer: ChoiceOffer, **kwargs: object) -> ChoiceReceipt:
    return ChoiceReceipt(
        schema_id=RECEIPT_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        review_status=CHOICE_FORMAT_STATUS,
        decision_id=offer.decision_id,
        household_id=offer.household_id,
        revision=offer.revision,
        day_index=offer.day_index,
        stratum=offer.stratum,
        opportunity=offer.opportunity,
        option_id=str(kwargs["option_id"]),
        rule_option_id=str(kwargs["rule_option_id"]),
        origin=str(kwargs["origin"]),
        selection_reason=str(kwargs["selection_reason"]),
        fallback_reason=kwargs["fallback_reason"] if kwargs["fallback_reason"] is None else str(kwargs["fallback_reason"]),
        observation_hash=offer.gateway_observation().content_hash(),
        prompt_version=kwargs["prompt_version"] if kwargs["prompt_version"] is None else str(kwargs["prompt_version"]),
        model_configuration=(
            kwargs["model_configuration"] if kwargs["model_configuration"] is None else str(kwargs["model_configuration"])
        ),
        raw_response=kwargs["raw_response"] if kwargs["raw_response"] is None else str(kwargs["raw_response"]),
        explanation=str(kwargs["explanation"]),
        explanation_origin=str(kwargs["explanation_origin"]),
        synthetic_label=str(kwargs["synthetic_label"]),
        cited_event_ids=tuple(kwargs["cited"]),  # type: ignore[arg-type]
        input_tokens=int(kwargs["input_tokens"]),  # type: ignore[arg-type]
        output_tokens=int(kwargs["output_tokens"]),  # type: ignore[arg-type]
        reserved_charge_cad=kwargs["reserved_cad"] if kwargs["reserved_cad"] is None else str(kwargs["reserved_cad"]),
        actual_charge_cad=kwargs["actual_cad"] if kwargs["actual_cad"] is None else str(kwargs["actual_cad"]),
        latency_seconds=kwargs["latency"] if kwargs["latency"] is None else float(kwargs["latency"]),  # type: ignore[arg-type]
        utility=float(kwargs["utility"]),  # type: ignore[arg-type]
        stream_algorithm=STREAM_ALGORITHM,
        legal_at_observation=True,
    )


def _request(offer: ChoiceOffer, config: BehaviorConfig, reserved_cad: str | None) -> GatewayRequest:
    return GatewayRequest(
        observation=offer.gateway_observation(),
        max_input_tokens=config.max_input_tokens,
        max_output_tokens=config.max_output_tokens,
        reserved_charge_cad=reserved_cad or "0",
    )


def _align(
    batch: tuple[GatewayResponse, ...],
    requests: tuple[GatewayRequest, ...],
) -> dict[str, GatewayResponse | None]:
    by_decision: dict[str, GatewayResponse] = {}
    for response in batch:
        if response.decision_id in by_decision:
            raise BehaviorError("duplicate gateway response")
        by_decision[response.decision_id] = response
    aligned: dict[str, GatewayResponse | None] = {}
    for request in requests:
        aligned[request.observation.household_id] = by_decision.get(request.observation.decision_id)
    return aligned


def _admission_order(offers: tuple[ChoiceOffer, ...], master_seed: int) -> tuple[str, ...]:
    ranked = sorted(
        offers,
        key=lambda offer: (
            admission_rank(
                master_seed,
                household_id=offer.household_id,
                day=offer.day_index,
                opportunity=offer.opportunity,
            ),
            offer.household_id,
        ),
    )
    return tuple(offer.household_id for offer in ranked)


def _scored_choice(
    offer: ChoiceOffer,
    option_id: str,
    master_seed: int,
    coefficients: UtilityCoefficients,
) -> tuple[str, float]:
    rule_id, _ = choose_rule(
        offer.options,
        master_seed=master_seed,
        household_id=offer.household_id,
        day_index=offer.day_index,
        income_band=offer.stratum,
        coefficients=coefficients,
    )
    utility = utility_of(
        _option(offer, option_id),
        master_seed=master_seed,
        household_id=offer.household_id,
        day_index=offer.day_index,
        income_band=offer.stratum,
        coefficients=coefficients,
    )
    return rule_id, utility


def _option(offer: ChoiceOffer, option_id: str) -> FeasibleOption:
    for option in offer.options:
        if option.option_id == option_id:
            return option
    raise BehaviorError(f"option {option_id} is not on the offer")


def _unique_contexts(contexts: tuple[DecisionContext, ...]) -> None:
    decisions = [ctx.decision_id for ctx in contexts]
    households = [ctx.household.household_id for ctx in contexts]
    if len(decisions) != len(set(decisions)) or len(households) != len(set(households)):
        raise BehaviorError("a barrier has one context per household and decision")
    days = {ctx.day_index for ctx in contexts}
    if len(days) > 1:
        raise BehaviorError("a barrier is a single simulation day")

