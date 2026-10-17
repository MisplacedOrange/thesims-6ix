"""Drone requests fall back to a van, and a missed handoff can too."""

from __future__ import annotations

import unittest

from sim.logistics.events import MOVEMENT_KINDS
from sim.logistics.tests.support import corridor, drone, drone_order, engine_for, kinds, lot, of_kind, van

GROUND_DOOR_SECONDS = 55
GROUND_COST_CENTS = 1_220


def _fallback_world(order, drone_spec, corridor_spec, with_van=True):
    carriers = [drone_spec]
    if with_van:
        carriers.append(van())
    world, core = engine_for(
        [order],
        [lot("lot-1")],
        carriers,
        corridors=[corridor_spec],
    )
    world.advance_to(10_000)
    return world, core


class FallbackTests(unittest.TestCase):
    def test_no_approval_uses_the_van_and_does_not_fly(self) -> None:
        order = drone_order("o-1", "hh-1", "lot-1", allow_ground_fallback=True)
        world, core = _fallback_world(
            order,
            drone(),
            corridor(approval="no_approval", eligible=False),
        )
        metrics = world.metrics()
        self.assertEqual(of_kind(world, "RouteIneligible")[0].reason, "no_approval")
        self.assertEqual(of_kind(world, "GroundFallbackAssigned")[0].reason, "no_approval")
        self.assertEqual(of_kind(world, "DroneFlightStarted"), [])
        self.assertEqual(metrics.count("fallback_orders").value, 1)
        self.assertEqual(metrics.count("ground_completed_orders").value, 1)
        self.assertEqual(metrics.count("drone_completed_orders").value, 0)
        self.assertEqual(metrics.quantity("completed_flight_seconds").value, 0)
        self.assertEqual(metrics.quantity("vehicle_flight_seconds").value, 0)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, GROUND_DOOR_SECONDS)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, GROUND_COST_CENTS)
        self.assertEqual(of_kind(world, "DeliveryCompleted")[0].second, GROUND_DOOR_SECONDS)
        self.assertEqual(core.lot("lot-1").owner_id, "hh-1")
        self.assertEqual(core.balance_cents(), 0)

    def test_weather_and_site_hours_and_a_short_battery_fall_back(self) -> None:
        cases = [
            (
                "weather",
                drone(),
                corridor(weather=((0, 1000),)),
                "WeatherExcluded",
            ),
            (
                "site_hours",
                drone(),
                corridor(site_close_second=20),
                "CarrierUnavailable",
            ),
            (
                "energy_reserve",
                drone(energy_capacity=200, energy_remaining=50, reserve_energy=100, energy_per_metre=1),
                corridor(),
                "CarrierUnavailable",
            ),
            (
                "maintenance",
                drone(downtime=((0, 100),)),
                corridor(),
                "CarrierUnavailable",
            ),
        ]
        for reason, drone_spec, corridor_spec, event_kind in cases:
            with self.subTest(reason=reason):
                order = drone_order("o-1", "hh-1", "lot-1", allow_ground_fallback=True)
                world, _core = _fallback_world(order, drone_spec, corridor_spec)
                self.assertEqual(of_kind(world, event_kind)[0].reason, reason)
                self.assertEqual(of_kind(world, "DroneFlightStarted"), [])
                self.assertEqual(world.metrics().count("fallback_orders").value, 1)
                self.assertEqual(
                    world.metrics().quantity("completed_door_to_collection_seconds").value,
                    GROUND_DOOR_SECONDS,
                )
                self.assertEqual(
                    world.metrics().quantity("allocated_operating_cost_cents").value,
                    GROUND_COST_CENTS,
                )

    def test_no_approval_without_a_usable_van_is_excluded(self) -> None:
        order = drone_order("o-1", "hh-1", "lot-1", allow_ground_fallback=True, grams=6_000)
        world, core = engine_for(
            [order],
            [lot("lot-1", 6_000)],
            [drone(), van(payload_grams=5_000)],
            corridors=[corridor(approval="no_approval", eligible=False)],
        )
        world.advance_to(100)
        record = world.orders["o-1"]
        self.assertEqual(record.status, "excluded")
        self.assertIn("no_approval", record.reasons)
        self.assertIn("payload_grams", record.reasons)
        self.assertEqual(of_kind(world, "GroundFallbackAssigned"), [])
        self.assertEqual(of_kind(world, "DroneFlightStarted"), [])
        self.assertEqual(world.metrics().count("completed_orders").value, 0)
        self.assertEqual(world.metrics().count("excluded_orders").value, 1)
        self.assertFalse(world.metrics().ratio("cost_per_completed_order").defined)
        self.assertEqual(core.lot("lot-1").place_id, "hub")
        self.assertIsNone(core.lot("lot-1").reserved_by)

    def test_missed_handoff_is_completed_by_the_van(self) -> None:
        # Drone: 5 prep + 10 load + 15 flight + 10 unload + 10 missed window = 50 s.
        # Van from the locker: 5 prep + 30 approach + 10 load + 10 door leg + 10 unload = 65 s.
        # Collection is 50 + 65 = 115 s.
        # Drone money: 600 m * 3 cents + 30 flight-seconds + 20 service-seconds = 1,850.
        # Van money: 800 m * 2 cents + 20 service-seconds + 50 handling cents = 1,670.
        # Total 3,520 cents. The empty drone return is not on the customer's path.
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=True,
            handoff="miss",
            pickup_window_seconds=10,
        )
        world, core = _fallback_world(order, drone(), corridor())
        metrics = world.metrics()
        self.assertEqual(of_kind(world, "HandoffFailed")[0].second, 50)
        self.assertEqual(of_kind(world, "HandoffFailed")[0].reason, "miss")
        self.assertGreaterEqual(len(of_kind(world, "DroneFlightStarted")), 1)
        self.assertEqual(of_kind(world, "GroundFallbackAssigned")[-1].reason, "handoff_failed")
        self.assertEqual(of_kind(world, "DeliveryCompleted")[0].second, 115)
        self.assertEqual(metrics.count("completed_orders").value, 1)
        self.assertEqual(metrics.count("failed_orders").value, 0)
        self.assertEqual(metrics.count("handoff_failures").value, 1)
        self.assertEqual(metrics.count("ground_completed_orders").value, 1)
        self.assertEqual(metrics.count("fallback_orders").value, 1)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 115)
        self.assertEqual(metrics.quantity("completed_preparation_seconds").value, 10)
        self.assertEqual(metrics.quantity("completed_loading_seconds").value, 20)
        self.assertEqual(metrics.quantity("completed_access_transfer_seconds").value, 40)
        self.assertEqual(metrics.quantity("completed_flight_seconds").value, 15)
        self.assertEqual(metrics.quantity("completed_unloading_seconds").value, 20)
        self.assertEqual(metrics.quantity("completed_failed_pickup_wait_seconds").value, 10)
        self.assertEqual(metrics.quantity("completed_queue_seconds").value, 0)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 3_520)
        self.assertEqual(metrics.quantity("vehicle_flight_seconds").value, 30)
        self.assertEqual(metrics.quantity("vehicle_distance_m").value, 1_400)
        self.assertEqual(metrics.ratio("cost_per_completed_order").numerator, 3_520)
        self.assertEqual(metrics.ratio("cost_per_completed_order").denominator, 1)
        self.assertEqual(core.lot("lot-1").owner_id, "hh-1")
        self.assertEqual(core.lot("lot-1").grams, 1_000)
        self.assertEqual(core.balance_cents(), 0)
        self.assertEqual(core.accounts["carrier-operating"], -3_520)

    def test_a_walk_longer_than_the_pickup_window_is_a_failed_handoff(self) -> None:
        # 60 m at 2 m/s is 30 s, which misses a 10 s window even though the customer sets out.
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=True,
            handoff="collect",
            pickup_window_seconds=10,
            walk_distance_m=60,
            walk_speed_m_per_s=2,
        )
        world, _core = _fallback_world(order, drone(), corridor())
        self.assertEqual(of_kind(world, "HandoffFailed")[0].reason, "walk_exceeds_window")
        self.assertEqual(of_kind(world, "DeliveryCompleted")[0].second, 115)
        self.assertEqual(world.metrics().quantity("allocated_operating_cost_cents").value, 3_520)

    def test_missed_handoff_without_fallback_returns_the_food_and_is_not_completed(self) -> None:
        # 5 + 10 + 15 + 10 + 10 wait + 10 reload + 15 return + 10 hub unload = 85 s.
        # Money: 1,800 distance cents + 30 flight cents + 40 service cents = 1,870.
        # Nothing is completed, so cost per completed order stays undefined.
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=False,
            handoff="miss",
            pickup_window_seconds=10,
        )
        world, core = engine_for(
            [order],
            [lot("lot-1")],
            [drone(energy_per_metre=0, energy_capacity=0, energy_remaining=0, reserve_energy=0, charge_per_second=0)],
            corridors=[corridor()],
        )
        world.advance_to(10_000)
        metrics = world.metrics()
        self.assertEqual(world.orders["o-1"].status, "failed")
        self.assertEqual(of_kind(world, "DeliveryFailed")[0].second, 85)
        self.assertEqual(of_kind(world, "DeliveryCompleted"), [])
        self.assertEqual(metrics.count("failed_orders").value, 1)
        self.assertEqual(metrics.count("completed_orders").value, 0)
        self.assertEqual(metrics.count("fallback_orders").value, 0)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 1_870)
        self.assertFalse(metrics.ratio("cost_per_completed_order").defined)
        self.assertEqual(metrics.ratio("cost_per_completed_order").denominator, 0)
        returned = core.lot("lot-1")
        self.assertEqual(returned.owner_id, "hub-owner")
        self.assertEqual(returned.place_id, "hub")
        self.assertEqual(returned.custody, "place")
        self.assertEqual(returned.grams, 1_000)
        self.assertIsNone(returned.reserved_by)
        self.assertEqual(core.balance_cents(), 0)

    def test_a_collected_drone_order_animates_flight_pickup_and_charging(self) -> None:
        # Flight is 300 m at 20 m/s = 15 s. Walk is 60 m at 2 m/s = 30 s.
        # Path: 5 prep + 10 load + 15 flight + 10 unload + 30 walk = 70 s.
        # Vehicle flight includes the 15 s return, so billed flight seconds are 30.
        # Cost: 600 * 3 + 30 + 20 = 1,850 cents.
        # Return arrives at 55 s and the 600-unit deficit charges in 6 s, ending at 61.
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=False,
            handoff="collect",
            pickup_window_seconds=100,
        )
        world, core = engine_for([order], [lot("lot-1")], [drone()], corridors=[corridor()])
        world.advance_to(10_000)
        metrics = world.metrics()
        self.assertEqual(of_kind(world, "DeliveryCompleted")[0].second, 70)
        self.assertEqual(of_kind(world, "CustomerPickupStarted")[0].second, 40)
        self.assertEqual(of_kind(world, "CustomerPickupCompleted")[0].second, 70)
        self.assertEqual(of_kind(world, "ChargingStarted")[0].second, 55)
        self.assertEqual(of_kind(world, "ChargingStarted")[0].arrive_second, 61)
        self.assertEqual(of_kind(world, "ChargingCompleted")[0].second, 61)
        self.assertEqual(metrics.count("drone_completed_orders").value, 1)
        self.assertEqual(metrics.quantity("completed_door_to_collection_seconds").value, 70)
        self.assertEqual(metrics.quantity("completed_flight_seconds").value, 15)
        self.assertEqual(metrics.quantity("completed_customer_pickup_seconds").value, 30)
        self.assertEqual(metrics.quantity("vehicle_flight_seconds").value, 30)
        self.assertEqual(metrics.quantity("allocated_operating_cost_cents").value, 1_850)
        self.assertEqual(metrics.quantity("energy_consumed_units").value, 600)
        self.assertEqual(metrics.quantity("energy_consumed_units").unit, "energy_units")
        self.assertEqual(core.lot("lot-1").owner_id, "hh-1")
        self.assertEqual(core.lot("lot-1").place_id, "door-hh-1")
        self.assertEqual(core.balance_cents(), 0)

    def test_movement_events_carry_a_path_and_a_cause(self) -> None:
        order = drone_order(
            "o-1",
            "hh-1",
            "lot-1",
            allow_ground_fallback=True,
            handoff="miss",
            pickup_window_seconds=10,
        )
        world, _core = _fallback_world(order, drone(), corridor())
        present = set(kinds(world))
        for kind in (
            "QueueJoined",
            "LoadingStarted",
            "LoadingCompleted",
            "DroneFlightStarted",
            "DroneFlightCompleted",
            "NotificationSent",
            "HandoffFailed",
            "GroundFallbackAssigned",
            "JourneyStarted",
            "JourneyArrived",
            "UnloadingStarted",
            "UnloadingCompleted",
            "DeliveryCompleted",
            "CostAllocated",
        ):
            self.assertIn(kind, present)
        for event in world.events:
            if event.kind not in MOVEMENT_KINDS:
                continue
            self.assertGreaterEqual(len(event.waypoints_m), 2, event.kind)
            self.assertIsNotNone(event.depart_second)
            self.assertGreater(event.arrive_second, event.depart_second)
            self.assertTrue(event.causes)
            self.assertTrue(event.vehicle_id or event.leg == "walk")
        for event in of_kind(world, "QueueJoined"):
            self.assertIsNotNone(event.queue_position)
            self.assertGreaterEqual(event.queue_position, 0)
            self.assertEqual(event.queue_id, "hub-dispatch")


if __name__ == "__main__":
    unittest.main()
