"""Shortest paths minimize declared walk seconds."""

import unittest

import bootstrap  # noqa: F401

from sim.district.network import Edge, Network, shortest_path
from sim.district.snapshot import load_snapshot


class NetworkTest(unittest.TestCase):
    def test_time_beats_a_shorter_metre_path(self) -> None:
        network = Network(
            nodes=("home", "near", "far"),
            edges=(
                Edge("long-fast", "home", "far", 10000, 10),
                Edge("short-slow-a", "home", "near", 1, 100),
                Edge("short-slow-b", "near", "far", 1, 100),
            ),
        )
        path, seconds = shortest_path(network, "home", "far")
        self.assertEqual(path, ("home", "far"))
        self.assertEqual(seconds, 10)

    def test_equal_time_breaks_to_the_smaller_node_sequence(self) -> None:
        network = Network(
            nodes=("a", "b", "c", "d"),
            edges=(
                Edge("ab", "a", "b", 5, 10),
                Edge("ac", "a", "c", 5, 10),
                Edge("bd", "b", "d", 5, 10),
                Edge("cd", "c", "d", 5, 10),
            ),
        )
        path, seconds = shortest_path(network, "a", "d")
        self.assertEqual(path, ("a", "b", "d"))
        self.assertEqual(seconds, 20)

    def test_frozen_district_legs(self) -> None:
        network = load_snapshot().network
        expected = {
            ("area-a", "store-a"): 120,
            ("area-a", "store-b"): 720,
            ("area-a", "school-a"): 180,
            ("area-a", "store-d"): 1980,
        }
        for (origin, destination), seconds in expected.items():
            found = shortest_path(network, origin, destination)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found[1], seconds)
        self.assertGreater(expected[("area-a", "store-d")], 1500)


if __name__ == "__main__":
    unittest.main()
