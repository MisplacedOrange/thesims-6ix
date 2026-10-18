"""Command-line entry point for Toronto civic-data retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sim.data.catalog import load_registry
from sim.data.pipeline import ingest
from sim.data.retrieval import retrieve


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
    retrieve_parser.set_defaults(action="retrieve")
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
        result = retrieve(args.query, args.snapshot, args.top_k)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
