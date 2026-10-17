"""Capacity limits use literal seconds, cents, and grams."""

from __future__ import annotations

import unittest

from sim.logistics.core_interface.protocol import CoreRejection
from sim.logistics.drones import windows_overlap
from sim.logistics.errors import LogisticsError
from sim.logistics.tests.support import direct_order, engine_for, fleet, lot, of_kind, van
from sim.logistics.units import charge_seconds, travel_seconds


class RoundingTests(unittest.TestCase):
    def test_travel_and_charging_round_upward(self) -> None:
        # 101 m at 10 m/s is 10.1 s, which ceilings to 11. 1 m at 10 m/s is still 1 s.
        self.assertEqual(travel_seconds(0, 10, 1000), 0)
        self.assertEqual(travel_seconds(1, 10, 1000), 1)
        self.assertEqual(travel_seconds(101, 10, 1000), 11)
        # 100 m at 10 m/s with congestion 1.5 is 15 s exactly.
        self.assertEqual(travel_seconds(100, 10, 1500), 15)
        self.assertEqual(charge_seconds(0, 100), 0)
        self.assertEqual(charge_seconds(600, 100), 6)
        self.assertEqual(charge_seconds(601, 100), 7)

    def test_windows_are_half_open(self) -> None:
        self.assertTrue(windows_overlap(((0, 1000),), 15, 30))
        self.assertFalse(windows_overlap(((30, 40),), 15, 30))
        self.assertTrue(windows_overlap(((29, 30),), 15, 30))


class CapacityTests(unittest.TestCase):
    def test_waiting_line_rejects_the_order_that_does_not_fit(self) -> None:
        # One van, one waiting slot, three orders at the same second.
        # Trip: 5 prep + 10 load + 30 travel + 10 unload + 30 return = 85 s.
        # Collection is the unload, 55 s after a trip starts.
        # The van is free again at 85 s, so the waiter collects at 140 s.
        orders = [
            direct_order("o-1", "hh-1", "lot-1"),
            direct_order("o-2", "hh-2", "lot-2"),
            direct_order("o-3", "hh-3", "lot-3"),
        ]
        lots = [lot("lot-1"), lot("lot-2"), lot("lot-3")]
        world, core = engine_for(orders, lots, [van()], fleet_config=fleet(queue_waiting_capacity=1))
        world.advance_to(10_000)
        metrics = world.metrics()
        self.assertEqual(metrics.count("completed_orders").value, 2)
        self.assertEqual(metrics.count("unserved_orders").value, 1)
        self.assertEqual(metrics.count("queue_rejections").value, 1)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 195)
        self.assertEqual(metrics.quantity("completed_queue_seconds").value, 85)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 2_440)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").unit, "cents")
        self.assertEqual(metrics.ratio("cost_per_completed_order").numerator, 2_440)
        self.assertEqual(metrics.ratio("cost_per_completed_order").denominator, 2)
        rejected = [order for order in world.orders.values() if order.status == "unserved"]
        self.assertEqual(rejected[0].reasons, ("queue_capacity",))
        rejected_lot = core.lot(rejected[0].spec.lot_ids[0])
        self.assertEqual(rejected_lot.place_id, "hub")
        self.assertIsNone(rejected_lot.reserved_by)
        self.assertEqual(core.balance_cents(), 0)

    def test_a_full_line_advances_the_household_still_waiting(self) -> None:
        # Capacity 2 lets all three orders in: one starts, two wait.
        # The first return at 85 s admits the next household and moves the last to position 0.
        orders = [direct_order(f"o-{index}", f"hh-{index}", f"lot-{index}") for index in (1, 2, 3)]
        lots = [lot(f"lot-{index}") for index in (1, 2, 3)]
        world, _core = engine_for(orders, lots, [van()], fleet_config=fleet(queue_waiting_capacity=2))
        world.advance_to(10_000)
        metrics = world.metrics()
        self.assertEqual(metrics.count("completed_orders").value, 3)
        self.assertEqual(metrics.count("unserved_orders").value, 0)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 420)
        self.assertEqual(metrics.quantity("completed_queue_seconds").value, 255)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 3_660)
        advanced = of_kind(world, "QueueAdvanced")
        self.assertEqual(len(advanced), 1)
        self.assertEqual(advanced[0].second, 85)
        self.assertEqual(advanced[0].queue_position, 0)

    def test_one_loading_bay_serializes_two_vans(self) -> None:
        # 100 m at 10 m/s is 10 s. Prep 5 + load 10 occupy the only bay.
        # The second van starts at 15 s. Collections are 35 s and 50 s.
        orders = [
            direct_order("o-1", "hh-1", "lot-1", distance_m=100),
            direct_order("o-2", "hh-2", "lot-2", distance_m=100),
        ]
        lots = [lot("lot-1"), lot("lot-2")]
        carriers = [van("van-a"), van("van-b")]
        world, _core = engine_for(orders, lots, carriers, fleet_config=fleet(bay_servers=1))
        world.advance_to(10_000)
        metrics = world.metrics()
        self.assertEqual(metrics.count("completed_orders").value, 2)
        self.assertEqual(metrics.quantity("completed_queue_seconds").value, 15)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 85)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 840)
        self.assertEqual(metrics.quantity("vehicle_distance_m").value, 400)
        self.assertEqual(metrics.quantity("vehicle_distance_m").unit, "metres")

    def test_payload_cold_chain_and_shift_refuse_the_trip(self) -> None:
        heavy, heavy_core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1", grams=6_000)],
            [lot("lot-1", 6_000)],
            [van(payload_grams=5_000)],
        )
        heavy.advance_to(100)
        self.assertEqual(heavy.orders["o-1"].status, "unserved")
        self.assertEqual(heavy.orders["o-1"].reasons, ("payload_grams",))
        self.assertEqual(of_kind(heavy, "JourneyStarted"), [])
        self.assertEqual(heavy.metrics().count("completed_orders").value, 0)
        self.assertFalse(heavy.metrics().ratio("cost_per_completed_order").defined)
        self.assertIsNone(heavy_core.lot("lot-1").reserved_by)
        self.assertEqual(heavy_core.lot("lot-1").grams, 6_000)

        chilled, _core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1", storage_class="chilled")],
            [lot("lot-1", storage_class="chilled")],
            [van(cold_chain=False)],
        )
        chilled.advance_to(100)
        self.assertEqual(chilled.orders["o-1"].reasons, ("cold_chain",))
        self.assertEqual(chilled.orders["o-1"].status, "unserved")

        short_shift, _core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1")],
            [lot("lot-1")],
            [van(shift_end=40)],
        )
        short_shift.advance_to(100)
        self.assertEqual(short_shift.orders["o-1"].reasons, ("shift",))
        self.assertEqual(short_shift.metrics().quantity("allocated_operating_cost_cents").value, 0)
        self.assertEqual(of_kind(short_shift, "JourneyStarted"), [])

    def test_unsafe_food_is_not_loaded(self) -> None:
        world, core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1")],
            [lot("lot-1", unsafe_after_second=0)],
            [van()],
        )
        world.advance_to(100)
        self.assertEqual(world.orders["o-1"].status, "excluded")
        self.assertEqual(world.orders["o-1"].reasons, ("unsafe_lot",))
        self.assertEqual(core.lot("lot-1").place_id, "hub")
        self.assertIsNone(core.lot("lot-1").reserved_by)
        self.assertEqual(of_kind(world, "LoadingStarted"), [])

    def test_a_ground_delivery_posts_a_balanced_cost_and_moves_the_lot(self) -> None:
        # 300 m out and 300 m back at 2 cents/m is 1,200 cents.
        # Load 10 s + unload 10 s at 1 cent/s is 20 cents. Total 1,220 cents.
        # Collection is 5 + 10 + 30 + 10 = 55 s.
        world, core = engine_for(
            [direct_order("o-1", "hh-1", "lot-1")],
            [lot("lot-1")],
            [van()],
        )
        world.advance_to(200)
        metrics = world.metrics()
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 55)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").unit, "seconds")
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 1_220)
        self.assertEqual(metrics.quantity("vehicle_distance_m").value, 600)
        self.assertEqual(of_kind(world, "DeliveryCompleted")[0].second, 55)
        self.assertEqual(of_kind(world, "CostAllocated")[0].cents, 1_220)
        delivered = core.lot("lot-1")
        self.assertEqual(delivered.owner_id, "hh-1")
        self.assertEqual(delivered.custody, "place")
        self.assertEqual(delivered.place_id, "door-hh-1")
        self.assertEqual(delivered.grams, 1_000)
        self.assertIsNone(delivered.reserved_by)
        self.assertEqual(core.balance_cents(), 0)
        self.assertEqual(core.accounts["carrier-operating"], -1_220)
        self.assertEqual(core.accounts["external-energy-labor"], 1_220)
        self.assertEqual(core.reservations, {})

    def test_mass_mismatch_and_duplicate_reservation_are_refused(self) -> None:
        world, _core = engine_for([], [lot("lot-1", 1_000)], [van()], submit=False)
        with self.assertRaises(LogisticsError):
            world.submit_order(direct_order("o-1", "hh-1", "lot-1", grams=900))
        core_only = engine_for([], [lot("lot-9")], [van()], submit=False)[1]
        core_only.reserve("lot-9", "holder", 0)
        with self.assertRaises(CoreRejection):
            core_only.reserve("lot-9", "other", 1)
        with self.assertRaises(CoreRejection):
            core_only.post("post-1", "a", "a", 10, "same", 0)


if __name__ == "__main__":
    unittest.main()
