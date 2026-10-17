"""Pure transition layer: state + command -> events + new state.

Persistence, HTTP, and rendering stay outside this package. A caller commits a
transition only by keeping the returned state and events. Discarding them is
the crash-before-commit behavior.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace

from sim.core import codec
from sim.core.codec import canonical_json, sha256_hex
from sim.core.commands import Command
from sim.core.contracts import SceneSnapshot
from sim.core.economy import (
    Rejection,
    account_by_id,
    account_for_owner,
    available_grams,
    compile_command,
    invariant_problems,
    lot_by_id,
    lots_for_owner,
    spendable_cents,
)
from sim.core.events import (
    EVENT_SCHEMA_VERSION,
    AccountsSet,
    ChoicesAppended,
    CommandRecorded,
    EventEnvelope,
    JournalAppended,
    LotsSet,
    MovementsAppended,
    ReservationsSet,
    NonMassLossRecorded,
)
from sim.core.models import WorldState, fresh_state
from sim.core.reasons import CLOCK_REGRESSION, DUPLICATE_COMMAND, NON_INTEGER, PHASE_REGRESSION, WRONG_PHASE, INVALID_ID
from sim.core.units import require_int, valid_id, valid_sha256


class SequenceError(ValueError):
    pass


class ConservationError(RuntimeError):
    def __init__(self, problems: tuple[str, ...]):
        self.problems = problems
        super().__init__("; ".join(problems))


@dataclass(frozen=True, slots=True)
class Transition:
    status: str
    state: WorldState
    events: tuple[EventEnvelope, ...]
    command_id: str
    reason: str | None
    detail: str | None


def empty_state(
    *,
    run_id: str,
    scenario_id: str,
    catalog_id: str,
    catalog_sha256: str,
    known_product_ids: tuple[str, ...],
) -> WorldState:
    if not valid_id(run_id) or not valid_id(scenario_id) or not valid_id(catalog_id):
        raise ValueError("run_id, scenario_id, and catalog_id must be ids")
    if not valid_sha256(catalog_sha256):
        raise ValueError("catalog_sha256 must be a lowercase sha256 hex string")
    if not known_product_ids or any(not valid_id(product_id) for product_id in known_product_ids):
        raise ValueError("known_product_ids must be a non-empty tuple of ids")
    return fresh_state(
        run_id=run_id,
        scenario_id=scenario_id,
        catalog_id=catalog_id,
        catalog_sha256=catalog_sha256,
        known_product_ids=tuple(known_product_ids),
    )


def state_hash(state: WorldState) -> str:
    return sha256_hex(state)


def output_hash(state: WorldState, events: tuple[EventEnvelope, ...]) -> str:
    return sha256_hex({"events": events, "state": state})


def state_to_json(state: WorldState) -> str:
    return codec.state_to_json(state)


def state_from_json(text: str) -> WorldState:
    state = codec.state_from_json(text)
    problems = invariant_problems(state)
    if problems:
        raise ConservationError(problems)
    return state


def events_to_json(events: tuple[EventEnvelope, ...]) -> str:
    return codec.events_to_json(events)


def events_from_json(text: str) -> tuple[EventEnvelope, ...]:
    return codec.events_from_json(text)


def seeded_admission_order(seed: int, opportunity: str, actor_ids: Sequence[str]) -> tuple[str, ...]:
    """Deterministic order that is not actor-id order.

    The digest is keyed by seed, opportunity, and actor. Equal actor ids keep
    their relative order only when the digests tie, which they do not for
    distinct ids.
    """

    require_int(seed, "seed")
    if not isinstance(opportunity, str) or opportunity == "":
        raise ValueError("opportunity must be a non-empty string")

    def sort_key(actor_id: str) -> bytes:
        return hashlib.sha256(f"{seed}|{opportunity}|{actor_id}|admission".encode("utf-8")).hexdigest().encode()

    return tuple(sorted(actor_ids, key=sort_key))


def scene_snapshot(state: WorldState) -> SceneSnapshot:
    return SceneSnapshot(
        schema_version=1,
        run_id=state.run_id,
        scenario_id=state.scenario_id,
        sequence=state.next_sequence - 1,
        second=state.second,
        phase=state.phase,
        state_hash=state_hash(state),
        accounts=state.accounts,
        lots=state.lots,
        reservations=state.reservations,
        imported_grams=state.imported_grams,
        added_grams=state.added_grams,
        consumed_grams=state.consumed_grams,
        loss_grams=state.loss_grams,
        exported_grams=state.exported_grams,
    )


def apply_command(state: WorldState, command: Command) -> Transition:
    header = _header(state, command)
    if header == DUPLICATE_COMMAND:
        return Transition(
            "duplicate",
            state,
            (),
            command.command_id,
            DUPLICATE_COMMAND,
            "command id already applied",
        )
    if isinstance(header, Rejection):
        return Transition("rejected", state, (), getattr(command, "command_id", ""), header.code, header.detail)
    compiled = compile_command(state, command)
    if isinstance(compiled, Rejection):
        return Transition("rejected", state, (), command.command_id, compiled.code, compiled.detail)
    events = _number_events(state, command, compiled)
    new_state = fold_events(state, events, check=True)
    return Transition("accepted", new_state, events, command.command_id, None, None)


def apply_commands(state: WorldState, commands: Sequence[Command]) -> tuple[Transition, ...]:
    transitions: list[Transition] = []
    for command in commands:
        transition = apply_command(state, command)
        transitions.append(transition)
        state = transition.state
    return tuple(transitions)


def fold_events(
    state: WorldState,
    events: tuple[EventEnvelope, ...] | list[EventEnvelope],
    *,
    check: bool = True,
) -> WorldState:
    for event in events:
        state = apply_event(state, event)
        if check and isinstance(event.payload, CommandRecorded):
            problems = invariant_problems(state)
            if problems:
                raise ConservationError(problems)
    return state


def apply_event(state: WorldState, event: EventEnvelope) -> WorldState:
    if event.schema_version != EVENT_SCHEMA_VERSION:
        raise SequenceError("unsupported event schema_version")
    if event.run_id != state.run_id:
        raise SequenceError("event run_id does not match the state")
    if event.sequence != state.next_sequence:
        raise SequenceError(f"expected sequence {state.next_sequence}, got {event.sequence}")
    if event.kind != event.payload.kind:
        raise SequenceError("event kind does not match its payload")
    state = replace(
        state,
        next_sequence=event.sequence + 1,
        second=event.second,
        phase=event.phase,
        last_event_id=event.event_id,
    )
    payload = event.payload
    if isinstance(payload, AccountsSet):
        by_id = {account.account_id: account for account in state.accounts}
        for account in payload.accounts:
            by_id[account.account_id] = account
        state = replace(state, accounts=tuple(by_id[key] for key in sorted(by_id)))
    elif isinstance(payload, LotsSet):
        by_id = {lot.lot_id: lot for lot in state.lots}
        for lot_id in payload.remove_ids:
            by_id.pop(lot_id, None)
        for lot in payload.lots:
            by_id[lot.lot_id] = lot
        state = replace(state, lots=tuple(by_id[key] for key in sorted(by_id)))
    elif isinstance(payload, ReservationsSet):
        by_id = {reservation.reservation_id: reservation for reservation in state.reservations}
        for reservation_id in payload.remove_ids:
            by_id.pop(reservation_id, None)
        for reservation in payload.reservations:
            by_id[reservation.reservation_id] = reservation
        state = replace(state, reservations=tuple(by_id[key] for key in sorted(by_id)))
    elif isinstance(payload, JournalAppended):
        state = replace(state, journal=state.journal + payload.entries)
    elif isinstance(payload, MovementsAppended):
        state = replace(
            state,
            movements=state.movements + payload.movements,
            imported_grams=payload.imported_grams,
            added_grams=payload.added_grams,
            consumed_grams=payload.consumed_grams,
            loss_grams=payload.loss_grams,
            exported_grams=payload.exported_grams,
        )
    elif isinstance(payload, ChoicesAppended):
        state = replace(state, choices=state.choices + payload.choices)
    elif isinstance(payload, NonMassLossRecorded):
        state = replace(state, non_mass_loss_cents=state.non_mass_loss_cents + payload.cents)
    elif isinstance(payload, CommandRecorded):
        if payload.command_id in state.applied_command_ids:
            raise SequenceError("duplicate command in the event log")
        state = replace(state, applied_command_ids=state.applied_command_ids + (payload.command_id,))
    else:
        raise SequenceError(f"unknown payload {type(payload).__name__}")
    return state


def _header(state: WorldState, command: Command) -> Rejection | str | None:
    command_id = getattr(command, "command_id", "")
    if not valid_id(command_id):
        return Rejection(INVALID_ID, "command_id")
    if command_id in state.applied_command_ids:
        return DUPLICATE_COMMAND
    try:
        second = require_int(command.second, "second")
        phase = require_int(command.phase, "phase")
    except ValueError as exc:
        return Rejection(NON_INTEGER, str(exc))
    if second < 0:
        return Rejection(CLOCK_REGRESSION, "second is negative")
    if phase < 1 or phase > 6:
        return Rejection(WRONG_PHASE, "phase must be 1..6")
    if second < state.second:
        return Rejection(CLOCK_REGRESSION, "second moved backwards")
    if second == state.second and phase < state.phase:
        return Rejection(PHASE_REGRESSION, "phase moved backwards in the same second")
    return None


def _stamp(payload: object, sequence: int) -> object:
    if isinstance(payload, JournalAppended):
        entries = tuple(replace(entry, sequence=sequence) for entry in payload.entries)
        return replace(payload, entries=entries)
    if isinstance(payload, MovementsAppended):
        movements = tuple(replace(movement, sequence=sequence) for movement in payload.movements)
        return replace(payload, movements=movements)
    return payload


def _number_events(state: WorldState, command: Command, payloads: tuple[object, ...]) -> tuple[EventEnvelope, ...]:
    stamped = tuple(payloads) + (CommandRecorded(command_id=command.command_id),)
    events: list[EventEnvelope] = []
    sequence = state.next_sequence
    previous = state.last_event_id
    for payload in stamped:
        payload = _stamp(payload, sequence)
        event_id = f"{state.run_id}:{sequence}"
        events.append(
            EventEnvelope(
                schema_version=EVENT_SCHEMA_VERSION,
                run_id=state.run_id,
                event_id=event_id,
                sequence=sequence,
                second=command.second,
                phase=command.phase,
                kind=payload.kind,  # type: ignore[attr-defined]
                causes=(previous,) if previous is not None else (),
                command_id=command.command_id,
                payload=payload,  # type: ignore[arg-type]
            )
        )
        previous = event_id
        sequence += 1
    return tuple(events)


# Re-export query helpers so the public module can import them from the kernel
# surface without callers reaching into economy.py. They are pure reads.
__all_queries__ = (
    account_by_id,
    account_for_owner,
    lot_by_id,
    lots_for_owner,
    spendable_cents,
    available_grams,
    invariant_problems,
    canonical_json,
)
