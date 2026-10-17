"""Frozen inputs: raw hashes, integer units, and the planning baseline label."""

import ast
import hashlib
import json
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

from sim.district.snapshot import SnapshotError, _refuse_floats, load_snapshot

ROOT = Path(__file__).resolve().parents[3]


class SnapshotTest(unittest.TestCase):
    def test_manifest_pins_raw_bytes(self) -> None:
        snapshot = load_snapshot()
        manifest_ids = [row["dataset_id"] for row in snapshot.manifest["datasets"]]
        self.assertEqual(
            manifest_ids,
            ["snapshot", "controls", "behavior", "places", "network", "calendar", "catalog"],
        )
        self.assertNotIn("manifest", manifest_ids)
        for row in snapshot.manifest["datasets"]:
            raw = (ROOT / row["package_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["raw_sha256"])
            self.assertEqual(row["evidence_state"], "illustrative")
            self.assertEqual(row["quality_flags"], ["illustrative", "not_for_calibration"])
            self.assertIsNone(row["price_base_month"])
            self.assertIsNone(row["published_at"])
            self.assertIsNone(row["source_url"])
        self.assertEqual(snapshot.header["catalog_id"], snapshot.catalog.catalog_id)
        self.assertEqual(snapshot.catalog.sha256, next(row["raw_sha256"] for row in snapshot.manifest["datasets"] if row["dataset_id"] == "catalog"))
        self.assertIsNone(snapshot.header["price_base_month"])
        self.assertEqual(len(snapshot.days), 7)
        self.assertEqual(snapshot.network.edges[0].walk_seconds, 600)

    def test_header_matches_planning_baseline(self) -> None:
        snapshot = load_snapshot()
        planning = json.loads((ROOT / "planning" / "scenarios.json").read_text(encoding="utf-8"))
        baseline = next(item for item in planning["scenarios"] if item["id"] == "baseline")
        self.assertEqual(snapshot.header["planning_scenario_id"], "baseline")
        self.assertEqual(snapshot.header["planning_mode"], baseline["mode"])
        self.assertEqual(snapshot.header["planning_enabled"], baseline["enabled"])
        self.assertEqual(baseline["mode"], "observed_service_with_explicit_unknowns")

    def test_floats_and_dollar_keys_are_refused(self) -> None:
        with self.assertRaises(SnapshotError):
            _refuse_floats({"price_cents": 1.5}, "sample")
        with self.assertRaises(SnapshotError):
            _refuse_floats({"shelf_dollars": 4}, "sample")
        _refuse_floats({"price_cents_per_100g": 70, "note": "points per dollar"}, "sample")

    def test_district_sources_parse(self) -> None:
        for path in (ROOT / "sim" / "district").rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
