"""Accounting, eligibility, contested service and route invariants on a small graph."""

import unittest

from sim.interactables.manifest import load_manifest
from sim.interactables.simulation import HORIZON, WalkingNetwork, run, run_day


def district():
    nodes = [[x * 400 - 800, z * 400 - 800] for z in range(5) for x in range(5)]
    edges = []
    for z in range(5):
        for x in range(5):
            node = z * 5 + x
            if x < 4:
                edges.append([node, node + 1, "crossing"])
            if z < 4:
                edges.append([node, node + 5, "sidewalk"])
    return dict(walkNodes=nodes, walkEdges=edges)


class FoodInteractionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.map = district()
        cls.baseline = run(cls.map, 80)
        cls.policy = run(cls.map, 80, emergency=True)

    def test_food_and_money_conserve_and_households_never_overdraw(self):
        for trace in [self.baseline, self.policy]:
            accounting = trace["accounting"]
            self.assertEqual(accounting["invariant_problems"], [])
            self.assertEqual(accounting["total_cash_cents"], 0)
            self.assertEqual(accounting["imported_grams"], accounting["remaining_grams"] + accounting["consumed_grams"])
            for h in trace["households"]:
                final = trace["terminal_households"][h["id"]]
                self.assertGreaterEqual(final["cash_cents"], 0)
                self.assertEqual(final["cash_cents"] + final["expenditure_cents"], h["opening_cents"])
                self.assertEqual(final["consumed_grams"] + final["pantry_grams"],
                                 h["opening_grams"] + final["received_grams"] + final["purchased_grams"])
                self.assertEqual(final["carrying_grams"], 0)
                self.assertEqual(final["unmet_grams"], max(0, h["need_grams"] - final["consumed_grams"]))

    def test_seed_repeats_exact_events_and_policy_holds_population_fixed(self):
        self.assertEqual(self.baseline, run(self.map, 80))
        self.assertEqual(self.baseline["households"], self.policy["households"])
        self.assertNotIn("emergency", {s["id"] for s in self.baseline["sites"]})
        self.assertTrue(all(e["simulation_time"] >= 3600 for e in self.policy["events"] if e["site_id"] == "emergency"))
        grant = next(e for e in self.policy["events"] if e["action"] == "policy_activation")
        self.assertEqual(grant["public_spending_cents"], 30000)

    def test_only_legal_offers_are_chosen_and_school_eligibility_is_enforced(self):
        latest = {}
        for event in self.policy["events"]:
            if event["action"] == "offered":
                latest[event["household_id"]] = event
            if event["action"] == "chosen" and event.get("option_id") not in {"no_purchase"}:
                offered = latest[event["household_id"]]
                self.assertIn(event["option_id"], {o["option_id"] for o in offered["options"]})
            if event["action"] == "receive_service" and event["site_type"] == "school":
                household = self.policy["households"][event["resident_id"]]
                self.assertGreater(household["children"], 0)
                self.assertLessEqual(event["quantity_grams"], household["children"] * 300)
                self.assertEqual(event["quantity_grams"] % 300, 0)

    def test_capacity_is_rechecked_and_failed_attempts_transfer_nothing(self):
        denials = []
        for trace in [self.baseline, self.policy]:
            for e in trace["events"]:
                if "site_state" in e:
                    self.assertLessEqual(e["site_state"]["served"], e["site_state"]["capacity"])
                    self.assertGreaterEqual(e["site_state"]["stock_grams"], 0)
                if e["result"] == "denied":
                    denials.append(e)
                    self.assertEqual(e["payment_cents"], 0)
                    self.assertEqual(e["quantity_grams"], 0)
        self.assertTrue(denials)

    def test_trips_use_edges_fit_time_budget_and_have_no_future_food_at_home(self):
        edges = {tuple(sorted(e[:2])) for e in self.map["walkEdges"]}
        for trace in [self.baseline, self.policy]:
            self.assertEqual([e["simulation_time"] for e in trace["events"]], sorted(e["simulation_time"] for e in trace["events"]))
            for household_id, trip in trace["journeys"].items():
                h = next(h for h in trace["households"] if h["id"] == household_id)
                self.assertLessEqual(trip["home_at"], HORIZON)
                self.assertLessEqual(trip["home_at"] - trip["depart"], h["time_budget_seconds"])
                for a, b in zip(trip["nodes"], trip["nodes"][1:]):
                    if a != b:
                        self.assertIn(tuple(sorted((a, b))), edges)
            for e in trace["events"]:
                if e["action"] == "purchase":
                    h = trace["households"][e["resident_id"]]
                    self.assertEqual(e["household_state"]["pantry_grams"], h["opening_grams"])
                    self.assertGreater(e["household_state"]["carrying_grams"], 0)

    def test_closures_change_access_without_relocating_homes_or_sites(self):
        closed = tuple((e[0], e[1]) for e in self.map["walkEdges"])
        original = WalkingNetwork(self.map, ())
        disrupted = WalkingNetwork(self.map, closed)
        self.assertEqual(original.usable, disrupted.usable)
        self.assertEqual(original.nearest([0, 0]), disrupted.nearest([0, 0]))
        self.assertIsNone(disrupted.route(0, 1, 1.4))
        self.assertEqual(original.route(0, 1, 1.4)["seconds"], 12 + 286)
        trace = run(self.map, 10, closed_edges=closed)
        self.assertTrue(any(x["reason"] == "inaccessible_route" for e in trace["events"] for x in e.get("excluded", [])))

    def test_invalid_population_is_explicit(self):
        with self.assertRaises(ValueError):
            run(self.map, True)
        with self.assertRaises(ValueError):
            run(self.map, 0)

    def test_frozen_manifest_pins_today_and_five_year_decisions(self):
        manifest = load_manifest()
        self.assertEqual(manifest["start_date"], "2026-10-18")
        self.assertEqual(manifest["timezone"], "America/Toronto")
        self.assertEqual(manifest["horizon_months"], 60)
        self.assertEqual(manifest["planning"]["first_decision_date"], "2026-11-01")
        self.assertEqual(manifest["planning"]["decision_count"], 60)
        self.assertEqual(manifest["end_date_exclusive"], "2031-10-18")

    def test_calendar_day_runner_is_deterministic_and_respects_dst(self):
        baseline = run_day(self.map, "2026-10-18", population=8)
        self.assertEqual(baseline, run_day(self.map, "2026-10-18", population=8))
        self.assertEqual(baseline["horizon_seconds"], 86400)
        self.assertEqual(baseline["start_time"], "2026-10-18T00:00:00-04:00")
        self.assertEqual(baseline["accounting"]["invariant_problems"], [])
        self.assertEqual(baseline["accounting"]["imported_grams"],
                         baseline["accounting"]["remaining_grams"] + baseline["accounting"]["consumed_grams"])
        times = [event["simulation_time"] for event in baseline["events"]]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(0 <= second <= baseline["horizon_seconds"] for second in times))
        spring = run_day(self.map, "2026-03-08", population=1)
        fall = run_day(self.map, "2026-11-01", population=1)
        self.assertEqual(spring["horizon_seconds"], 23 * 3600)
        self.assertEqual(fall["horizon_seconds"], 25 * 3600)


if __name__ == "__main__":
    unittest.main()
