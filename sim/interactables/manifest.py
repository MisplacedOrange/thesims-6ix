"""Pinned scenario-manifest loading for reproducible simulation runs."""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "planning" / "scenarios" / "toronto-long-horizon-v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def load_manifest(path: Path = DEFAULT_MANIFEST, verify_inputs: bool = True) -> dict:
    """Load and validate a fully pinned scenario manifest.

    Relative input paths are rooted at the repository, never at the caller's
    current working directory. No simulation date or value is inferred from
    the machine clock.
    """
    path = Path(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read scenario manifest {path}: {exc}") from exc

    required = {
        "schema_version", "scenario_id", "created_at_utc", "start_date", "timezone",
        "horizon_months", "end_date_exclusive", "planning", "seed", "population",
        "day_clock", "inputs", "funding", "model", "known_unknowns",
    }
    if not isinstance(manifest, dict) or set(manifest) != required:
        raise ValueError("scenario manifest has missing or unexpected top-level fields")
    if manifest["schema_version"] != 1:
        raise ValueError("unsupported scenario manifest schema_version")
    if not isinstance(manifest["scenario_id"], str) or not manifest["scenario_id"]:
        raise ValueError("scenario_id must be non-empty text")
    if not isinstance(manifest["seed"], int) or isinstance(manifest["seed"], bool):
        raise ValueError("seed must be an integer")

    try:
        start_date = date.fromisoformat(manifest["start_date"])
        ZoneInfo(manifest["timezone"])
    except (TypeError, ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("start_date or timezone is invalid") from exc
    horizon_months = manifest["horizon_months"]
    if not isinstance(horizon_months, int) or isinstance(horizon_months, bool) or horizon_months <= 0:
        raise ValueError("horizon_months must be a positive integer")
    expected_end = _add_months(start_date, horizon_months).isoformat()
    if manifest["end_date_exclusive"] != expected_end:
        raise ValueError(f"end_date_exclusive must be {expected_end} for this start date and horizon")

    planning = manifest["planning"]
    if not isinstance(planning, dict):
        raise ValueError("planning must be an object")
    try:
        first_decision = date.fromisoformat(planning["first_decision_date"])
        expected_decisions = planning["decision_count"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("planning decision schedule is incomplete") from exc
    decision_dates = []
    current = date(first_decision.year, first_decision.month, 1)
    end_date = date.fromisoformat(expected_end)
    while current < end_date:
        decision_dates.append(current)
        current = _add_months(current, 1)
    if (first_decision != decision_dates[0] if decision_dates else True):
        raise ValueError("first_decision_date must be a calendar-month boundary before the horizon end")
    if expected_decisions != len(decision_dates):
        raise ValueError(f"decision_count must be {len(decision_dates)} for the pinned monthly schedule")
    if first_decision <= start_date:
        raise ValueError("first_decision_date must follow the scenario start date")

    if verify_inputs:
        inputs = manifest["inputs"]
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError("inputs must pin the files used by the scenario")
        for name, record in inputs.items():
            if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
                raise ValueError(f"input {name} must declare path and sha256")
            input_path = ROOT / record["path"]
            if not input_path.is_file():
                raise ValueError(f"pinned input {name} is missing: {input_path}")
            if _sha256(input_path) != record["sha256"]:
                raise ValueError(f"pinned input {name} hash does not match {input_path}")

    return manifest
