"""Carrier limits, journey timing, stable hashes, and animation cues."""

import ast
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.core import CAD_CENTS, GRAMS, Metric, invariant_problems, lots_for_owner
from sim.logistics import (
    Carrier,
    RunIdentity,
    animation_cues,
    compare_paired,
    plan_loads,
    queue_positions,
    run_integrated,
)

ROOT = Path(__file__).resolve().parents[1]


class QueueAndCarrierTest(unittest.TestCase):
    def test_admission_is_stable_and_not_id_order(self) -> None:
        actors = ("hh-c", "hh-a", "hh-b")
        first = queue_positions(17, "van-morning", actors)
        second = queue_positions(17, "van-morning", actors)
        self.assertEqual(first, second)
        self.assertNotEqual(tuple(actor for actor, _rank in first), tuple(sorted(actors)))

    def test_payload_misses_the_second_order_whole(self) -> None:
        carrier = Carrier("van-1", 1000, 0, 86400)
        plan = plan_loads(carrier, (("order-a", 600), ("order-b", 600)), 100)
        self.assertEqual([(item.order_id, item.status) for item in plan], [("order-a", "loaded"), ("order-b", "missed_payload")])
        self.assertEqual(sum(item.grams for item in plan if item.status == "loaded"), 600)

    def test_outside_the_shift_loads_nothing(self) -> None:
        carrier = Carrier("van-1", 1000, 1000, 2000)
        plan = plan_loads(carrier, (("order-a", 100),), 2000)
        self.assertEqual(plan[0].status, "missed_shift")


class IntegratedTest(unittest.TestCase):
    def test_hash_and_cues(self) -> None:
        first = run_integrated(17)
        second = run_integrated(17)
        other = run_integrated(18)
        self.assertEqual(invariant_problems(first.state), ())
        self.assertEqual(first.state_hash, second.state_hash)
        self.assertEqual(first.cues, second.cues)
        self.assertNotEqual(first.state_hash, other.state_hash)
        self.assertEqual(len(first.loaded_order_ids), 1)
        self.assertEqual(len(first.missed_order_ids), 2)
        self.assertEqual(first.arrival_second, 220)
        kinds = [cue.kind for cue in first.cues]
        self.assertEqual(kinds.count("queue_admission"), 3)
        self.assertEqual(kinds.count("trip_started"), 1)
        self.assertEqual(kinds.count("trip_arrived"), 1)
        self.assertEqual(kinds.count("purchase"), 1)
        self.assertEqual(kinds.count("processing_batch"), 1)
        self.assertEqual(kinds.count("meal_served"), 1)
        event_ids = {event.event_id for event in first.events}
        self.assertTrue(all(cue.event_id in event_ids for cue in first.cues))
        travelling = [lot for lot in first.state.lots if lot.journey_id is not None]
        self.assertEqual(travelling, [])
        school = lots_for_owner(first.state, "school-a")
        self.assertEqual(sum(lot.grams for lot in school), 600)
        self.assertEqual(sum(lot.grams for lot in lots_for_owner(first.state, "hh-shop")), 400)
        self.assertEqual(first.state.consumed_grams, 200)
        self.assertEqual(first.state.loss_grams, 100)
        self.assertEqual(animation_cues(first.events), first.cues)

    def test_pair_rejects_a_different_population(self) -> None:
        metrics = (Metric("grams", 1, GRAMS),)
        identity = RunIdentity("0.1.0", "a" * 64, "pop-1")
        self.assertEqual(compare_paired(metrics, metrics, identity, identity), (Metric("grams", 0, GRAMS),))
        with self.assertRaises(ValueError):
            compare_paired(metrics, metrics, identity, RunIdentity("0.1.0", "a" * 64, "pop-2"))
        with self.assertRaises(ValueError):
            compare_paired(metrics, (Metric("grams", 1, CAD_CENTS),), identity, identity)


class LogisticsBoundaryTest(unittest.TestCase):
    def test_imports(self) -> None:
        allowed = ("sim.core", "sim.logistics")
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.startswith("sim.core."):
                        self.fail(name)
                    if name.startswith("sim.") and not any(name == item or name.startswith(item + ".") for item in allowed):
                        self.fail(name)


if __name__ == "__main__":
    unittest.main()
