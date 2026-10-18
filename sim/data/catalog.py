"""Read and validate the small, versioned civic-data source register."""

from __future__ import annotations

import json
from pathlib import Path


class CatalogError(ValueError):
    """Raised when source metadata is inconsistent with the pipeline contract."""


def registry_path() -> Path:
    return Path(__file__).resolve().parent / "sources.json"


def schema_path() -> Path:
    return Path(__file__).resolve().parent / "dataset_schema.json"


def load_registry() -> dict:
    registry = json.loads(registry_path().read_text(encoding="utf-8"))
    if registry.get("schema_version") != 1:
        raise CatalogError("unsupported civic-data source register version")
    sources = registry.get("sources")
    if not isinstance(sources, list) or not sources:
        raise CatalogError("source register must contain at least one source")
    ids = [source.get("id") for source in sources]
    if any(not isinstance(source_id, str) or not source_id for source_id in ids):
        raise CatalogError("each source needs a non-empty id")
    if len(ids) != len(set(ids)):
        raise CatalogError("source ids must be unique")
    for source in sources:
        if source.get("connector") != "arcgis_feature_layer":
            raise CatalogError(f"unsupported connector for {source['id']}")
        if not source.get("layer_url", "").startswith("https://"):
            raise CatalogError(f"{source['id']} must use an HTTPS layer URL")
        field_map = source.get("field_map")
        if not isinstance(field_map, dict) or "source_record_id" not in field_map:
            raise CatalogError(f"{source['id']} needs a source_record_id mapping")
    return registry


def source_by_id(source_id: str, registry: dict | None = None) -> dict:
    catalog = registry or load_registry()
    for source in catalog["sources"]:
        if source["id"] == source_id:
            return source
    raise CatalogError(f"unknown source id: {source_id}")
