"""Load the literal fixture's inputs. Expected outputs live in the tests."""

from __future__ import annotations

import json
from pathlib import Path

from sim.core.catalog import _keys, _refuse_floats
from sim.core.reporting import FieldError, InputError
from sim.core.version import SCENARIO_SCHEMA_VERSION


def fixture_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "fixture_scenario.json"


def load_fixture_spec(path: Path | None = None) -> dict:
    data = json.loads((path or fixture_path()).read_text(encoding="utf-8"))
    errors = validate_fixture_spec(data)
    if errors:
        raise InputError(errors)
    return data


def validate_fixture_spec(data: object) -> tuple[FieldError, ...]:
    errors: list[FieldError] = []
    if not isinstance(data, dict):
        return (FieldError("scenario", "must be an object"),)
    _refuse_floats(data, "scenario", errors)
    _keys(
        data,
        {
            "schema_version",
            "scenario_id",
            "label",
            "evidence_state",
            "cutoff",
            "timezone",
            "epoch",
            "catalog_id",
            "price_base_month",
            "planning_ref",
            "actors",
            "external_account_id",
            "external_owner_id",
            "opening_cash_cents",
            "opening_lots",
            "subsidy_example",
        },
        "scenario",
        errors,
    )
    if data.get("schema_version") != SCENARIO_SCHEMA_VERSION:
        errors.append(FieldError("schema_version", "unsupported scenario schema"))
    if data.get("evidence_state") != "illustrative":
        errors.append(FieldError("evidence_state", "fixture inputs are illustrative"))
    if data.get("price_base_month") is not None:
        errors.append(FieldError("price_base_month", "nominal fixture cash has no price base"))
    if data.get("catalog_id") != "sim6ix-basket-v1":
        errors.append(FieldError("catalog_id", "fixture must use the frozen catalog"))
    return tuple(errors)
