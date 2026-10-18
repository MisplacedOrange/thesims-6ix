"""Export bounded Python-authoritative runs for browser playback."""

import argparse
import hashlib
import json
from pathlib import Path

from sim.data.simulation_sites import load_simulation_site_snapshot
from .simulation import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=Path("apps/web/public/data/toronto.json"))
    parser.add_argument("--out", type=Path, default=Path("apps/web/public/data/interactables"))
    parser.add_argument("--populations", type=int, nargs="+", default=[200, 600, 1200])
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--closed-edge", action="append", default=[], help="Walking edge as node:node")
    parser.add_argument(
        "--site-snapshot",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "sim" / "data" / "snapshots" / "toronto-downtown-sites-v3.json",
        help="frozen source-listed site locations to use (default: pinned downtown snapshot)",
    )
    parser.add_argument("--illustrative-sites-only", action="store_true", help="use the original synthetic site anchors")
    args = parser.parse_args()
    district = json.loads(args.map.read_text(encoding="utf-8"))
    site_snapshot = None
    site_snapshot_sha256 = None
    if not args.illustrative_sites_only:
        site_snapshot, site_snapshot_sha256 = load_simulation_site_snapshot(args.site_snapshot)
        map_sha256 = hashlib.sha256(args.map.read_bytes()).hexdigest()
        if site_snapshot.get("map_sha256") != map_sha256:
            raise ValueError(
                "site snapshot was prepared for a different map file; rerun `python -m sim.data prepare-sites`"
            )
    closures = tuple(tuple(map(int, edge.split(":"))) for edge in args.closed_edge)
    if any(len(e) != 2 for e in closures):
        parser.error("closed edges require two node ids")
    args.out.mkdir(parents=True, exist_ok=True)
    for population in args.populations:
        for emergency in [False, True]:
            trace = run(
                district,
                population,
                args.seed,
                emergency,
                closures,
                site_snapshot,
                site_snapshot_sha256,
            )
            path = args.out / f"{population}-{'emergency' if emergency else 'baseline'}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(trace, separators=(",", ":")), encoding="utf-8")
            temporary.replace(path)
            print(f"{path}: {len(trace['events'])} interaction records", flush=True)


if __name__ == "__main__":
    main()
