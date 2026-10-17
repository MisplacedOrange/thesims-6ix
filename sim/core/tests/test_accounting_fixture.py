"""Literal purchase, consumption, and processing fixture.

Expected cents and grams are the values written in the validation note.
They are not computed from the implementation's pricing or yield helpers.
"""

import unittest

import bootstrap  # noqa: F401

from sim.core.commands import (
    PHASE_CONSUME,
    PHASE_POLICY,
    PHASE_SETTLE,
    ConsumeFood,
    ProcessBatch,
    PurchaseLot,
    TransferCash,
    TransferLot,
)
from sim.core.economy import lots_for_owner
from sim.core.examples import open_fixture_world
from sim.core.kernel import apply_command, fold_events, invariant_problems


def _cash(state, owner: str) -> int:
    return next(account.settled_cents for account in state.accounts if account.owner_id == owner)


class LiteralFixtureTest(unittest.TestCase):
    def test_exact_cents_and_grams(self) -> None:
        state = open_fixture_world("fixture-run")
        self.assertEqual(_cash(state, "H"), 1000)
        self.assertEqual(_cash(state, "M"), 500)
        self.assertEqual(_cash(state, "R"), 0)
        self.assertEqual(_cash(state, "P"), 0)
        self.assertEqual(sum(lot.grams for lot in state.lots), 1000)

        state = apply_command(
            state,
            TransferCash("fx-subsidy", 1, PHASE_POLICY, "acct-M", "acct-R", 200, "subsidy"),
        ).state
        bought = apply_command(
            state,
            PurchaseLot(
                "fx-purchase",
                2,
                PHASE_SETTLE,
                "acct-H",
                "acct-R",
                "home-H",
                "lot-produce-open",
                600,
                400,
            ),
        )
        self.assertEqual(bought.status, "accepted")
        state = bought.state
        household_lots = lots_for_owner(state, "H")
        retailer_lots = lots_for_owner(state, "R")
        self.assertEqual(sum(lot.grams for lot in household_lots), 600)
        self.assertEqual(sum(lot.grams for lot in retailer_lots), 400)

        eaten = apply_command(
            state,
            ConsumeFood("fx-eat", 3, PHASE_CONSUME, "H", household_lots[0].lot_id, 200),
        )
        self.assertEqual(eaten.status, "accepted")
        state = eaten.state
        moved = apply_command(
            state,
            TransferLot("fx-move", 4, PHASE_SETTLE, retailer_lots[0].lot_id, 400, "P", "plant-P"),
        )
        self.assertEqual(moved.status, "accepted")
        state = moved.state
        paid = apply_command(
            state,
            TransferCash("fx-fee", 4, PHASE_SETTLE, "acct-R", "acct-P", 100, "processing_fee"),
        )
        self.assertEqual(paid.status, "accepted")
        state = paid.state
        processor_lots = lots_for_owner(state, "P")
        self.assertEqual(sum(lot.grams for lot in processor_lots), 400)
        processed = apply_command(
            state,
            ProcessBatch(
                "fx-process",
                5,
                PHASE_SETTLE,
                "P",
                processor_lots[0].lot_id,
                400,
                "produce.prepared",
                300,
                100,
                "plant-P",
                None,
            ),
        )
        self.assertEqual(processed.status, "accepted")
        final = processed.state

        self.assertEqual(_cash(final, "H"), 600)
        self.assertEqual(_cash(final, "M"), 300)
        self.assertEqual(_cash(final, "R"), 500)
        self.assertEqual(_cash(final, "P"), 100)
        self.assertEqual(_cash(final, "H") + _cash(final, "M") + _cash(final, "R") + _cash(final, "P"), 1500)
        self.assertEqual(sum(lot.grams for lot in lots_for_owner(final, "H")), 400)
        self.assertEqual(sum(lot.grams for lot in lots_for_owner(final, "P")), 300)
        self.assertEqual(final.consumed_grams, 200)
        self.assertEqual(final.loss_grams, 100)
        self.assertEqual(400 + 300 + 200 + 100, 1000)
        self.assertEqual(final.reservations, ())
        self.assertEqual(invariant_problems(final), ())

        subsidy = next(entry for entry in final.journal if entry.command_id == "fx-subsidy")
        purchase = next(entry for entry in final.journal if entry.command_id == "fx-purchase")
        fee = next(entry for entry in final.journal if entry.command_id == "fx-fee")
        self.assertEqual({(line.account_id, line.cents) for line in subsidy.lines}, {("acct-M", -200), ("acct-R", 200)})
        self.assertEqual(
            {(line.account_id, line.cents) for line in purchase.lines},
            {("acct-H", -400), ("acct-R", 400)},
        )
        self.assertEqual({(line.account_id, line.cents) for line in fee.lines}, {("acct-R", -100), ("acct-P", 100)})
        for entry in final.journal:
            self.assertEqual(sum(line.cents for line in entry.lines), 0)

        kinds = {}
        for movement in final.movements:
            kinds.setdefault(movement.kind, 0)
            kinds[movement.kind] += movement.grams
        self.assertEqual(kinds["import"], 1000)
        self.assertEqual(kinds["transfer"], 1000)
        self.assertEqual(kinds["consume"], 200)
        self.assertEqual(kinds["process_output"], 300)
        self.assertEqual(kinds["process_loss"], 100)
        self.assertEqual(
            next(movement.product_id for movement in final.movements if movement.kind == "process_output"),
            "produce.prepared",
        )
        self.assertEqual(
            next(movement.product_id for movement in final.movements if movement.kind == "process_loss"),
            "produce.fresh",
        )

    def test_unbalanced_process_is_rejected(self) -> None:
        state = open_fixture_world("fixture-reject")
        state = apply_command(
            state,
            TransferLot("move", 1, PHASE_SETTLE, "lot-produce-open", 400, "P", "plant-P"),
        ).state
        lot_id = lots_for_owner(state, "P")[0].lot_id
        rejected = apply_command(
            state,
            ProcessBatch("bad", 2, PHASE_SETTLE, "P", lot_id, 400, "produce.prepared", 300, 50, "plant-P", None),
        )
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.reason, "mass_not_conserved")
        self.assertIs(rejected.state, state)


class ReplayFixtureTest(unittest.TestCase):
    def test_folding_events_reproduces_the_fixture_without_recompiling(self) -> None:
        opening = open_fixture_world("fixture-replay")
        commands = []
        state = opening
        steps = [
            TransferCash("fx-subsidy", 1, PHASE_POLICY, "acct-M", "acct-R", 200, "subsidy"),
            PurchaseLot("fx-purchase", 2, PHASE_SETTLE, "acct-H", "acct-R", "home-H", "lot-produce-open", 600, 400),
        ]
        for command in steps:
            transition = apply_command(state, command)
            commands.append(transition)
            state = transition.state
        household_lot = lots_for_owner(state, "H")[0].lot_id
        retailer_lot = lots_for_owner(state, "R")[0].lot_id
        follow = [
            ConsumeFood("fx-eat", 3, PHASE_CONSUME, "H", household_lot, 200),
            TransferLot("fx-move", 4, PHASE_SETTLE, retailer_lot, 400, "P", "plant-P"),
            TransferCash("fx-fee", 4, PHASE_SETTLE, "acct-R", "acct-P", 100, "processing_fee"),
        ]
        for command in follow:
            transition = apply_command(state, command)
            commands.append(transition)
            state = transition.state
        processor_lot = lots_for_owner(state, "P")[0].lot_id
        transition = apply_command(
            state,
            ProcessBatch(
                "fx-process",
                5,
                PHASE_SETTLE,
                "P",
                processor_lot,
                400,
                "produce.prepared",
                300,
                100,
                "plant-P",
                None,
            ),
        )
        commands.append(transition)
        final = transition.state
        events = tuple(event for step in commands for event in step.events)
        replayed = fold_events(opening, events)
        self.assertEqual(replayed, final)
        self.assertEqual(_cash(replayed, "H"), 600)
        self.assertEqual(replayed.loss_grams, 100)


if __name__ == "__main__":
    unittest.main()
