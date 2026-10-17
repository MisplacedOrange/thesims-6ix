"""Immutable terminal artifacts; this is not a durable live-run service."""
import hashlib
import json
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path

from sim.core import events_to_json, state_to_json


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def export_run(run, directory, request=None):
    directory = Path(directory)
    # Never refresh a completed or interrupted artifact in place.
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "state.json").write_text(state_to_json(run.ledger.state), encoding="utf-8")
    (directory / "events.json").write_text(events_to_json(tuple(run.ledger.events)), encoding="utf-8")
    write_json(directory / "decisions.json", [r.to_payload() for r in run.decisions])
    write_json(directory / "results.json", {"outcomes": run.outcomes,
        "households": [asdict(h) for h in run.households], "feelings": run.feelings,
        "feeling_label": "Illustrative latent proxies, not measured human feelings or sentiment",
        "policies": run.policy_results, "settlements": run.settlements})
    write_json(directory / "presentation.json", {"journeys": run.journeys})
    write_json(directory / "logistics.json", run.logistics_state)
    from sim.core import KERNEL_VERSION, EVENT_SCHEMA_VERSION
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[2], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    manifest = {"schema_version": 1, "economic_hash": run.economic_hash,
        "economic_hash_algorithm": "core-logistics-policy-decisions-inputs-v1",
        "runtime": {"python": platform.python_version(), "kernel": KERNEL_VERSION,
                    "event_schema": EVENT_SCHEMA_VERSION, "git_revision": revision},
        "source_files": {str(p.relative_to(Path(__file__).resolve().parents[2])).replace('\\', '/'):
                         hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(Path(__file__).resolve().parents[1].rglob('*.py'))},
        "inputs": run.inputs, "request": asdict(request) if request else None,
        "limitations": ["Illustrative inputs; no observed Toronto calibration",
            "One synthetic school day and one produce component, not nutritional adequacy",
            "No live provider, infrastructure planner, API, durable recovery, or frontend integration",
            "Conditional drone eligibility is not flight permission",
            "Monte Carlo variation is not parameter uncertainty or external validity"],
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())}}
    write_json(directory / "manifest.json", manifest)
    # Written last. Consumers reject missing markers or hash mismatches.
    (directory / "COMPLETE").write_text(hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest() + "\n", encoding="ascii")
    return directory


def verify_export(directory):
    directory = Path(directory)
    expected = (directory / "COMPLETE").read_text(encoding="ascii").strip()
    raw = (directory / "manifest.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("manifest hash mismatch")
    manifest = json.loads(raw)
    for name, digest in manifest["files"].items():
        if Path(name).name != name or hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"invalid or incomplete artifact: {name}")
    return manifest
