"""Lot operations used by the policy and logistics adapters.

These compile to the same replayable events as purchases. No adapter edits
WorldState, and all mass, book value, reservations and cash remain in core.
"""

from dataclasses import replace

from sim.core.commands import (
    DisposeLot, MoveLot, RecognizeNonMassLoss, SplitLot, TransformLot,
)
from sim.core.economy import (
    Rejection, _flows, _split_acquisition, account_for_owner, lot_by_id,
)
from sim.core.events import LotsSet, MovementsAppended, NonMassLossRecorded
from sim.core.models import FoodLot, FoodMovement
from sim.core.units import require_int, valid_id


def _movement(state, command, lot, grams, kind, *, child=None, recognized=0, index=0):
    return FoodMovement(
        movement_id=f"{command.command_id}:{kind}:{index}",
        command_id=command.command_id, sequence=0, kind=kind,
        product_id=child.product_id if child else lot.product_id, grams=grams,
        from_owner_id=lot.owner_id, to_owner_id=child.owner_id if child else None,
        from_lot_id=lot.lot_id, to_lot_id=child.lot_id if child else None,
        parent_lot_ids=(lot.lot_id,), acquisition_cents_recognized=recognized,
        acquisition_cents_introduced=0,
    )


def compile_operation(state, command):
    try:
        return _compile(state, command)
    except ValueError as exc:
        return Rejection("invalid_operation", str(exc))


def _compile(state, command):
    if not isinstance(command, (SplitLot, MoveLot, DisposeLot, TransformLot, RecognizeNonMassLoss)):
        return Rejection("invalid_kind", type(command).__name__)
    if isinstance(command, RecognizeNonMassLoss):
        if require_int(command.cents, "cents") <= 0 or not command.reason:
            raise ValueError("a non-mass loss needs positive cents and a reason")
        return (NonMassLossRecorded(command.cents, command.reason),)
    lot = lot_by_id(state, command.lot_id)
    if lot is None:
        raise ValueError("unknown lot")
    if isinstance(command, MoveLot):
        return _move(state, command, lot)
    if lot.reserved_grams:
        raise ValueError("reserved lot cannot be split, disposed or transformed")
    if lot.journey_id is not None:
        raise ValueError("lot is in transit")
    if isinstance(command, SplitLot):
        grams = require_int(command.grams, "grams")
        if not 0 < grams < lot.grams:
            raise ValueError("split must leave positive source and child lots")
        if not valid_id(command.child_id) or lot_by_id(state, command.child_id):
            raise ValueError("invalid or duplicate split child")
        if lot.unsafe_after is not None and lot.unsafe_after <= command.second:
            raise ValueError("unsafe food cannot be split for use")
        # Policy-port contract: floor the taken book value and keep the
        # remainder on the source; the final piece receives that remainder.
        moved = lot.acquisition_cents * grams // lot.grams
        kept = lot.acquisition_cents - moved
        child = replace(lot, lot_id=command.child_id, grams=grams,
                        acquisition_cents=moved, parents=(lot.lot_id,))
        source = replace(lot, grams=lot.grams - grams, acquisition_cents=kept)
        return (
            LotsSet((), (source, child)),
            MovementsAppended((_movement(state, command, lot, grams, "split", child=child),), **_flows(state)),
        )
    if isinstance(command, DisposeLot):
        return _dispose(state, command, lot)
    return _transform(state, command, lot)


def _move(state, command, lot):
    if (command.place_id is None) == (command.journey_id is None):
        raise ValueError("custody must be exactly one place or journey")
    if not valid_id(command.place_id or command.journey_id):
        raise ValueError("invalid custody id")
    if account_for_owner(state, command.owner_id) is None:
        raise ValueError("unknown new owner")
    if command.holder_id is None:
        if lot.reserved_grams or lot.journey_id is not None:
            raise ValueError("moving a reserved or travelling lot requires its holder")
    else:
        holds = [r for r in state.reservations if r.lot_id == lot.lot_id]
        if len(holds) != 1 or holds[0].holder_id != command.holder_id or holds[0].grams != lot.grams:
            raise ValueError("whole-lot reservation does not match the holder")
    if command.owner_id != lot.owner_id:
        if lot.unsafe_after is not None and lot.unsafe_after <= command.second:
            raise ValueError("unsafe food cannot be handed to a recipient")
        if lot.journey_id is not None:
            raise ValueError("arrival must precede ownership transfer")
    child = replace(lot, owner_id=command.owner_id, place_id=command.place_id, journey_id=command.journey_id)
    return (
        LotsSet((), (child,)),
        MovementsAppended((_movement(state, command, lot, lot.grams, "transfer", child=child),), **_flows(state)),
    )


def _dispose(state, command, lot):
    grams = require_int(command.grams, "grams")
    if not 0 < grams <= lot.grams or not command.reason:
        raise ValueError("invalid disposal quantity or reason")
    if command.disposition not in {"consume", "waste", "export"}:
        raise ValueError("invalid disposal kind")
    if command.disposition != "waste" and lot.unsafe_after is not None and lot.unsafe_after <= command.second:
        raise ValueError("unsafe food cannot be consumed or exported")
    recognized, kept = _split_acquisition(lot.acquisition_cents, grams, lot.grams - grams)
    lots = LotsSet((lot.lot_id,), ()) if grams == lot.grams else LotsSet((), (
        replace(lot, grams=lot.grams - grams, acquisition_cents=kept),))
    return (lots, MovementsAppended(
        (_movement(state, command, lot, grams, command.disposition, recognized=recognized),),
        **_flows(state, consumed=grams if command.disposition == "consume" else 0,
                 loss=grams if command.disposition == "waste" else 0,
                 exported=grams if command.disposition == "export" else 0)))


def _transform(state, command, lot):
    if lot.unsafe_after is not None and lot.unsafe_after <= command.second:
        raise ValueError("unsafe food cannot be transformed")
    if sum(require_int(o.grams, "grams") for o in command.outputs) != lot.grams:
        raise ValueError("transform must conserve grams")
    if sum(require_int(o.acquisition_cents, "acquisition_cents") for o in command.outputs) != lot.acquisition_cents:
        raise ValueError("transform must conserve acquisition cents")
    created, movements, seen = [], [], set()
    loss = 0
    for index, output in enumerate(command.outputs):
        grams = require_int(output.grams, "grams")
        cents = require_int(output.acquisition_cents, "acquisition_cents")
        if grams < 0 or cents < 0 or (grams == 0 and cents):
            raise ValueError("invalid transform quantities")
        if output.disposition not in {"stock", "waste"}:
            raise ValueError("invalid transform disposition")
        if not grams:
            continue
        if output.disposition == "waste":
            loss += grams
            movements.append(_movement(state, command, lot, grams, "process_loss", recognized=cents, index=index))
            continue
        if not valid_id(output.lot_id) or output.lot_id in seen or lot_by_id(state, output.lot_id):
            raise ValueError("invalid or duplicate output id")
        seen.add(output.lot_id)
        if output.product_id not in state.known_product_ids or not valid_id(output.place_id):
            raise ValueError("unknown product or invalid output place")
        if not valid_id(output.source_kind) or not valid_id(output.input_class):
            raise ValueError("invalid output provenance")
        if account_for_owner(state, output.owner_id) is None:
            raise ValueError("unknown output owner")
        if output.unsafe_after is not None:
            if require_int(output.unsafe_after, "unsafe_after") <= command.second:
                raise ValueError("output must remain safe after production")
        child = FoodLot(output.lot_id, output.product_id, output.owner_id, output.place_id,
                        None, grams, 0, output.unsafe_after, (lot.lot_id,), cents,
                        output.source_kind, output.input_class)
        created.append(child)
        movements.append(_movement(state, command, lot, grams, "process_output", child=child, index=index))
    return (LotsSet((lot.lot_id,), tuple(created)),
            MovementsAppended(tuple(movements), **_flows(state, loss=loss)))
