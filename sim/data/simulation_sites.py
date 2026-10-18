"""Prepare cited City-listed locations for the downtown pedestrian simulation."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from sim.data.retrieval import retrieve


ROLE_ANCHORS = {
    "retail-west": {"dataset_id": "toronto_supermarkets", "point": (-750.0, 0.0)},
    "retail-east": {"dataset_id": "toronto_supermarkets", "point": (650.0, 100.0)},
    "support": {"dataset_id": "toronto_food_support_sites", "point": (-150.0, -250.0)},
    "school": {"dataset_id": "toronto_education_sites", "point": (450.0, -550.0)},
}

_FRONTEND_ORIGIN = (-79.385, 43.65)
_SCHOOL_BOARD_CODES = {"EP", "ES", "FP"}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_file(root: Path, relative_path: str, expected: str, label: str) -> Path:
    path = root.joinpath(*relative_path.replace("\\", "/").split("/"))
    if not path.is_file() or _sha256(path) != expected:
        raise ValueError(f"{label} is missing or has a hash mismatch: {path}")
    return path


def _load_source_rows(snapshot_dir: Path, manifest: dict) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    datasets = {row["dataset_id"]: row for row in manifest.get("datasets", [])}
    source_rows: dict[str, list[dict]] = {}
    for source_id in sorted({item["dataset_id"] for item in ROLE_ANCHORS.values()}):
        dataset = datasets.get(source_id)
        if not dataset or dataset.get("status") != "complete":
            raise ValueError(f"required source is not complete: {source_id}")
        for raw in dataset.get("raw_files", []):
            _verify_file(snapshot_dir, raw["path"], raw["sha256"], f"{source_id} raw source")
        normalized_path = _verify_file(
            snapshot_dir,
            dataset["normalized_file"],
            dataset["normalized_sha256"],
            f"{source_id} normalized source",
        )
        rows = []
        with normalized_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid normalized record in {normalized_path}:{line_number}") from exc
                if row.get("source_id") != source_id:
                    raise ValueError(f"wrong source id in {normalized_path}:{line_number}")
                rows.append(row)
        if len(rows) != dataset.get("accepted_record_count"):
            raise ValueError(f"normalized row count mismatch for {source_id}")
        source_rows[source_id] = rows
    return datasets, source_rows


def _project(lon: float, lat: float, origin: tuple[float, float]) -> tuple[float, float]:
    return (
        (lon - origin[0]) * 111320 * math.cos(math.radians(origin[1])),
        (origin[1] - lat) * 111320,
    )


def _is_school(row: dict) -> bool:
    code = str(row.get("category_code") or "").upper()
    name = str(row.get("site_name") or "").casefold()
    return (
        code in _SCHOOL_BOARD_CODES
        and "school" in name
        and not any(token in name for token in ("gymnasium", "gym", "choral bldg", "administration"))
    )


def prepare_simulation_site_snapshot(
    source_snapshot_dir: Path,
    map_path: Path,
    output_path: Path,
) -> Path:
    """Select the nearest source-listed sites to the current scenario anchors.

    Only location and label fields come from the City snapshot. The simulation's
    prices, hours, inventory, eligibility, capacity, and service rules stay as
    declared scenario assumptions.
    """
    source_snapshot_dir = Path(source_snapshot_dir).resolve()
    map_path = Path(map_path).resolve()
    output_path = Path(output_path)
    manifest_path = source_snapshot_dir / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    manifest = _read_json(manifest_path)
    if manifest.get("complete") is not True:
        raise ValueError(f"source snapshot is incomplete: {manifest.get('snapshot_id')}")
    for name, expected in (
        ("dashboard.json", manifest.get("dashboard_sha256")),
        ("simulation_inputs.json", manifest.get("simulation_inputs_sha256")),
        ("documents.jsonl", manifest.get("documents_sha256")),
    ):
        if not isinstance(expected, str) or _sha256(source_snapshot_dir / name) != expected:
            raise ValueError(f"candidate snapshot output hash mismatch: {name}")

    datasets, source_rows = _load_source_rows(source_snapshot_dir, manifest)
    map_raw = map_path.read_bytes()
    try:
        district = json.loads(map_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid map JSON: {map_path}") from exc
    origin_values = district.get("origin")
    bounds = district.get("bounds")
    if not isinstance(origin_values, list) or len(origin_values) != 2:
        raise ValueError("map input must declare its longitude/latitude origin")
    if not isinstance(bounds, list) or len(bounds) != 4 or not district.get("walkNodes"):
        raise ValueError("map input must declare scene bounds and a walking graph")
    origin = (float(origin_values[0]), float(origin_values[1]))
    if any(abs(a - b) > 1e-9 for a, b in zip(origin, _FRONTEND_ORIGIN)):
        raise ValueError("map origin differs from the browser's fixed coordinate transform")
    min_x, min_z, max_x, max_z = map(float, bounds)
    map_hash = hashlib.sha256(map_raw).hexdigest()
    manifest_hash = hashlib.sha256(manifest_raw).hexdigest()

    projected: dict[str, list[dict]] = {}
    counts_in_map: dict[str, int] = {}
    for source_id, rows in source_rows.items():
        in_map = []
        for row in rows:
            lat, lon = row.get("latitude_deg"), row.get("longitude_deg")
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                continue
            point = _project(float(lon), float(lat), origin)
            if min_x <= point[0] <= max_x and min_z <= point[1] <= max_z:
                in_map.append({**row, "scene_point": [round(point[0], 2), round(point[1], 2)]})
        projected[source_id] = in_map
        counts_in_map[source_id] = len(in_map)

    selected: dict[str, dict] = {}
    selected_record_ids: set[str] = set()
    for role, specification in ROLE_ANCHORS.items():
        source_id = specification["dataset_id"]
        anchor = specification["point"]
        candidates = projected[source_id]
        if role == "school":
            candidates = [row for row in candidates if _is_school(row)]
        candidates = [row for row in candidates if row["site_id"] not in selected_record_ids]
        if not candidates:
            raise ValueError(f"no eligible {role} records fall inside the map bounds")
        row = min(
            candidates,
            key=lambda item: (
                math.dist(item["scene_point"], anchor),
                item["site_id"],
            ),
        )
        selected_record_ids.add(row["site_id"])
        dataset = datasets[source_id]
        query = " ".join(
            value for value in (
                dataset.get("source_layer_name"),
                row.get("site_name"),
                row.get("service_type"),
                row.get("address"),
            ) if value
        )
        rag = retrieve(
            query,
            source_snapshot_dir,
            top_k=10,
            dataset_id=source_id,
            record_id=row["source_record_id"],
        )
        retrieved = next(
            (item for item in rag["results"] if item.get("record_id") == row["source_record_id"]),
            None,
        )
        if retrieved is None:
            raise ValueError(f"RAG retrieval did not return selected source record {row['site_id']}")

        source_field = dataset.get("field_map", {}).get("source_record_id", {}).get("source", "OBJECTID")
        where = f"{source_field}={row['source_record_id']}"
        record_url = dataset["resource_url"] + "?" + urlencode({
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "f": "pjson",
        })
        selected[role] = {
            "role": role,
            "source_id": source_id,
            "source_record_id": row["source_record_id"],
            "source_site_id": row["site_id"],
            "site_name": row.get("site_name"),
            "service_type": row.get("service_type"),
            "address": row.get("address"),
            "scene_point": row["scene_point"],
            "distance_to_illustrative_anchor_m": round(math.dist(row["scene_point"], anchor), 1),
            "source_url": dataset["source_url"],
            "source_record_url": record_url,
            "publisher": dataset["publisher"],
            "licence_url": dataset.get("licence_url"),
            "licence_status": dataset.get("licence_status"),
            "attribution": dataset.get("attribution"),
            "source_snapshot_id": manifest["snapshot_id"],
            "source_retrieved_at": row["retrieved_at"],
            "source_published_at": row.get("published_at"),
            "source_updated_at": dataset.get("source_updated_at"),
            "source_vintage_status": "reported" if dataset.get("source_updated_at") else "unknown",
            "location_evidence_state": row["evidence_state"],
            "listing_current_status": "unknown",
            "operations_evidence_state": "illustrative",
            "quality_flags": sorted(set(row.get("quality_flags", [])) | set(dataset.get("quality_flags", []))),
            "retrieval": {
                "query": rag["query"],
                "method": rag["retrieval_method"],
                "doc_id": retrieved["doc_id"],
                "rank": retrieved["rank"],
                "score": retrieved["score"],
                "text": retrieved["text"],
                "citation": next(
                    citation for citation in rag["citations"]
                    if citation["doc_id"] == retrieved["doc_id"]
                ),
            },
        }

    local = {"EP": "English Public", "ES": "English Separate", "FP": "French Public"}
    for role, item in selected.items():
        if role.startswith("retail-"):
            item["display_name"] = f"City-listed supermarket - {item['site_name']}"
        elif role == "support":
            item["display_name"] = "City-listed food support - " + str(item["site_name"] or item["service_type"])
            if item.get("service_type"):
                item["display_name"] += f" ({item['service_type']})"
        else:
            item["display_name"] = f"City-listed school - {item['site_name']}"
            item["school_type_label"] = local.get(
                next((row.get("category_code") for row in projected["toronto_education_sites"]
                      if row.get("site_id") == item["source_site_id"]), None),
                "school board type not mapped",
            )

    try:
        map_label = map_path.relative_to(Path(__file__).resolve().parents[2]).as_posix()
    except ValueError:
        map_label = map_path.name
    output = {
        "schema_version": 1,
        "snapshot_id": "toronto-downtown-sites-v3",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "geography_id": "downtown-toronto-map-core",
        "spatial_scope": "City-listed points filtered to the bounds of the frozen downtown Toronto OSM map and walking graph.",
        "source_snapshot_id": manifest["snapshot_id"],
        "source_snapshot_manifest_sha256": manifest_hash,
        "source_snapshot_retrieved_at": manifest["retrieved_at"],
        "source_snapshot_spatial_scope": manifest["spatial_scope"],
        "map_path": map_label,
        "map_sha256": map_hash,
        "map_origin_lon_lat": list(origin),
        "map_bounds_xz_m": [min_x, min_z, max_x, max_z],
        "coordinate_transform": "x=(longitude-origin_lon)*111320*cos(origin_lat); z=(origin_lat-latitude)*111320",
        "selection_method": "Nearest source-listed record to each frozen illustrative role anchor in projected map metres, restricted to map bounds; source records are unique across roles.",
        "counts_in_map_bounds": counts_in_map,
        "sites": selected,
        "evidence_limits": [
            "A source-listed point does not establish that the location is currently operating.",
            "The source observation date is unavailable; retrieval time is not an observation date.",
            "Prices, inventory, hours, capacity, eligibility, service quality, and behavior remain illustrative.",
            "School locations do not establish school-meal participation or reach.",
            "The selected sites are nearest matches to scenario anchors, not a representative sample of Toronto services.",
            "The source registry flags the source-layer license terms for review before publication.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
    except FileExistsError as exc:
        raise FileExistsError(f"refusing to overwrite immutable site snapshot: {output_path}") from exc
    return output_path


def load_simulation_site_snapshot(path: Path) -> tuple[dict, str]:
    """Load a frozen derived snapshot and return its content hash."""
    path = Path(path)
    raw = path.read_bytes()
    value = json.loads(raw)
    required_roles = set(ROLE_ANCHORS)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"unsupported simulation site snapshot: {path}")
    sites = value.get("sites")
    if not isinstance(sites, dict) or set(sites) != required_roles:
        raise ValueError("simulation site snapshot must contain exactly the registered roles")
    for role, site in sites.items():
        point = site.get("scene_point")
        retrieval = site.get("retrieval")
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not all(isinstance(number, (int, float)) and math.isfinite(number) for number in point)
            or not site.get("source_id")
            or not site.get("source_record_id")
            or not isinstance(retrieval, dict)
            or retrieval.get("citation", {}).get("record_id") != site.get("source_record_id")
        ):
            raise ValueError(f"invalid source location or citation for role: {role}")
    return value, hashlib.sha256(raw).hexdigest()
