"""Build the offline Toronto visual district from the public OSM map API.

The derived map database is distributed under ODbL 1.0. Source tiles are cached
outside tracked application assets. No credentials or third-party code required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = (-79.385, 43.65)
BBOX = (-79.405, 43.635, -79.365, 43.665)
API = "https://api.openstreetmap.org/api/0.6/map"
WIDTHS = {
    "motorway": 18, "motorway_link": 9, "trunk": 17, "trunk_link": 8,
    "primary": 16, "primary_link": 8, "secondary": 13, "secondary_link": 8,
    "tertiary": 11, "tertiary_link": 7, "residential": 9, "unclassified": 9,
    "living_street": 7, "service": 5, "pedestrian": 9, "footway": 3,
    "path": 3, "steps": 2, "cycleway": 3,
}
WALKABLE = set(WIDTHS) - {"motorway", "motorway_link", "trunk", "trunk_link", "cycleway"}


def project(lon: float, lat: float) -> list[float]:
    return [
        round((lon - ORIGIN[0]) * 111320 * math.cos(math.radians(ORIGIN[1])), 2),
        round((ORIGIN[1] - lat) * 111320, 2),
    ]


def number(value: str | None) -> float | None:
    try:
        return float((value or "").split(";")[0].replace(" m", "").strip())
    except ValueError:
        return None


def tile(cache: Path, bounds: tuple[float, float, float, float], sources: list) -> list[Path]:
    name = hashlib.sha256(str(bounds).encode()).hexdigest()[:14] + ".osm"
    path = cache / name
    url = API + "?bbox=" + ",".join(str(v) for v in bounds)
    if not path.exists():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Sims6ix-Toronto-environment/0.1"})
            raw = urllib.request.urlopen(req, timeout=45).read()
            path.write_bytes(raw)
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            a, b, c, d = bounds
            if c - a < 0.002:
                raise
            mid = (a + c) / 2
            return tile(cache, (a, b, mid, d), sources) + tile(cache, (mid, b, c, d), sources)
    raw = path.read_bytes()
    sources.append({"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    return [path]


def prepare(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    sources: list[dict] = []
    paths: list[Path] = []
    a, b, c, d = BBOX
    for bounds in [(a, b, ORIGIN[0], ORIGIN[1]), (ORIGIN[0], b, c, ORIGIN[1]),
                   (a, ORIGIN[1], ORIGIN[0], d), (ORIGIN[0], ORIGIN[1], c, d)]:
        paths.extend(tile(cache, bounds, sources))
    nodes: dict[str, list[float]] = {}
    ways: dict[str, ET.Element] = {}
    relations: dict[str, ET.Element] = {}
    for path in paths:
        root = ET.parse(path).getroot()
        for item in root:
            if item.tag == "node":
                nodes[item.attrib["id"]] = project(float(item.attrib["lon"]), float(item.attrib["lat"]))
            elif item.tag == "way":
                ways[item.attrib["id"]] = item
            elif item.tag == "relation":
                relations[item.attrib["id"]] = item

    def tags(item: ET.Element) -> dict[str, str]:
        return {t.attrib["k"]: t.attrib["v"] for t in item.findall("tag")}

    def geometry(item: ET.Element) -> tuple[list[str], list[list[float]]]:
        ids = [nd.attrib["ref"] for nd in item.findall("nd")]
        return ids, [nodes[n] for n in ids if n in nodes]

    buildings, roads, parks, water, shores, rails = [], [], [], [], [], []
    graph_nodes: list[list[float]] = []
    graph_edges: list[list[int | str]] = []
    graph_index: dict[tuple[int, int], int] = {}
    junctions: dict[str, set[int]] = {}

    def graph_node(p: list[float]) -> int:
        key = (round(p[0] * 10), round(p[1] * 10))
        if key not in graph_index:
            graph_index[key] = len(graph_nodes)
            graph_nodes.append([round(p[0], 2), round(p[1], 2)])
        return graph_index[key]

    def inside(p: list[float], pad: float = 0) -> bool:
        return -1611 - pad <= p[0] <= 1611 + pad and -1670 - pad <= p[1] <= 1670 + pad

    for wid, way in ways.items():
        t = tags(way)
        ids, poly = geometry(way)
        if len(poly) < 2:
            continue
        if ("building" in t or "building:part" in t) and len(poly) >= 4 and ids[0] == ids[-1]:
            centre = [sum(p[k] for p in poly) / len(poly) for k in (0, 1)]
            if not inside(centre) or t.get("location") == "underground":
                continue
            height = number(t.get("height"))
            levels = number(t.get("building:levels"))
            basis = "tag" if height else "levels" if levels else "estimate"
            height = height or (levels * 3.5 if levels else 11 + int(wid) % 8 * 2)
            minimum = number(t.get("min_height")) or (number(t.get("building:min_level")) or 0) * 3.5
            buildings.append({"id": "way/" + wid, "name": t.get("name", ""),
                              "polygon": poly, "height": round(min(height, 380), 1),
                              "base": round(minimum, 1), "basis": basis,
                              "use": t.get("building", t.get("building:part", "yes"))})
        if t.get("leisure") in {"park", "garden"} or t.get("landuse") in {"grass", "recreation_ground"}:
            if len(poly) >= 4 and ids[0] == ids[-1] and any(inside(p) for p in poly):
                parks.append({"id": "way/" + wid, "name": t.get("name", ""), "polygon": poly})
        if t.get("natural") == "water" and ids[0] == ids[-1]:
            water.append({"id": "way/" + wid, "name": t.get("name", ""), "polygon": poly})
        if t.get("railway") in {"rail", "light_rail"} and t.get("tunnel") != "yes":
            if any(inside(p) for p in poly):
                rails.append(poly)
        kind = t.get("highway")
        if kind not in WIDTHS or not any(inside(p) for p in poly):
            continue
        if t.get("area") == "yes" or t.get("tunnel") == "yes" or t.get("access") in {"private", "no"}:
            continue
        width = WIDTHS[kind]
        roads.append({"id": "way/" + wid, "name": t.get("name", ""), "kind": kind,
                      "width": width, "points": poly, "bridge": t.get("bridge") == "yes"})
        if kind not in WALKABLE or t.get("foot") == "no":
            continue
        if t.get("indoor") in {"yes", "corridor", "room"} or t.get("level", "0") not in {"0", "0.0"}:
            continue
        if kind == "service" and t.get("foot") not in {"yes", "designated"}:
            continue
        is_path = kind in {"footway", "path", "steps", "pedestrian", "living_street"}
        for i in range(len(poly) - 1):
            p, q = poly[i], poly[i + 1]
            if not inside(p) or not inside(q):
                continue
            length = math.dist(p, q)
            if length < 0.4 or length > 450:
                continue
            # Sidewalks are derived parallel offsets. Mapped footpaths remain on source geometry.
            offsets = [0] if is_path else [-width / 2 - 1.6, width / 2 + 1.6]
            for offset in offsets:
                dx, dz = (q[0] - p[0]) / length, (q[1] - p[1]) / length
                p2, q2 = [p[0] - dz * offset, p[1] + dx * offset], [q[0] - dz * offset, q[1] + dx * offset]
                u, v = graph_node(p2), graph_node(q2)
                graph_edges.append([u, v, "footpath" if is_path else "sidewalk"])
                if i < len(ids) - 1:
                    junctions.setdefault(ids[i], set()).add(u)
                    junctions.setdefault(ids[i + 1], set()).add(v)
    for points in junctions.values():
        ordered = sorted(points)
        for i, u in enumerate(ordered):
            for v in ordered[i + 1:]:
                distance = math.dist(graph_nodes[u], graph_nodes[v])
                if 0.2 < distance < 38:
                    graph_edges.append([u, v, "crossing"])

    # The Lake Ontario relation references open shore segments in the downloaded map tiles.
    shore_ids: set[str] = set()
    for relation in relations.values():
        t = tags(relation)
        if t.get("name") in {"Lake Ontario", "Toronto Harbour", "Inner Harbour"}:
            for member in relation.findall("member"):
                if member.attrib.get("type") == "way" and member.attrib.get("role") == "outer":
                    shore_ids.add(member.attrib["ref"])
    for wid in shore_ids:
        if wid in ways:
            _, poly = geometry(ways[wid])
            if any(inside(p, 1000) for p in poly):
                shores.append(poly)
    # Reject derived paths through the ground-level building massing. Mapped
    # indoor passages remain outside this outdoor visual environment.
    building_grid: dict[tuple[int, int], list[dict]] = {}
    for building in buildings:
        if building["base"] >= 5:
            continue
        poly = building["polygon"]
        lo_x, hi_x = min(p[0] for p in poly), max(p[0] for p in poly)
        lo_z, hi_z = min(p[1] for p in poly), max(p[1] for p in poly)
        building["bounds"] = [lo_x, lo_z, hi_x, hi_z]
        for gx in range(math.floor(lo_x / 60), math.floor(hi_x / 60) + 1):
            for gz in range(math.floor(lo_z / 60), math.floor(hi_z / 60) + 1):
                building_grid.setdefault((gx, gz), []).append(building)

    def blocked(p: list[float]) -> bool:
        for building in building_grid.get((math.floor(p[0] / 60), math.floor(p[1] / 60)), []):
            x1, z1, x2, z2 = building["bounds"]
            if not (x1 < p[0] < x2 and z1 < p[1] < z2):
                continue
            inside_polygon = False
            poly = building["polygon"]
            for i in range(len(poly) - 1):
                a, b = poly[i], poly[i + 1]
                if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
                    inside_polygon = not inside_polygon
            if inside_polygon:
                return True
        return False

    valid_edges = []
    for edge in graph_edges:
        p, q = graph_nodes[edge[0]], graph_nodes[edge[1]]
        steps = max(1, math.ceil(math.dist(p, q) / 4))
        if not any(blocked([p[k] + (q[k] - p[k]) * i / steps for k in (0, 1)]) for i in range(steps + 1)):
            valid_edges.append(edge)
    rejected_edges = len(graph_edges) - len(valid_edges)
    graph_edges = valid_edges
    for building in buildings:
        building.pop("bounds", None)
    output = {
        "schema": 1, "origin": list(ORIGIN), "bounds": [-1611, -1670, 1611, 1670],
        "buildings": buildings, "roads": roads, "parks": parks, "water": water,
        "shores": shores, "rails": rails, "walkNodes": graph_nodes, "walkEdges": graph_edges,
        "source": {"publisher": "OpenStreetMap contributors", "url": "https://www.openstreetmap.org/copyright",
                   "license": "ODbL-1.0", "licenseUrl": "https://opendatacommons.org/licenses/odbl/1-0/",
                   "retrievedAt": datetime.fromtimestamp(max(p.stat().st_mtime for p in paths), timezone.utc).isoformat(),
                   "note": "Street and footprint geometry is mapped. Missing heights are estimated. Sidewalk offsets and intersection connectors are illustrative; pedestrians are synthetic.",
                   "rejectedIndoorOrBuildingEdges": rejected_edges, "tiles": sources},
    }
    target = ROOT / "public/data/toronto.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    print(json.dumps({"buildings": len(buildings), "roads": len(roads), "parks": len(parks),
                      "shoreSegments": len(shores), "walkNodes": len(graph_nodes),
                      "walkEdges": len(graph_edges), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=ROOT / ".data-cache")
    prepare(parser.parse_args().cache)
