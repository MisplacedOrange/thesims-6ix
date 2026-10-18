"""Command-line entry point for Toronto civic-data retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim.data.catalog import load_registry
from sim.data.pipeline import ingest
from sim.data.retrieval import retrieve
from sim.data.simulation_sites import prepare_simulation_site_snapshot


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire and retrieve Toronto civic food-access data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog", help="list registered datasets and simulation mappings")
    catalog_parser.set_defaults(action="catalog")

    ingest_parser = subparsers.add_parser("ingest", help="retrieve public City ArcGIS layers into a candidate snapshot")
    ingest_parser.add_argument("--source", action="append", help="source id; repeat to select multiple (default: all)")
    ingest_parser.add_argument("--out", type=Path, help="new output directory (default: outputs/toronto-data/candidate-<UTC timestamp>)")
    ingest_parser.add_argument("--timeout", type=int, default=60, help="per-request timeout in seconds")
    ingest_parser.set_defaults(action="ingest")

    retrieve_parser = subparsers.add_parser("retrieve", help="retrieve cited source or location records from a snapshot")
    retrieve_parser.add_argument("query", help="question or search terms")
    retrieve_parser.add_argument("--snapshot", type=Path, required=True, help="candidate snapshot directory")
    retrieve_parser.add_argument("--top-k", type=int, default=5)
    retrieve_parser.add_argument("--dataset-id", help="restrict retrieval to a registered source in the snapshot")
    retrieve_parser.add_argument("--record-id", help="retrieve one exact source record (requires --dataset-id)")
    retrieve_parser.set_defaults(action="retrieve")

    prepare_parser = subparsers.add_parser(
        "prepare-sites",
        help="select cited City-listed locations for the downtown pedestrian simulation",
    )
    prepare_parser.add_argument("--snapshot", type=Path, required=True, help="complete candidate snapshot directory")
    prepare_parser.add_argument("--map", type=Path, default=Path("apps/web/public/data/toronto.json"))
    prepare_parser.add_argument(
        "--out",
        type=Path,
        default=Path("sim/data/snapshots/toronto-downtown-sites-v3.json"),
        help="new immutable derived location snapshot",
    )
    prepare_parser.set_defaults(action="prepare_sites")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.action == "catalog":
        registry = load_registry()
        print(json.dumps(registry, ensure_ascii=False, indent=2))
    elif args.action == "ingest":
        path = ingest(source_ids=args.source, output_dir=args.out, timeout=args.timeout)
        print(f"Candidate snapshot: {path}")
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        print(f"Complete: {manifest['complete']}; accepted rows: {manifest['row_count']}")
        if not manifest["complete"]:
            raise SystemExit(1)
    elif args.action == "retrieve":
        result = retrieve(args.query, args.snapshot, args.top_k, args.dataset_id, args.record_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.action == "prepare_sites":
        path = prepare_simulation_site_snapshot(args.snapshot, args.map, args.out)
        print(f"Simulation site snapshot: {path}")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        print(f"Source snapshot: {snapshot['source_snapshot_id']}")
        for role, site in snapshot["sites"].items():
            print(f"  {role}: {site['display_name']} ({site['source_id']}:{site['source_record_id']})")


if __name__ == "__main__":
    main()
