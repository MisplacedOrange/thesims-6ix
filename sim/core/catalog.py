"""Frozen product catalog loader.

The catalog file is an input snapshot. Its raw SHA-256 is stored on each run
so a later edit cannot be mistaken for the catalog a run already used.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sim.core.reporting import FieldError, InputError
from sim.core.version import CATALOG_SCHEMA_VERSION

_STORAGE = frozenset({"ambient", "refrigerated", "frozen"})
_ROLES = frozenset({"rescue_input", "basket_component", "recipe_output"})
_REMAINDERS = frozenset({"process_loss", "edible_output"})


@dataclass(frozen=True, slots=True)
class Product:
    product_id: str
    label: str
    storage_class: str
    pricing_unit: str
    illustrative_retail_cents_per_100g: int
    illustrative_procurement_cents_per_100g: int
    illustrative_max_storage_seconds: int
    recipe_roles: tuple[str, ...]
    evidence_state: str
    note: str


@dataclass(frozen=True, slots=True)
class Recipe:
    recipe_id: str
    input_product_id: str
    output_product_id: str
    edible_numerator: int
    edible_denominator: int
    remainder_to: str
    evidence_state: str
    note: str


@dataclass(frozen=True, slots=True)
class Catalog:
    schema_version: int
    catalog_id: str
    frozen_on: str
    evidence_state: str
    note: str
    products: tuple[Product, ...]
    recipes: tuple[Recipe, ...]
    sha256: str


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "catalog.json"


def load_catalog(path: Path | None = None) -> Catalog:
    catalog_path = path or default_catalog_path()
    raw = catalog_path.read_bytes()
    data = json.loads(raw)
    errors = validate_catalog(data)
    if errors:
        raise InputError(errors)
    products = tuple(
        Product(
            product_id=item["product_id"],
            label=item["label"],
            storage_class=item["storage_class"],
            pricing_unit=item["pricing_unit"],
            illustrative_retail_cents_per_100g=item["illustrative_retail_cents_per_100g"],
            illustrative_procurement_cents_per_100g=item["illustrative_procurement_cents_per_100g"],
            illustrative_max_storage_seconds=item["illustrative_max_storage_seconds"],
            recipe_roles=tuple(item["recipe_roles"]),
            evidence_state=item["evidence_state"],
            note=item["note"],
        )
        for item in data["products"]
    )
    recipes = tuple(
        Recipe(
            recipe_id=item["recipe_id"],
            input_product_id=item["input_product_id"],
            output_product_id=item["output_product_id"],
            edible_numerator=item["edible_numerator"],
            edible_denominator=item["edible_denominator"],
            remainder_to=item["remainder_to"],
            evidence_state=item["evidence_state"],
            note=item["note"],
        )
        for item in data["recipes"]
    )
    return Catalog(
        schema_version=data["schema_version"],
        catalog_id=data["catalog_id"],
        frozen_on=data["frozen_on"],
        evidence_state=data["evidence_state"],
        note=data["note"],
        products=products,
        recipes=recipes,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def validate_catalog(data: object) -> tuple[FieldError, ...]:
    errors: list[FieldError] = []
    if not isinstance(data, dict):
        return (FieldError("catalog", "must be an object"),)
    _refuse_floats(data, "catalog", errors)
    expected = {
        "schema_version",
        "catalog_id",
        "frozen_on",
        "evidence_state",
        "note",
        "products",
        "recipes",
    }
    _keys(data, expected, "catalog", errors)
    if data.get("schema_version") != CATALOG_SCHEMA_VERSION:
        errors.append(FieldError("schema_version", f"must be {CATALOG_SCHEMA_VERSION}"))
    if data.get("catalog_id") != "sim6ix-basket-v1":
        errors.append(FieldError("catalog_id", "the frozen catalog id is sim6ix-basket-v1"))
    if data.get("evidence_state") != "illustrative":
        errors.append(FieldError("evidence_state", "this freeze is illustrative"))
    products = data.get("products")
    if not isinstance(products, list) or not products:
        errors.append(FieldError("products", "at least one product is required"))
        return tuple(errors)
    seen: set[str] = set()
    for index, product in enumerate(products):
        field = f"products[{index}]"
        if not isinstance(product, dict):
            errors.append(FieldError(field, "must be an object"))
            continue
        _keys(
            product,
            {
                "product_id",
                "label",
                "storage_class",
                "pricing_unit",
                "illustrative_retail_cents_per_100g",
                "illustrative_procurement_cents_per_100g",
                "illustrative_max_storage_seconds",
                "recipe_roles",
                "evidence_state",
                "note",
            },
            field,
            errors,
        )
        product_id = product.get("product_id")
        if not isinstance(product_id, str) or product_id in seen:
            errors.append(FieldError(f"{field}.product_id", "must be a unique string"))
        else:
            seen.add(product_id)
        if product.get("storage_class") not in _STORAGE:
            errors.append(FieldError(f"{field}.storage_class", "unknown storage class"))
        if product.get("pricing_unit") != "100g":
            errors.append(FieldError(f"{field}.pricing_unit", "pricing unit must be 100g"))
        if product.get("evidence_state") != "illustrative":
            errors.append(FieldError(f"{field}.evidence_state", "must be illustrative"))
        roles = product.get("recipe_roles")
        if not isinstance(roles, list) or any(role not in _ROLES for role in roles):
            errors.append(FieldError(f"{field}.recipe_roles", "unknown recipe role"))
        for money in (
            "illustrative_retail_cents_per_100g",
            "illustrative_procurement_cents_per_100g",
            "illustrative_max_storage_seconds",
        ):
            if isinstance(product.get(money), bool) or not isinstance(product.get(money), int) or product.get(money) < 0:
                errors.append(FieldError(f"{field}.{money}", "must be a non-negative integer"))
    recipes = data.get("recipes")
    if not isinstance(recipes, list):
        errors.append(FieldError("recipes", "must be a list"))
        return tuple(errors)
    for index, recipe in enumerate(recipes):
        field = f"recipes[{index}]"
        if not isinstance(recipe, dict):
            errors.append(FieldError(field, "must be an object"))
            continue
        _keys(
            recipe,
            {
                "recipe_id",
                "input_product_id",
                "output_product_id",
                "edible_numerator",
                "edible_denominator",
                "remainder_to",
                "evidence_state",
                "note",
            },
            field,
            errors,
        )
        if recipe.get("input_product_id") not in seen or recipe.get("output_product_id") not in seen:
            errors.append(FieldError(field, "recipe products must be in the catalog"))
        numerator = recipe.get("edible_numerator")
        denominator = recipe.get("edible_denominator")
        if (
            isinstance(numerator, bool)
            or isinstance(denominator, bool)
            or not isinstance(numerator, int)
            or not isinstance(denominator, int)
            or numerator < 0
            or denominator <= 0
            or numerator > denominator
        ):
            errors.append(FieldError(field, "edible ratio must be a fraction between 0 and 1"))
        if recipe.get("remainder_to") not in _REMAINDERS:
            errors.append(FieldError(f"{field}.remainder_to", "must be process_loss or edible_output"))
        if recipe.get("evidence_state") != "illustrative":
            errors.append(FieldError(f"{field}.evidence_state", "must be illustrative"))
    return tuple(errors)


def _keys(data: dict, expected: set[str], field: str, errors: list[FieldError]) -> None:
    missing = expected - set(data)
    extra = set(data) - expected
    if missing or extra:
        errors.append(FieldError(field, f"keys mismatch missing={sorted(missing)} extra={sorted(extra)}"))


def _refuse_floats(value: object, field: str, errors: list[FieldError]) -> None:
    if isinstance(value, float):
        errors.append(FieldError(field, "float values are refused; use integer cents, grams, or seconds"))
    elif isinstance(value, dict):
        for key, item in value.items():
            if "dollar" in str(key).lower():
                errors.append(FieldError(f"{field}.{key}", "dollar fields are refused; use integer cents"))
            _refuse_floats(item, f"{field}.{key}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _refuse_floats(item, f"{field}[{index}]", errors)
