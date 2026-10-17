import unittest

import bootstrap  # noqa: F401

from sim.core.commands import (
    PHASE_EXPIRY,
    PHASE_POLICY,
    PHASE_SETTLE,
    ApplyExpiry,
    IntroduceLot,
    OpenAccount,
    PurchaseLot,
    ReleaseReservation,
    ReserveResources,
    TransferCash,
)
from sim.core.economy import lots_for_owner, spendable_cents
from sim.core.kernel import apply_command, apply_commands, empty_state, seeded_admission_order, state_hash
from sim.core.catalog import load_catalog


def _world():
    catalog = load_catalog()
    state = empty_state(
        run_id="reserve-run",
        scenario_id="reserve",
        catalog_id=catalog.catalog_id,
        catalog_sha256=catalog.sha256,
        known_product_ids=tuple(product.product_id for product in catalog.products),
    )
    transitions = apply_commands(
        state,
        [
            OpenAccount("ext", 0, PHASE_POLICY, "acct-ext", "external", "external", True),
            OpenAccount("h1", 0, PHASE_POLICY, "acct-h1", "H1", "household", False),
            OpenAccount("h2", 0, PHASE_POLICY, "acct-h2", "H2", "household", False),
            OpenAccount("r", 0, PHASE_POLICY, "acct-r", "R", "retailer", False),
            TransferCash("c1", 0, PHASE_POLICY, "acct-ext", "acct-h1", 1000, "opening_balance"),
            TransferCash("c2", 0, PHASE_POLICY, "acct-ext", "acct-h2", 1000, "opening_balance"),
            IntroduceLot("lot", 0, PHASE_POLICY, "lot-a", "produce.fresh", "R", "store", 600, 0, None),
        ],
    )
    return transitions[-1].state


class ReservationTest(unittest.TestCase):
    def test_two_shoppers_cannot_reserve_the_same_stock(self) -> None:
        state = _world()
        order = seeded_admission_order(17, "shop", ["H1", "H2"])
        commands = []
        for actor in order:
            account = f"acct-{actor.lower()}"
            commands.append(ReserveResources(f"rs-{actor}", 1, PHASE_SETTLE, actor, account, 400, "lot-a", 600))
        transitions = apply_commands(state, commands)
        self.assertEqual([item.status for item in transitions], ["accepted", "rejected"])
        self.assertEqual(transitions[1].reason, "insufficient_stock")
        self.assertEqual(len(transitions[-1].state.reservations), 1)
        self.assertEqual(sum(lot.grams for lot in transitions[-1].state.lots), 600)

    def test_cash_reservation_blocks_overspend_and_releases_once(self) -> None:
        state = _world()
        held = apply_command(state, ReserveResources("hold", 1, PHASE_SETTLE, "H1", "acct-h1", 600, None, 0))
        self.assertEqual(held.status, "accepted")
        state = held.state
        account = next(item for item in state.accounts if item.account_id == "acct-h1")
        self.assertEqual(spendable_cents(account), 400)
        blocked = apply_command(state, ReserveResources("more", 1, PHASE_SETTLE, "H1", "acct-h1", 500, None, 0))
        self.assertEqual(blocked.status, "rejected")
        self.assertEqual(blocked.reason, "insufficient_cash")
        self.assertIs(blocked.state, state)
        released = apply_command(state, ReleaseReservation("drop", 2, PHASE_SETTLE, "rsv.hold"))
        self.assertEqual(released.status, "accepted")
        again = apply_command(released.state, ReleaseReservation("drop-2", 2, PHASE_SETTLE, "rsv.hold"))
        self.assertEqual(again.status, "rejected")
        self.assertEqual(again.reason, "unknown_reservation")
        self.assertEqual(state_hash(again.state), state_hash(released.state))
        restored = next(item for item in released.state.accounts if item.account_id == "acct-h1")
        self.assertEqual(restored.settled_cents, 1000)
        self.assertEqual(restored.reserved_cents, 0)

    def test_settlement_releases_the_unused_hold_and_cannot_exceed_it(self) -> None:
        state = _world()
        state = apply_command(
            state, IntroduceLot("more-stock", 1, PHASE_POLICY, "lot-b", "produce.fresh", "R", "store", 1000, 90, None)
        ).state
        held = apply_command(state, ReserveResources("hold", 2, PHASE_SETTLE, "H1", "acct-h1", 500, "lot-b", 800))
        self.assertEqual(held.status, "accepted")
        too_much = apply_command(
            held.state,
            PurchaseLot("too", 2, PHASE_SETTLE, "acct-h1", "acct-r", "home", "lot-b", 100, 501, "rsv.hold"),
        )
        self.assertEqual(too_much.status, "rejected")
        self.assertEqual(too_much.reason, "reservation_exceeded")
        self.assertEqual(len(too_much.state.reservations), 1)
        bought = apply_command(
            held.state,
            PurchaseLot("buy", 2, PHASE_SETTLE, "acct-h1", "acct-r", "home", "lot-b", 600, 400, "rsv.hold"),
        )
        self.assertEqual(bought.status, "accepted")
        self.assertEqual(bought.state.reservations, ())
        buyer = next(item for item in bought.state.accounts if item.account_id == "acct-h1")
        seller = next(item for item in bought.state.accounts if item.account_id == "acct-r")
        self.assertEqual(buyer.settled_cents, 600)
        self.assertEqual(buyer.reserved_cents, 0)
        self.assertEqual(seller.settled_cents, 400)
        self.assertEqual(sum(lot.grams for lot in lots_for_owner(bought.state, "H1")), 600)
        self.assertEqual(sum(lot.grams for lot in lots_for_owner(bought.state, "R")), 1000)

    def test_direct_purchases_cannot_duplicate_food(self) -> None:
        state = _world()
        order = seeded_admission_order(4, "buy", ["H2", "H1"])
        commands = [
            PurchaseLot(f"buy-{actor}", 1, PHASE_SETTLE, f"acct-{actor.lower()}", "acct-r", f"home-{actor}", "lot-a", 400, 300)
            for actor in order
        ]
        transitions = apply_commands(state, commands)
        self.assertEqual(transitions[0].status, "accepted")
        self.assertEqual(transitions[1].status, "rejected")
        self.assertEqual(transitions[1].reason, "insufficient_stock")
        final = transitions[-1].state
        self.assertEqual(sum(lot.grams for lot in final.lots if lot.owner_id == order[0]), 400)
        self.assertEqual(sum(lot.grams for lot in final.lots if lot.owner_id == order[1]), 0)
        self.assertEqual(sum(lot.grams for lot in final.lots if lot.owner_id == "R"), 200)
        self.assertEqual(sum(lot.grams for lot in final.lots), 600)
        self.assertEqual(next(account.settled_cents for account in final.accounts if account.owner_id == "R"), 300)

    def test_partial_reservation_failure_holds_nothing(self) -> None:
        state = _world()
        rejected = apply_command(state, ReserveResources("both", 1, PHASE_SETTLE, "H1", "acct-h1", 100, "lot-a", 99999))
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.reason, "insufficient_stock")
        self.assertEqual(rejected.state.reservations, ())
        account = next(item for item in rejected.state.accounts if item.account_id == "acct-h1")
        self.assertEqual(account.reserved_cents, 0)

    def test_expired_lot_cannot_be_purchased_and_waste_conserves_mass(self) -> None:
        state = _world()
        state = apply_command(
            state,
            IntroduceLot("old", 1, PHASE_POLICY, "lot-old", "produce.fresh", "R", "store", 100, 10, 5),
        ).state
        state = apply_command(state, ReserveResources("hold", 4, PHASE_SETTLE, "H1", "acct-h1", 40, "lot-old", 100)).state
        blocked = apply_command(
            state,
            PurchaseLot("late", 5, PHASE_SETTLE, "acct-h1", "acct-r", "home", "lot-old", 100, 40, "rsv.hold"),
        )
        self.assertEqual(blocked.reason, "unsafe_lot")
        expired = apply_command(state, ApplyExpiry("expire", 5, PHASE_EXPIRY))
        self.assertEqual(expired.status, "accepted")
        self.assertFalse(any(lot.lot_id == "lot-old" for lot in expired.state.lots))
        self.assertEqual(expired.state.loss_grams, 100)
        self.assertEqual(expired.state.reservations, ())
        buyer = next(item for item in expired.state.accounts if item.account_id == "acct-h1")
        self.assertEqual(buyer.settled_cents, 1000)
        self.assertEqual(buyer.reserved_cents, 0)
        self.assertEqual(sum(lot.acquisition_cents for lot in expired.state.lots) + 10, 10)


if __name__ == "__main__":
    unittest.main()
