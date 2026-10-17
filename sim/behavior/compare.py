"""Compare rule choices with generated choices.

Reports are descriptive. A divergence outside an uncalibrated range is a
hypothesis, not a finding about Toronto residents. Budget-exhaustion shares
are not a significance test.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.behavior.draft import ORIGIN_FALLBACK, ORIGIN_LLM, ORIGIN_RECORDED, ORIGIN_RULE, ChoiceReceipt

_DESCRIPTIVE_GAP = 0.10


@dataclass(frozen=True)
class DivergenceRange:
    evidence_state: str = "uncalibrated"
    max_share: float | None = None


@dataclass(frozen=True)
class ShareRow:
    key: str
    count: int
    share: float


@dataclass(frozen=True)
class BehaviorComparison:
    decisions: int
    llm_choices: int
    rule_choices: int
    recorded_choices: int
    fallback_choices: int
    dispatched: int
    not_selected_for_live_barrier: int
    timeouts: int
    grounding_replacements: int
    divergence_share: float | None
    divergence_within_range: bool | None
    range_evidence_state: str
    selection_by_stratum: tuple[ShareRow, ...]
    eligible_by_stratum: tuple[ShareRow, ...]
    fallback_reasons: tuple[ShareRow, ...]
    budget_exhausted_by_stratum: tuple[ShareRow, ...]
    budget_exhausted_by_day: tuple[ShareRow, ...]
    budget_gap_by_stratum: tuple[tuple[str, float], ...]
    late_days_carry_more_exhaustion: bool | None
    input_tokens: int
    output_tokens: int
    charge_cad: str
    mean_latency_seconds: float | None
    note: str


def compare_receipts(
    receipts: tuple[ChoiceReceipt, ...] | list[ChoiceReceipt],
    *,
    divergence_range: DivergenceRange | None = None,
) -> BehaviorComparison:
    rows = tuple(receipts)
    band = divergence_range or DivergenceRange()
    decisions = len(rows)
    llm = sum(1 for row in rows if row.origin == ORIGIN_LLM)
    rule = sum(1 for row in rows if row.origin == ORIGIN_RULE)
    recorded = sum(1 for row in rows if row.origin == ORIGIN_RECORDED)
    fallback = sum(1 for row in rows if row.origin == ORIGIN_FALLBACK)
    dispatched = sum(1 for row in rows if row.selection_reason == "dispatched")
    not_selected = sum(1 for row in rows if row.selection_reason == "not_selected_for_live_barrier")
    timeouts = sum(1 for row in rows if row.fallback_reason == "late")
    grounding = sum(1 for row in rows if row.explanation_origin == "llm_replaced_ungrounded")
    comparable = [row for row in rows if row.rule_option_id]
    if comparable:
        mismatches = sum(1 for row in comparable if row.option_id != row.rule_option_id)
        divergence = mismatches / len(comparable)
    else:
        divergence = None
    within: bool | None
    if divergence is None or band.max_share is None or band.evidence_state == "uncalibrated":
        within = None
    else:
        within = divergence <= band.max_share
    eligible = [
        row
        for row in rows
        if row.selection_reason
        not in {"not_a_live_opportunity", "not_in_focal_panel", "rule_policy", "frozen_receipt"}
    ]
    exhausted = [row for row in rows if row.fallback_reason == "budget_exhausted"]
    latencies = [row.latency_seconds for row in rows if row.latency_seconds is not None and row.origin == ORIGIN_LLM]
    gaps = _gaps(exhausted, eligible)
    return BehaviorComparison(
        decisions=decisions,
        llm_choices=llm,
        rule_choices=rule,
        recorded_choices=recorded,
        fallback_choices=fallback,
        dispatched=dispatched,
        not_selected_for_live_barrier=not_selected,
        timeouts=timeouts,
        grounding_replacements=grounding,
        divergence_share=divergence,
        divergence_within_range=within,
        range_evidence_state=band.evidence_state,
        selection_by_stratum=_shares(_counts(row.stratum for row in rows if row.selection_reason == "dispatched")),
        eligible_by_stratum=_shares(_counts(row.stratum for row in eligible)),
        fallback_reasons=_shares(_counts(row.fallback_reason or "" for row in rows if row.fallback_reason)),
        budget_exhausted_by_stratum=_shares(_counts(row.stratum for row in exhausted)),
        budget_exhausted_by_day=_shares(_counts(str(row.day_index) for row in exhausted)),
        budget_gap_by_stratum=gaps,
        late_days_carry_more_exhaustion=_late_days(exhausted),
        input_tokens=sum(row.input_tokens for row in rows),
        output_tokens=sum(row.output_tokens for row in rows),
        charge_cad=_charge(rows),
        mean_latency_seconds=(sum(latencies) / len(latencies)) if latencies else None,
        note=(
            "Choice divergence and budget shares are descriptive model diagnostics. "
            "They are not public opinion and not a significance test. "
            "Timeouts are counted separately from households left on the rule policy."
        ),
    )


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value == "":
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _shares(counts: dict[str, int]) -> tuple[ShareRow, ...]:
    total = sum(counts.values())
    rows = []
    for key in sorted(counts):
        count = counts[key]
        rows.append(ShareRow(key, count, 0.0 if total == 0 else count / total))
    return tuple(rows)


def _gaps(exhausted: list[ChoiceReceipt], eligible: list[ChoiceReceipt]) -> tuple[tuple[str, float], ...]:
    if not exhausted or not eligible:
        return ()
    exhausted_counts = _counts(row.stratum for row in exhausted)
    eligible_counts = _counts(row.stratum for row in eligible)
    exhausted_total = sum(exhausted_counts.values())
    eligible_total = sum(eligible_counts.values())
    keys = sorted(set(exhausted_counts) | set(eligible_counts))
    gaps = []
    for key in keys:
        exhausted_share = exhausted_counts.get(key, 0) / exhausted_total
        eligible_share = eligible_counts.get(key, 0) / eligible_total
        gaps.append((key, exhausted_share - eligible_share))
    return tuple(gaps)


def _late_days(exhausted: list[ChoiceReceipt]) -> bool | None:
    if not exhausted:
        return None
    days = sorted({row.day_index for row in exhausted})
    if len(days) < 2:
        return None
    cutoff = days[0] + (days[-1] - days[0]) * 2 / 3
    early = sum(1 for row in exhausted if row.day_index <= days[0] + (days[-1] - days[0]) / 3)
    late = sum(1 for row in exhausted if row.day_index >= cutoff)
    return late > early


def _charge(rows: tuple[ChoiceReceipt, ...]) -> str:
    from decimal import Decimal

    total = Decimal("0")
    for row in rows:
        if row.actual_charge_cad:
            total += Decimal(row.actual_charge_cad)
    return format(total, "f")


def disproportionate_strata(comparison: BehaviorComparison) -> tuple[str, ...]:
    """Strata whose exhaustion share exceeds their eligible share by 10 points."""

    return tuple(key for key, gap in comparison.budget_gap_by_stratum if gap >= _DESCRIPTIVE_GAP)
