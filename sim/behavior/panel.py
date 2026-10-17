"""Fixed focal panel and the predeclared live-barrier subset.

The camera never selects this panel. A study fixes it before the run from the
roster and a seed. Each decision barrier then admits at most four focal
households using a rotation that does not look at provider latency.
"""

from __future__ import annotations

from dataclasses import dataclass

from sim.behavior.determinism import draw_rank
from sim.behavior.errors import BehaviorError
from sim.behavior.snapshot import LIVE_OPPORTUNITIES

MAX_FOCAL = 40
MAX_LIVE_PER_BARRIER = 4
PANEL_ALGORITHM = "guaranteed-seat-then-dhondt-v1"


@dataclass(frozen=True)
class RosterHousehold:
    household_id: str
    stratum: str


@dataclass(frozen=True)
class FocalPanel:
    household_ids: tuple[str, ...]
    stratum_by_household: tuple[tuple[str, str], ...]
    seed: int
    max_focal: int
    algorithm: str = PANEL_ALGORITHM

    def stratum(self, household_id: str) -> str | None:
        for household, stratum in self.stratum_by_household:
            if household == household_id:
                return stratum
        return None

    @property
    def ids(self) -> frozenset[str]:
        return frozenset(self.household_ids)


def allocate_seats(population_by_stratum: dict[str, int], max_focal: int) -> dict[str, int]:
    """Give seats to strata, then households are drawn inside the stratum.

    When there are enough seats, every occupied stratum gets one seat first so
    a small study group is not dropped. Remaining seats go one at a time to the
    stratum with the largest ``population / (seats + 1)``. Ties break by
    stratum name ascending. A stratum cannot receive more seats than households.
    """

    if type(max_focal) is not int or max_focal < 0:
        raise BehaviorError("max_focal must be a non-negative int")
    if max_focal > MAX_FOCAL:
        raise BehaviorError("focal panel cannot exceed 40")
    counts = {stratum: count for stratum, count in population_by_stratum.items()}
    for stratum, count in counts.items():
        if type(count) is not int or count < 0 or not stratum:
            raise BehaviorError("stratum population is invalid")
    seats = {stratum: 0 for stratum in counts}
    occupied = sorted(stratum for stratum, count in counts.items() if count > 0)
    remaining = min(max_focal, sum(counts.values()))
    if remaining >= len(occupied) and occupied:
        for stratum in occupied:
            seats[stratum] = 1
        remaining -= len(occupied)
    while remaining > 0:
        room = [stratum for stratum in occupied if seats[stratum] < counts[stratum]]
        if not room:
            break
        winner = min(room, key=lambda stratum: (-(counts[stratum] / (seats[stratum] + 1)), stratum))
        seats[winner] += 1
        remaining -= 1
    return seats


def select_focal_panel(
    roster: tuple[RosterHousehold, ...] | list[RosterHousehold],
    *,
    seed: int,
    max_focal: int = MAX_FOCAL,
) -> FocalPanel:
    if type(seed) is not int or seed < 0:
        raise BehaviorError("panel seed must be a non-negative int")
    seen: set[str] = set()
    by_stratum: dict[str, list[str]] = {}
    for entry in roster:
        if not entry.household_id or any(ch.isspace() for ch in entry.household_id):
            raise BehaviorError("roster household id is invalid")
        if not entry.stratum or any(ch.isspace() for ch in entry.stratum):
            raise BehaviorError("roster stratum is invalid")
        if entry.household_id in seen:
            raise BehaviorError(f"duplicate household {entry.household_id}")
        seen.add(entry.household_id)
        by_stratum.setdefault(entry.stratum, []).append(entry.household_id)
    seats = allocate_seats({stratum: len(ids) for stratum, ids in by_stratum.items()}, max_focal)
    chosen: list[tuple[str, str]] = []
    for stratum in sorted(by_stratum):
        ranked = sorted(
            by_stratum[stratum],
            key=lambda household_id: (
                draw_rank(seed, actor=household_id, day=0, purpose="focal_panel"),
                household_id,
            ),
        )
        for household_id in ranked[: seats[stratum]]:
            chosen.append((stratum, household_id))
    chosen.sort()
    return FocalPanel(
        household_ids=tuple(household_id for _, household_id in chosen),
        stratum_by_household=tuple((household_id, stratum) for stratum, household_id in chosen),
        seed=seed,
        max_focal=max_focal,
    )


def live_rotation_order(
    panel: FocalPanel,
    *,
    day_index: int,
    opportunity: str,
    candidates: tuple[str, ...],
    blocked: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Full predeclared order for one opportunity, before the four-household cap."""

    if type(day_index) is not int or day_index < 0:
        raise BehaviorError("day_index must be a non-negative int")
    if opportunity not in LIVE_OPPORTUNITIES:
        return ()
    strata_of = dict(panel.stratum_by_household)
    candidate_set = set(candidates)
    by_stratum: dict[str, list[str]] = {}
    for household_id in panel.household_ids:
        if household_id not in candidate_set or household_id in blocked:
            continue
        by_stratum.setdefault(strata_of[household_id], []).append(household_id)
    if not by_stratum:
        return ()
    strata = sorted(by_stratum)
    rotation = day_index * len(LIVE_OPPORTUNITIES) + LIVE_OPPORTUNITIES.index(opportunity)
    start = rotation % len(strata)
    ordered_strata = strata[start:] + strata[:start]
    rotated: dict[str, tuple[str, ...]] = {}
    for stratum, members in by_stratum.items():
        ordered = tuple(sorted(members))
        offset = rotation % len(ordered)
        rotated[stratum] = ordered[offset:] + ordered[:offset]
    picked: list[str] = []
    cursors = {stratum: 0 for stratum in ordered_strata}
    while True:
        progressed = False
        for stratum in ordered_strata:
            index = cursors[stratum]
            members = rotated[stratum]
            if index < len(members):
                picked.append(members[index])
                cursors[stratum] = index + 1
                progressed = True
        if not progressed:
            break
    return tuple(picked)


def predeclare_live_subset(
    panel: FocalPanel,
    *,
    day_index: int,
    opportunity: str,
    candidates: tuple[str, ...],
    blocked: frozenset[str] = frozenset(),
    max_live: int = MAX_LIVE_PER_BARRIER,
) -> tuple[str, ...]:
    """Households dispatched for one opportunity, in rotation order.

    The order is a round-robin across strata. Rotation depends on the day and
    the opportunity, not on which response arrives first. The result is at most
    four households.
    """

    if type(max_live) is not int or max_live < 0 or max_live > MAX_LIVE_PER_BARRIER:
        raise BehaviorError("a barrier admits at most 4 live choices")
    return live_rotation_order(
        panel,
        day_index=day_index,
        opportunity=opportunity,
        candidates=candidates,
        blocked=blocked,
    )[:max_live]
