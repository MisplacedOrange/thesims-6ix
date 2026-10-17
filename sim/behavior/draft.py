"""Draft choice-offer and choice-receipt records.

Status: DRAFT_JOINT_REVIEW_PERSON_2
Schema version: 0-draft

Person 2 owns transport, charge persistence, and replay. This module owns the
economic meaning of an offer and the receipt fields the gateway must return.
Do not treat this schema as a stable wire format until that joint review lands.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.behavior.canonical import canon_float, observation_hash

CHOICE_FORMAT_STATUS = "DRAFT_JOINT_REVIEW_PERSON_2"
SCHEMA_VERSION = "0-draft"
OFFER_SCHEMA_ID = "sim6ix.choice_offer"
RECEIPT_SCHEMA_ID = "sim6ix.choice_receipt"
OBSERVATION_SCHEMA_ID = "sim6ix.choice_observation"

ORIGIN_RULE = "rule"
ORIGIN_LLM = "llm"
ORIGIN_RECORDED = "recorded"
ORIGIN_FALLBACK = "fallback"
ORIGINS = (ORIGIN_RULE, ORIGIN_LLM, ORIGIN_RECORDED, ORIGIN_FALLBACK)

EXPLANATION_RULE = "rule_template"
EXPLANATION_GROUNDED = "llm_grounded"
EXPLANATION_REPLACED = "llm_replaced_ungrounded"

LABEL_RULE = "rule explanation from the simulation"
LABEL_GENERATED = "generated from the simulation"


@dataclass(frozen=True)
class ObservedFact:
    fact_id: str
    kind: str
    attributes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BasketLine:
    product_id: str
    grams: int
    price_cents: int


@dataclass(frozen=True)
class FeasibleOption:
    """One legal action at observation time.

    Feasibility here is not a settlement guarantee. Core validates the option
    again when the purchase is committed.
    """

    option_id: str
    kind: str
    store_id: str | None
    lines: tuple[BasketLine, ...]
    expected_payment_cents: int
    total_seconds: int
    preference_fit: float
    habit_value: float
    known_quality: float
    stockout_penalty: float
    uncertainty_penalty: float
    attributes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ChoiceOffer:
    schema_id: str
    schema_version: str
    review_status: str
    decision_id: str
    household_id: str
    revision: int
    sim_second: int
    day_index: int
    opportunity: str
    stratum: str
    known_facts: tuple[ObservedFact, ...]
    recent_event_ids: tuple[str, ...]
    options: tuple[FeasibleOption, ...]

    def gateway_observation(self) -> GatewayObservation:
        return GatewayObservation(
            schema_id=OBSERVATION_SCHEMA_ID,
            schema_version=self.schema_version,
            decision_id=self.decision_id,
            household_id=self.household_id,
            revision=self.revision,
            sim_second=self.sim_second,
            day_index=self.day_index,
            opportunity=self.opportunity,
            known_facts=self.known_facts,
            recent_event_ids=self.recent_event_ids,
            options=self.options,
        )


@dataclass(frozen=True)
class GatewayObservation:
    schema_id: str
    schema_version: str
    decision_id: str
    household_id: str
    revision: int
    sim_second: int
    day_index: int
    opportunity: str
    known_facts: tuple[ObservedFact, ...]
    recent_event_ids: tuple[str, ...]
    options: tuple[FeasibleOption, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "household_id": self.household_id,
            "revision": self.revision,
            "sim_second": self.sim_second,
            "day_index": self.day_index,
            "opportunity": self.opportunity,
            "known_facts": [_fact_payload(fact) for fact in self.known_facts],
            "recent_event_ids": list(self.recent_event_ids),
            "options": [_option_payload(option) for option in self.options],
        }

    def content_hash(self) -> str:
        return observation_hash(self.to_payload())


@dataclass(frozen=True)
class GatewayRequest:
    observation: GatewayObservation
    max_input_tokens: int
    max_output_tokens: int
    reserved_charge_cad: str

    def to_payload(self) -> dict[str, object]:
        return {
            "observation": self.observation.to_payload(),
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "reserved_charge_cad": self.reserved_charge_cad,
        }


@dataclass(frozen=True)
class GatewayResponse:
    """What Person 2's gateway returns for one dispatched observation.

    ``raw_response`` and ``explanation`` are untrusted text. They never become
    a ledger posting. ``status`` is one of ``ok``, ``refused``, ``invalid``,
    ``timeout``, ``error``, or ``unaffordable``.
    """

    decision_id: str
    option_id: str | None
    explanation: str | None
    status: str
    prompt_version: str
    model_configuration: str
    raw_response: str
    input_tokens: int
    output_tokens: int
    actual_charge_cad: str
    latency_seconds: float
    revision: int | None = None


@dataclass(frozen=True)
class ChoiceReceipt:
    schema_id: str
    schema_version: str
    review_status: str
    decision_id: str
    household_id: str
    revision: int
    day_index: int
    stratum: str
    opportunity: str
    option_id: str
    rule_option_id: str
    origin: str
    selection_reason: str
    fallback_reason: str | None
    observation_hash: str
    prompt_version: str | None
    model_configuration: str | None
    raw_response: str | None
    explanation: str
    explanation_origin: str
    synthetic_label: str
    cited_event_ids: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    reserved_charge_cad: str | None
    actual_charge_cad: str | None
    latency_seconds: float | None
    utility: float
    stream_algorithm: str
    legal_at_observation: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "review_status": self.review_status,
            "decision_id": self.decision_id,
            "household_id": self.household_id,
            "revision": self.revision,
            "day_index": self.day_index,
            "stratum": self.stratum,
            "opportunity": self.opportunity,
            "option_id": self.option_id,
            "rule_option_id": self.rule_option_id,
            "origin": self.origin,
            "selection_reason": self.selection_reason,
            "fallback_reason": self.fallback_reason,
            "observation_hash": self.observation_hash,
            "prompt_version": self.prompt_version,
            "model_configuration": self.model_configuration,
            "raw_response": self.raw_response,
            "explanation": self.explanation,
            "explanation_origin": self.explanation_origin,
            "synthetic_label": self.synthetic_label,
            "cited_event_ids": list(self.cited_event_ids),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reserved_charge_cad": self.reserved_charge_cad,
            "actual_charge_cad": self.actual_charge_cad,
            "latency_seconds": None if self.latency_seconds is None else canon_float(self.latency_seconds),
            "utility": canon_float(self.utility),
            "stream_algorithm": self.stream_algorithm,
            "legal_at_observation": self.legal_at_observation,
        }


def _fact_payload(fact: ObservedFact) -> dict[str, object]:
    return {
        "fact_id": fact.fact_id,
        "kind": fact.kind,
        "attributes": [[key, value] for key, value in fact.attributes],
    }


def _option_payload(option: FeasibleOption) -> dict[str, object]:
    return {
        "option_id": option.option_id,
        "kind": option.kind,
        "store_id": option.store_id,
        "lines": [
            {"product_id": line.product_id, "grams": line.grams, "price_cents": line.price_cents}
            for line in option.lines
        ],
        "expected_payment_cents": option.expected_payment_cents,
        "total_seconds": option.total_seconds,
        "preference_fit": canon_float(option.preference_fit),
        "habit_value": canon_float(option.habit_value),
        "known_quality": canon_float(option.known_quality),
        "stockout_penalty": canon_float(option.stockout_penalty),
        "uncertainty_penalty": canon_float(option.uncertainty_penalty),
        "attributes": [[key, value] for key, value in option.attributes],
    }
