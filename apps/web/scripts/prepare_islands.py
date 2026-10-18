"""Build the Toronto Islands layer from OpenStreetMap via the Overpass API.

The main district snapshot only keeps the mainland shore. This companion file
adds the island outlines and Billy Bishop runways seen across the harbour.
The derived database is distributed under ODbL 1.0.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from prepare_toronto import ROOT, project

API = "https://overpass-api.de/api/interpreter"
QUERY = """[out:json][timeout:60];
(way["place"~"island|islet"](43.600,-79.420,43.640,-79.330);
 relation["place"~"island|islet"](43.600,-79.420,43.640,-79.330);
 way["aeroway"="runway"](43.615,-79.41,43.64,-79.38););
out geom;"""
RUNWAY_WIDTH = 45
MIN_AREA = 150


def fetch(cache: Path) -> tuple[dict, dict]:
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / "islands-overpass.json"
    if not path.exists():
        body = urllib.parse.urlencode({"data": QUERY}).encode()
        req = urllib.request.Request(API, data=body, headers={
            "User-Agent": "Sims6ix-Toronto-environment/0.1", "Accept": "application/json"})
        path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
    raw = path.read_bytes()
    return json.loads(raw), {"url": API, "query": QUERY, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    length = math.dist(a, b) or 1e-9
    worst, index = 0.0, 0
    for i in range(1, len(points) - 1):
        p = points[i]
        distance = abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / length
        if distance > worst:
            worst, index = distance, i
    if worst <= tolerance:
        return [a, b]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def area(points: list[list[float]]) -> float:
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(points, points[1:]))) / 2


def rings(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    """Join open multipolygon members end to end into closed rings."""
    pending = [s for s in segments if len(s) >= 2]
    result = []
    while pending:
        ring = pending.pop(0)
        changed = True
        while math.dist(ring[0], ring[-1]) > 0.5 and changed:
            changed = False
            for i, s in enumerate(pending):
                if math.dist(ring[-1], s[0]) < 0.5:
                    ring = ring + s[1:]
                elif math.dist(ring[-1], s[-1]) < 0.5:
                    ring = ring + s[::-1][1:]
                elif math.dist(ring[0], s[-1]) < 0.5:
                    ring = s + ring[1:]
                elif math.dist(ring[0], s[0]) < 0.5:
                    ring = s[::-1] + ring[1:]
                else:
                    continue
                pending.pop(i)
                changed = True
                break
        if math.dist(ring[0], ring[-1]) <= 0.5:
            result.append(ring)
    return result


def prepare(cache: Path) -> None:
    data, source = fetch(cache)
    islands, runways = [], []
    for element in data["elements"]:
        tags = element.get("tags", {})
        if element["type"] == "way" and tags.get("aeroway") == "runway":
            points = [project(n["lon"], n["lat"]) for n in element["geometry"]]
            runways.append({"id": "way/" + str(element["id"]), "width": RUNWAY_WIDTH, "points": simplify(points, 1)})
            continue
        if element["type"] == "way":
            outlines = rings([[project(n["lon"], n["lat"]) for n in element["geometry"]]])
        else:
            outlines = rings([[project(n["lon"], n["lat"]) for n in m["geometry"]]
                              for m in element["members"] if m.get("role") == "outer" and m.get("geometry")])
        for i, ring in enumerate(outlines):
            far = max(range(len(ring)), key=lambda k: math.dist(ring[0], ring[k]))
            polygon = simplify(ring[:far + 1], 2.5)[:-1] + simplify(ring[far:], 2.5)
            if len(polygon) >= 4 and area(polygon) >= MIN_AREA:
                islands.append({"id": element["type"] + "/" + str(element["id"]) + ("" if i == 0 else "#" + str(i)),
                                "name": tags.get("name", ""), "polygon": [[round(x, 1), round(z, 1)] for x, z in polygon]})
    output = {
        "schema": 1, "islands": islands, "runways": runways,
        "source": {"publisher": "OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright",
                   "license": "ODbL-1.0", "licenseUrl": "https://opendatacommons.org/licenses/odbl/1-0/",
                   "retrievedAt": datetime.fromtimestamp((cache / "islands-overpass.json").stat().st_mtime, timezone.utc).isoformat(),
                   "query": source},
    }
    target = ROOT / "public/data/islands.json"
    target.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"islands": len(islands), "runways": len(runways), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".data-cache")
    prepare(parser.parse_args().cache)
