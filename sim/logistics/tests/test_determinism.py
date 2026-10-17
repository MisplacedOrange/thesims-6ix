"""Same inputs produce the same economic hash and the same event log."""

from __future__ import annotations

import unittest
from dataclasses import replace

from sim.logistics.errors import LogisticsError
from sim.logistics.tests.support import context, direct_order, engine_for, fleet, lot, van


def _three_orders():
    orders = [
        direct_order("o-1", "hh-1", "lot-1"),
        direct_order("o-2", "hh-2", "lot-2"),
        direct_order("o-3", "hh-3", "lot-3"),
    ]
    lots = [lot("lot-1"), lot("lot-2"), lot("lot-3")]
    return orders, lots


def _run(orders, lots, target=10_000):
    world, _core = engine_for(orders, lots, [van()], fleet_config=fleet(queue_waiting_capacity=1))
    world.advance_to(target)
    return world


class DeterminismTests(unittest.TestCase):
    def test_two_runs_share_one_hash_and_one_event_log(self) -> None:
        orders, lots = _three_orders()
        first = _run(orders, lots)
        second = _run(orders, lots)
        self.assertEqual(first.economic_hash(), second.economic_hash())
        self.assertEqual(
            [event.economic_dict() for event in first.events],
            [event.economic_dict() for event in second.events],
        )

    def test_split_advances_match_one_advance(self) -> None:
        orders, lots = _three_orders()
        whole, _core = engine_for(orders, lots, [van()], fleet_config=fleet(queue_waiting_capacity=1))
        whole.advance_to(200)
        stepped, _core = engine_for(orders, lots, [van()], fleet_config=fleet(queue_waiting_capacity=1))
        stepped.advance_to(20)
        stepped.advance_to(50)
        stepped.advance_to(200)
        self.assertEqual(whole.economic_hash(), stepped.economic_hash())
        self.assertEqual(
            [event.economic_dict() for event in whole.events],
            [event.economic_dict() for event in stepped.events],
        )

    def test_submission_order_does_not_change_who_is_served(self) -> None:
        orders, lots = _three_orders()
        forward = _run(orders, lots)
        backward = _run(list(reversed(orders)), lots)
        self.assertEqual(forward.economic_hash(), backward.economic_hash())
        forward_ids = [event.order_id for event in forward.events if event.kind == "LoadingStarted"]
        backward_ids = [event.order_id for event in backward.events if event.kind == "LoadingStarted"]
        self.assertEqual(forward_ids, backward_ids)
        self.assertEqual(
            sorted(order_id for order_id, order in forward.orders.items() if order.status == "completed"),
            sorted(order_id for order_id, order in backward.orders.items() if order.status == "completed"),
        )

    def test_cosmetic_notes_are_outside_the_hash(self) -> None:
        orders, lots = _three_orders()
        world = _run(orders[:1], lots[:1])
        original = world.economic_hash()
        world.cosmetic_note = "camera pan"
        world.events[0] = replace(world.events[0], cosmetic_note="sparkle")
        self.assertEqual(world.economic_hash(), original)
        self.assertNotIn("sparkle", world.canonical_state()["events"][0].values())

    def test_a_different_seed_changes_the_hash(self) -> None:
        order = direct_order("o-1", "hh-1", "lot-1")
        lots = [lot("lot-1")]
        first, _core = engine_for([order], lots, [van()])
        second, _core = engine_for([order], lots, [van()], scenario=context(seed=18))
        first.advance_to(200)
        second.advance_to(200)
        self.assertNotEqual(first.economic_hash(), second.economic_hash())

    def test_a_different_mass_changes_the_hash(self) -> None:
        light, _core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1", grams=1_000)],
            [lot("lot-1", 1_000)],
            [van()],
        )
        heavy, _core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1", grams=1_500)],
            [lot("lot-1", 1_500)],
            [van()],
        )
        light.advance_to(200)
        heavy.advance_to(200)
        self.assertNotEqual(light.economic_hash(), heavy.economic_hash())

    def test_clock_guards(self) -> None:
        world, _core = engine_for([], [], [van()], submit=False)
        world.advance_to(5)
        with self.assertRaises(LogisticsError):
            world.advance_to(4)
        with self.assertRaises(LogisticsError):
            world.submit_order(direct_order("late", "hh-1", "lot-1"))
        digest = world.economic_hash()
        self.assertEqual(world.advance_to(5), ())
        self.assertEqual(world.economic_hash(), digest)


if __name__ == "__main__":
    unittest.main()
