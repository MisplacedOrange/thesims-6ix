"""Export bounded Python-authoritative runs for browser playback."""

import argparse
import hashlib
import json
from pathlib import Path

from sim.data.simulation_sites import load_simulation_site_snapshot
from .manifest import DEFAULT_MANIFEST, ROOT, load_manifest
from .simulation import run_day


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                        help="validated scenario manifest (pins calendar, sample, seed, and data inputs)")
    parser.add_argument("--map", type=Path, help="optional map override; must match the manifest hash")
    parser.add_argument("--out", type=Path, default=Path("apps/web/public/data/interactables"))
    parser.add_argument("--populations", type=int, nargs="+", help="optional sample-size override")
    parser.add_argument("--seed", type=int, help="optional seed override")
    parser.add_argument("--closed-edge", action="append", default=[], help="Walking edge as node:node")
    parser.add_argument(
        "--site-snapshot",
        type=Path,
        help="optional site snapshot override; must match the manifest hash",
    )
    parser.add_argument("--illustrative-sites-only", action="store_true", help="use the original synthetic site anchors")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    manifest_bytes = args.manifest.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    map_path = args.map or ROOT / manifest["inputs"]["map"]["path"]
    map_bytes = map_path.read_bytes()
    if hashlib.sha256(map_bytes).hexdigest() != manifest["inputs"]["map"]["sha256"]:
        raise ValueError("map override does not match the pinned scenario manifest")
    district = json.loads(map_bytes)
    site_snapshot = None
    site_snapshot_sha256 = None
    if not args.illustrative_sites_only:
        snapshot_path = args.site_snapshot or ROOT / manifest["inputs"]["site_snapshot"]["path"]
        if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != manifest["inputs"]["site_snapshot"]["sha256"]:
            raise ValueError("site snapshot override does not match the pinned scenario manifest")
        site_snapshot, site_snapshot_sha256 = load_simulation_site_snapshot(snapshot_path)
        map_sha256 = hashlib.sha256(map_bytes).hexdigest()
        if site_snapshot.get("map_sha256") != map_sha256:
            raise ValueError(
                "site snapshot was prepared for a different map file; rerun `python -m sim.data prepare-sites`"
            )
    closures = tuple(tuple(map(int, edge.split(":"))) for edge in args.closed_edge)
    if any(len(e) != 2 for e in closures):
        parser.error("closed edges require two node ids")
    args.out.mkdir(parents=True, exist_ok=True)
    populations = args.populations or manifest["population"]["trace_presets"]
    seed = manifest["seed"] if args.seed is None else args.seed
    for population in populations:
        for emergency in [False, True]:
            trace = run_day(
                district,
                manifest["start_date"],
                population=population,
                seed=seed,
                emergency=emergency,
                closed_edges=closures,
                site_snapshot=site_snapshot,
                site_snapshot_sha256=site_snapshot_sha256,
                timezone_name=manifest["timezone"],
            )
            trace["scenario_manifest_id"] = manifest["scenario_id"]
            trace["scenario_manifest_sha256"] = manifest_sha256
            if args.seed is not None or args.populations is not None:
                trace["run_overrides"] = {
                    "seed": args.seed,
                    "populations": args.populations,
                }
            path = args.out / f"{population}-{'emergency' if emergency else 'baseline'}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(trace, separators=(",", ":")), encoding="utf-8")
            temporary.replace(path)
            print(f"{path}: {len(trace['events'])} interaction records", flush=True)


if __name__ == "__main__":
    main()
