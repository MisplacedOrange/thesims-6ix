"""Acquire immutable candidate snapshots from the registered Toronto GIS layers."""

from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sim.data.catalog import load_registry, registry_path, schema_path, source_by_id


class DataPipelineError(ValueError):
    """Raised when a public source cannot meet the declared dataset contract."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _request(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TheSims6ix-Toronto-Simulation/0.1 (civic open data)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DataPipelineError(f"request failed for {url}: {exc}") from exc


def _json_response(raw: bytes, url: str) -> dict:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataPipelineError(f"non-JSON response from {url}") from exc
    if not isinstance(payload, dict):
        raise DataPipelineError(f"expected a JSON object from {url}")
    if "error" in payload:
        error = payload["error"]
        detail = error.get("message", error) if isinstance(error, dict) else error
        raise DataPipelineError(f"ArcGIS error from {url}: {detail}")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _field_value(attributes: dict, mapping: dict) -> Any:
    if "value" in mapping:
        value = mapping["value"]
    else:
        source_name = mapping["source"]
        value = attributes.get(source_name)
        if source_name not in attributes:
            value = next(
                (value for key, value in attributes.items() if key.casefold() == source_name.casefold()),
                None,
            )
    if value is None or value == "":
        return None
    if mapping.get("type") == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None
    return str(value).strip()


def _normalize_feature(source: dict, attributes: dict, retrieved_at: str) -> tuple[dict | None, list[str]]:
    mapped = {
        field: _field_value(attributes, mapping)
        for field, mapping in source["field_map"].items()
    }
    source_record_id = mapped.get("source_record_id")
    if not source_record_id:
        return None, ["missing_source_record_id"]
    lat = mapped.get("latitude_deg")
    lon = mapped.get("longitude_deg")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, ["missing_or_invalid_coordinates"]

    flags = ["source_vintage_unverified"]
    if not mapped.get("site_name"):
        flags.append("source_name_missing")
    if not mapped.get("service_type"):
        flags.append("source_category_missing")
    if not mapped.get("address"):
        flags.append("source_address_missing")
    record = {
        "source_id": source["id"],
        "source_record_id": source_record_id,
        "site_id": f"{source['id']}:{source_record_id}",
        **mapped,
        "geography_id": "city-of-toronto",
        "source_url": source["layer_url"],
        "retrieved_at": retrieved_at,
        "published_at": None,
        "evidence_state": "observed",
        "quality_flags": flags,
    }
    return record, []


def _validate_source_fields(source: dict, metadata: dict) -> None:
    available = {
        field.get("name", "").casefold()
        for field in metadata.get("fields", [])
        if isinstance(field, dict)
    }
    if not available:
        raise DataPipelineError(f"{source['id']} returned no field metadata")
    missing = [
        mapping["source"]
        for mapping in source["field_map"].values()
        if "source" in mapping and mapping["source"].casefold() not in available
    ]
    if missing:
        raise DataPipelineError(
            f"{source['id']} source schema changed; missing mapped fields: {', '.join(missing)}"
        )


def _source_updated_at(metadata: dict) -> str | None:
    edit_date = metadata.get("editingInfo", {}).get("lastEditDate")
    if not isinstance(edit_date, (int, float)) or not math.isfinite(edit_date) or edit_date < 0:
        return None
    return datetime.fromtimestamp(edit_date / 1000, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_source_documents(sources: list[dict], source_runs: list[dict], records: list[dict], path: Path) -> None:
    run_by_id = {row["dataset_id"]: row for row in source_runs}
    documents = []
    for source in sources:
        run = run_by_id[source["id"]]
        text = " ".join(
            [
                source["title"],
                source["publisher"],
                source["description"],
                "Simulation variables: " + ", ".join(source["simulation_variables"]),
                "Search terms: " + ", ".join(source["retrieval_terms"]),
                "Data limitations: " + " ".join(source["limitations"]),
                "Ingestion status: " + run["status"],
            ]
        )
        documents.append(
            {
                "doc_id": f"source:{source['id']}",
                "doc_type": "dataset_source",
                "dataset_id": source["id"],
                "record_id": None,
                "source_url": source["layer_url"],
                "retrieved_at": run.get("retrieved_at"),
                "evidence_state": "observed",
                "text": text,
                "fields": None,
            }
        )
    for record in records:
        values = [
            record.get("site_name"),
            record.get("place_category"),
            record.get("service_type"),
            record.get("institution_name"),
            record.get("address"),
            record.get("postal_code"),
            record.get("municipality"),
        ]
        text = " ".join(str(value) for value in values if value)
        documents.append(
            {
                "doc_id": f"record:{record['site_id']}",
                "doc_type": "dataset_record",
                "dataset_id": record["source_id"],
                "record_id": record["source_record_id"],
                "source_url": record["source_url"],
                "retrieved_at": record["retrieved_at"],
                "evidence_state": record["evidence_state"],
                "text": text,
                "fields": record,
            }
        )
    _write_jsonl(path, documents)


def _source_metric(source_id: str, source_runs: dict[str, dict], records: list[dict]) -> dict:
    run = source_runs.get(source_id)
    if not run:
        return {
            "value": None,
            "unit": "locations",
            "status": "source_not_selected",
            "source_id": source_id,
        }
    if run.get("status") != "complete":
        return {
            "value": None,
            "unit": "locations",
            "status": "source_ingestion_incomplete",
            "source_id": source_id,
        }
    count = sum(record["source_id"] == source_id for record in records)
    return {
        "value": count,
        "unit": "locations",
        "status": "observed_accepted_record_count",
        "source_id": source_id,
        "evidence_state": "observed",
        "source_vintage": run.get("source_updated_at"),
        "quality_flags": run.get("quality_flags", []),
    }


def _unavailable_metric(
    source_runs: dict[str, dict],
    required_source_ids: list[str],
    unit: str,
    reason: str,
) -> dict:
    not_selected = [source_id for source_id in required_source_ids if source_id not in source_runs]
    failed = [
        source_id for source_id in required_source_ids
        if source_id in source_runs and source_runs[source_id].get("status") != "complete"
    ]
    if not_selected:
        status = "source_not_selected"
    elif failed:
        status = "source_ingestion_incomplete"
    else:
        status = "not_reported_by_selected_sources"
    return {
        "value": None,
        "unit": unit,
        "status": status,
        "required_source_ids": required_source_ids,
        "missing_source_ids": not_selected + failed,
        "reason": reason,
    }


def _dashboard(sources: list[dict], source_runs: list[dict], records: list[dict], snapshot_id: str) -> dict:
    source_map = {source["id"]: source for source in sources}
    run_map = {run["dataset_id"]: run for run in source_runs}
    school_records = [row for row in records if row["source_id"] == "toronto_education_sites"]
    board_counts = Counter(
        row["institution_name"] for row in school_records if row.get("institution_name")
    )
    by_service_type = {
        source_id: dict(sorted(Counter(
            row["service_type"] for row in records
            if row["source_id"] == source_id and row.get("service_type")
        ).items()))
        for source_id in source_map
    }
    metrics = {
        "listed_supermarket_sites": _source_metric("toronto_supermarkets", run_map, records),
        "listed_convenience_store_sites": _source_metric("toronto_convenience_stores", run_map, records),
        "listed_food_support_program_sites": _source_metric("toronto_food_support_sites", run_map, records),
        "listed_education_sites": _source_metric("toronto_education_sites", run_map, records),
        "distinct_reported_school_institution_labels": (
            {
                "value": len(board_counts),
                "unit": "labels",
                "status": "observed_distinct_non_null_labels",
                "source_id": "toronto_education_sites",
                "not_an_operator_count": True,
            }
            if run_map.get("toronto_education_sites", {}).get("status") == "complete"
            else {
                "value": None,
                "unit": "labels",
                "status": "source_ingestion_incomplete" if "toronto_education_sites" in run_map else "source_not_selected",
                "source_id": "toronto_education_sites",
                "not_an_operator_count": True,
            }
        ),
        "unique_grocery_operator_count": _unavailable_metric(
            run_map,
            ["toronto_supermarkets", "toronto_convenience_stores"],
            "organizations",
            "The retail layers identify sites, not grocery-chain/operator entities.",
        ),
        "store_inventory_kg": _unavailable_metric(
            run_map,
            ["toronto_supermarkets", "toronto_convenience_stores"],
            "kg",
            "The retail layers do not report food stock, inventory, sales, or daily throughput.",
        ),
        "local_retail_price_cad_per_kg": _unavailable_metric(
            run_map,
            ["toronto_supermarkets", "toronto_convenience_stores"],
            "CAD/kg",
            "The retail layers do not report item-level prices.",
        ),
        "food_support_daily_capacity_or_unmet_demand": _unavailable_metric(
            run_map,
            ["toronto_food_support_sites"],
            "households/day",
            "The location layer does not report clients served, unmet requests, stock, or capacity.",
        ),
        "school_meals_served_per_day": _unavailable_metric(
            run_map,
            ["toronto_education_sites"],
            "meals/day",
            "The education location layer does not report meal-program participation or servings.",
        ),
    }
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "geography_id": "city-of-toronto",
        "spatial_scope": "Citywide points; not assigned to the active simulation district.",
        "metrics": metrics,
        "service_type_counts": by_service_type,
        "school_site_counts_by_reported_institution": dict(sorted(board_counts.items())),
        "sources": [
            {
                "dataset_id": run["dataset_id"],
                "status": run["status"],
                "source_updated_at": run.get("source_updated_at"),
                "source_vintage_status": "reported" if run.get("source_updated_at") else "unknown",
                "accepted_row_count": run.get("accepted_record_count"),
                "rejected_row_count": run.get("rejected_row_count"),
                "rejected_reason_counts": run.get("rejected_reason_counts", {}),
                "quality_flags": run.get("quality_flags", []),
            }
            for run in source_runs
        ],
        "evidence_note": "Counts describe accepted records in this retrieved City layer snapshot. They are not counts of operating capacity, demand served, or food stock.",
    }


def _quality_report(source_runs: list[dict], retrieved_at: str, snapshot_id: str) -> dict:
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "retrieved_at": retrieved_at,
        "complete": all(run["status"] == "complete" for run in source_runs),
        "sources": [
            {
                "dataset_id": run["dataset_id"],
                "status": run["status"],
                "source_updated_at": run.get("source_updated_at"),
                "raw_record_count": run.get("raw_record_count"),
                "accepted_record_count": run.get("accepted_record_count"),
                "rejected_row_count": run.get("rejected_row_count"),
                "rejected_reason_counts": run.get("rejected_reason_counts", {}),
                "record_quality_flag_counts": run.get("record_quality_flag_counts", {}),
                "quality_flags": run.get("quality_flags", []),
                "error": run.get("error"),
            }
            for run in source_runs
        ],
    }


def _simulation_inputs(dashboard: dict, records: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "snapshot_id": dashboard["snapshot_id"],
        "evidence_state": "observed",
        "geography_id": "city-of-toronto",
        "spatial_scope": dashboard["spatial_scope"],
        "site_records": records,
        "candidate_variables": dashboard["metrics"],
        "activation_status": "candidate_only",
        "activation_note": "Review geography, source vintage, site matching, and licensing before wiring these citywide points into a simulation run.",
    }


def ingest(
    source_ids: Sequence[str] | None = None,
    output_dir: Path | None = None,
    timeout: int = 60,
) -> Path:
    """Fetch selected ArcGIS layers into a new, hashed candidate snapshot."""
    registry = load_registry()
    all_sources = registry["sources"]
    requested_ids = list(source_ids) if source_ids else [source["id"] for source in all_sources]
    if len(requested_ids) != len(set(requested_ids)):
        raise DataPipelineError("source ids must not be repeated")
    sources = [source_by_id(source_id, registry) for source_id in requested_ids]
    if timeout < 1:
        raise DataPipelineError("timeout must be positive")

    retrieved_at = _utc_now()
    stamp = retrieved_at.replace("-", "").replace(":", "")
    root = output_dir or (repo_root() / "outputs" / "toronto-data" / f"candidate-{stamp}")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for name in ("raw", "normalized", "rejected"):
        (root / name).mkdir()

    manifest = {
        "schema_version": 1,
        "snapshot_id": root.name,
        "retrieved_at": retrieved_at,
        "geography_id": registry["geography_id"],
        "spatial_scope": "Citywide City of Toronto point layers; no simulation-district clipping has been applied.",
        "dataset_schema": str(schema_path().relative_to(repo_root())),
        "registry_path": str(registry_path().relative_to(repo_root())),
        "source_registry_sha256": hashlib.sha256(registry_path().read_bytes()).hexdigest(),
        "dataset_schema_sha256": hashlib.sha256(schema_path().read_bytes()).hexdigest(),
        "transform_revision": "toronto-civic-locations-v1",
        "retrieval_method": "BM25-style lexical ranking over source metadata and source records",
        "complete": False,
        "datasets": [],
    }
    records: list[dict] = []
    for source in sources:
        print(f"Fetching {source['id']} from {source['layer_url']}")
        run = {
            "dataset_id": source["id"],
            "publisher": source["publisher"],
            "source_url": source["layer_url"],
            "resource_url": source["layer_url"].rstrip("/") + "/query",
            "retrieved_at": retrieved_at,
            "published_at": None,
            "source_updated_at": None,
            "reference_period_start": None,
            "reference_period_end": None,
            "geography_id": registry["geography_id"],
            "boundary_vintage": None,
            "units": "locations; latitude_deg and longitude_deg in decimal degrees",
            "licence_url": registry["licence_url"],
            "licence_status": registry["licence_status"],
            "attribution": "City of Toronto; confirm layer terms before publication.",
            "evidence_state": "observed",
            "field_map": source["field_map"],
            "simulation_variables": source["simulation_variables"],
            "limitations": source["limitations"],
            "status": "fetching",
            "quality_flags": ["source_vintage_unverified", "layer_licence_review_required"],
            "raw_files": [],
        }
        manifest["datasets"].append(run)
        source_records: list[dict] = []
        rejected: list[dict] = []
        seen_ids: set[str] = set()
        raw_record_count = 0
        try:
            metadata_url = source["layer_url"].rstrip("/") + "?f=json"
            metadata_raw = _request(metadata_url, timeout)
            metadata_path = root / "raw" / f"{source['id']}.metadata.json"
            metadata_path.write_bytes(metadata_raw)
            run["raw_files"].append(
                {"path": str(metadata_path.relative_to(root)), "sha256": _sha256(metadata_path), "bytes": metadata_path.stat().st_size}
            )
            metadata = _json_response(metadata_raw, metadata_url)
            _validate_source_fields(source, metadata)
            run["source_updated_at"] = _source_updated_at(metadata)
            run["source_layer_name"] = metadata.get("name")
            run["source_layer_description"] = metadata.get("description")
            run["source_max_record_count"] = metadata.get("maxRecordCount")

            query_url = source["layer_url"].rstrip("/") + "/query"
            offset = 0
            page_number = 0
            page_size = min(int(metadata.get("maxRecordCount") or 2000), 2000)
            while True:
                query = urllib.parse.urlencode(
                    {
                        "f": "json",
                        "where": "1=1",
                        "outFields": "*",
                        "returnGeometry": "false",
                        "orderByFields": "OBJECTID ASC",
                        "resultOffset": str(offset),
                        "resultRecordCount": str(page_size),
                    }
                )
                page_url = query_url + "?" + query
                page_raw = _request(page_url, timeout)
                page_path = root / "raw" / f"{source['id']}.page-{page_number:05d}.json"
                page_path.write_bytes(page_raw)
                run["raw_files"].append(
                    {"path": str(page_path.relative_to(root)), "sha256": _sha256(page_path), "bytes": page_path.stat().st_size}
                )
                payload = _json_response(page_raw, page_url)
                features = payload.get("features")
                if not isinstance(features, list):
                    raise DataPipelineError(f"{source['id']} query response has no feature list")
                raw_record_count += len(features)
                for feature in features:
                    attributes = feature.get("attributes", {}) if isinstance(feature, dict) else {}
                    if not isinstance(attributes, dict):
                        rejected.append({"reasons": ["invalid_attributes"], "raw_attributes": attributes})
                        continue
                    candidate, reasons = _normalize_feature(source, attributes, retrieved_at)
                    candidate_id = candidate["source_record_id"] if candidate else None
                    if candidate_id and candidate_id in seen_ids:
                        candidate = None
                        reasons = ["duplicate_source_record_id"]
                    if candidate is not None:
                        seen_ids.add(candidate_id)
                        source_records.append(candidate)
                    else:
                        rejected.append({"reasons": reasons, "raw_attributes": attributes})
                offset += len(features)
                page_number += 1
                if not features or (len(features) < page_size and not payload.get("exceededTransferLimit")):
                    break
            normalized_path = root / "normalized" / f"{source['id']}.jsonl"
            rejected_path = root / "rejected" / f"{source['id']}.jsonl"
            _write_jsonl(normalized_path, source_records)
            _write_jsonl(rejected_path, rejected)
            run["normalized_file"] = str(normalized_path.relative_to(root))
            run["normalized_sha256"] = _sha256(normalized_path)
            run["rejected_file"] = str(rejected_path.relative_to(root))
            run["rejected_sha256"] = _sha256(rejected_path)
            run["raw_record_count"] = raw_record_count
            run["accepted_record_count"] = len(source_records)
            run["rejected_row_count"] = len(rejected)
            run["rejected_reason_counts"] = dict(sorted(Counter(
                reason for row in rejected for reason in row["reasons"]
            ).items()))
            run["record_quality_flag_counts"] = dict(sorted(Counter(
                flag for row in source_records for flag in row["quality_flags"]
            ).items()))
            run["row_count"] = len(source_records)
            run["status"] = "complete"
            if run["source_updated_at"] is None:
                run["quality_flags"].append("source_update_date_unavailable")
            if rejected:
                run["quality_flags"].append("rows_rejected_for_required_id_or_coordinates")
            records.extend(source_records)
            print(f"  accepted {len(source_records)} of {raw_record_count} source rows")
        except (DataPipelineError, OSError, ValueError, urllib.error.URLError) as exc:
            run["status"] = "failed"
            run["error"] = str(exc)
            run["row_count"] = None
            run["raw_record_count"] = raw_record_count
            run["accepted_record_count"] = len(source_records)
            run["rejected_row_count"] = len(rejected)
            run["rejected_reason_counts"] = dict(sorted(Counter(
                reason for row in rejected for reason in row["reasons"]
            ).items()))
            run["record_quality_flag_counts"] = dict(sorted(Counter(
                flag for row in source_records for flag in row["quality_flags"]
            ).items()))
            print(f"  FAILED: {exc}")
        run["raw_sha256"] = None
        # Every exact response is hashed independently in raw_files. For a single
        # raw response, also expose that response hash under the short field.
        if len(run["raw_files"]) == 1:
            run["raw_sha256"] = run["raw_files"][0]["sha256"]

    manifest["complete"] = all(run["status"] == "complete" for run in manifest["datasets"])
    manifest["row_count"] = len(records)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dashboard = _dashboard(sources, manifest["datasets"], records, manifest["snapshot_id"])
    dashboard_path = root / "dashboard.json"
    dashboard_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path = root / "quality_report.json"
    quality_path.write_text(
        json.dumps(_quality_report(manifest["datasets"], retrieved_at, manifest["snapshot_id"]), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    inputs = _simulation_inputs(dashboard, records)
    inputs_path = root / "simulation_inputs.json"
    inputs_path.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_source_documents(sources, manifest["datasets"], records, root / "documents.jsonl")
    manifest["dashboard_sha256"] = _sha256(dashboard_path)
    manifest["quality_report_sha256"] = _sha256(quality_path)
    manifest["simulation_inputs_sha256"] = _sha256(inputs_path)
    manifest["documents_sha256"] = _sha256(root / "documents.jsonl")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return root
