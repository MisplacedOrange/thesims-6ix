"""District code reaches the kernel only through sim.core."""

import ast
import unittest
from pathlib import Path

import bootstrap  # noqa: F401

import sim.district as district

ROOT = Path(__file__).resolve().parents[1]
OWNED = {"sim.policies", "sim.logistics", "sim.behavior", "sim.experiments"}


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append(node.module)
    return found


class BoundaryTest(unittest.TestCase):
    def test_public_names(self) -> None:
        self.assertEqual(
            district.__all__,
            (
                "run_baseline",
                "BaselineReport",
                "BaselineResult",
                "Check",
                "Trip",
                "load_snapshot",
                "Snapshot",
                "SnapshotError",
                "build_population",
                "attendance_present",
                "Household",
                "Member",
                "Population",
                "Pupil",
                "shortest_path",
                "Network",
                "Edge",
                "score_option",
                "choice_noise",
                "choose",
                "plan_household",
                "DayPlan",
                "ScoredOption",
            ),
        )
        for name in district.__all__:
            self.assertTrue(hasattr(district, name), name)

    def test_imports_stay_on_the_public_kernel(self) -> None:
        for path in ROOT.glob("*.py"):
            for module in _imported_modules(path):
                if module in OWNED or any(module.startswith(prefix + ".") for prefix in OWNED):
                    self.fail(f"{path.name} imports {module}")
                if module.startswith("sim.core."):
                    self.fail(f"{path.name} imports private kernel module {module}")
                if module.startswith("sim.") and module != "sim.core" and not module.startswith("sim.district"):
                    self.fail(f"{path.name} imports {module}")


if __name__ == "__main__":
    unittest.main()
