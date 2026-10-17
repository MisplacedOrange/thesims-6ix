"""Load the frozen district inputs and refuse a hash or unit mismatch."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sim.core import DayWindow, InputError, load_catalog, validate_calendar
from sim.district.network import Edge, Network


class SnapshotError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Snapshot:
    header: dict
    manifest: dict
    controls: dict
    behavior: dict
    places: dict
    network: Network
    days: tuple[DayWindow, ...]
    catalog: object


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(__file__).resolve().parent / "data"


def load_snapshot() -> Snapshot:
    root = repo_root()
    manifest_path = data_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded: dict[str, object] = {}
    for dataset in manifest["datasets"]:
        path = root / dataset["package_path"]
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != dataset["raw_sha256"]:
            raise SnapshotError(f"{dataset['dataset_id']} raw hash mismatch")
        parsed = json.loads(raw)
        _refuse_floats(parsed, dataset["dataset_id"])
        loaded[dataset["dataset_id"]] = parsed
    header = loaded["snapshot"]
    if not isinstance(header, dict):
        raise SnapshotError("snapshot header must be an object")
    controls = loaded["controls"]
    behavior = loaded["behavior"]
    places = loaded["places"]
    network_data = loaded["network"]
    calendar = loaded["calendar"]
    if not isinstance(network_data, dict) or not isinstance(calendar, dict):
        raise SnapshotError("network and calendar must be objects")
    if not isinstance(controls, dict) or not isinstance(behavior, dict) or not isinstance(places, dict):
        raise SnapshotError("controls, behavior, and places must be objects")
    catalog = load_catalog(root / "sim" / "core" / "data" / "catalog.json")
    catalog_row = next(item for item in manifest["datasets"] if item["dataset_id"] == "catalog")
    if catalog.sha256 != catalog_row["raw_sha256"]:
        raise SnapshotError("catalog hash mismatch")
    if header.get("catalog_id") != catalog.catalog_id:
        raise SnapshotError("catalog id mismatch")
    if header.get("price_base_month") is not None:
        raise SnapshotError("price_base_month must stay null; cash is nominal")
    days = tuple(
        DayWindow(day["day_index"], day["local_date"], day["start_second"], day["length_seconds"])
        for day in calendar["days"]
    )
    problems = validate_calendar(days)
    if problems:
        raise InputError(problems)
    network = Network(
        nodes=tuple(network_data["nodes"]),
        edges=tuple(
            Edge(edge["edge_id"], edge["a"], edge["b"], edge["metres"], edge["walk_seconds"])
            for edge in network_data["edges"]
        ),
    )
    _validate_network(network)
    return Snapshot(header, manifest, controls, behavior, places, network, days, catalog)


def _validate_network(network: Network) -> None:
    nodes = set(network.nodes)
    seen: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for edge in network.edges:
        if edge.edge_id in seen:
            raise SnapshotError(f"duplicate edge {edge.edge_id}")
        seen.add(edge.edge_id)
        if edge.a not in nodes or edge.b not in nodes or edge.a == edge.b:
            raise SnapshotError(f"bad edge {edge.edge_id}")
        if edge.metres < 1 or edge.walk_seconds < 1:
            raise SnapshotError(f"edge {edge.edge_id} needs positive metres and seconds")
        pair = tuple(sorted((edge.a, edge.b)))
        if pair in pairs:
            raise SnapshotError(f"duplicate connection {edge.edge_id}")
        pairs.add(pair)  # type: ignore[arg-type]


def _refuse_floats(value: object, field: str) -> None:
    if isinstance(value, float):
        raise SnapshotError(f"{field} contains a float; use integers")
    if isinstance(value, dict):
        for key, item in value.items():
            if "dollar" in str(key).lower():
                raise SnapshotError(f"{field}.{key} uses a dollar field; use cents")
            _refuse_floats(item, f"{field}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _refuse_floats(item, f"{field}[{index}]")
