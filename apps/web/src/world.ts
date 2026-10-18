import type { Building, Point, Road } from './district.ts';

export type Box = { minX: number; maxX: number; minZ: number; maxZ: number };
export type Flat = { x: number; z: number };

/** Extent of the OSM snapshot: building centroids are inside, roads cross it. */
export const CORE: Box = { minX: -1611, maxX: 1611, minZ: -1670, maxZ: 1670 };
/** The orbit target stays over the mapped city or the harbour in front of it. */
export const TARGET_LIMIT: Box = { minX: -1450, maxX: 1450, minZ: -1500, maxZ: 2300 };
/** The camera itself never leaves the procedural fill around the core. */
export const CAMERA_LIMIT: Box = { minX: -2500, maxX: 2500, minZ: -2500, maxZ: 3600 };
/** Filler buildings stop here; fog fully hides everything beyond. */
export const FILL_LIMIT: Box = { minX: -6400, maxX: 6400, minZ: -6400, maxZ: 6400 };
export const MAX_DISTANCE = 3700;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
export function clampToBox(p: Flat, box: Box): Flat {
  return { x: clamp(p.x, box.minX, box.maxX), z: clamp(p.z, box.minZ, box.maxZ) };
}

export function insidePolygon(point: Point, polygon: readonly Point[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]!, b = polygon[j]!;
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
export function polygonArea(polygon: readonly Point[]): number {
  let sum = 0;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) sum += polygon[j]![0] * polygon[i]![1] - polygon[i]![0] * polygon[j]![1];
  return sum / 2;
}
function bounds(polygon: readonly Point[]): Box {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity;
  for (const [x, z] of polygon) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z); }
  return { minX, maxX, minZ, maxZ };
}
function centroid(polygon: readonly Point[]): Point {
  const ring = ring0(polygon);
  return [ring.reduce((s, p) => s + p[0], 0) / ring.length, ring.reduce((s, p) => s + p[1], 0) / ring.length];
}
/** Drops the closing duplicate vertex of an OSM ring. */
export function ring0(polygon: readonly Point[]): Point[] {
  const first = polygon[0], last = polygon[polygon.length - 1];
  return first && last && first[0] === last[0] && first[1] === last[1] ? polygon.slice(0, -1) : polygon.slice();
}

/** Dominant street direction, folded into (-45°, 45°], from road length per degree. */
export function streetGridAngle(roads: readonly Pick<Road, 'kind' | 'points'>[]): number {
  const histogram = new Array<number>(90).fill(0);
  for (const road of roads) {
    if (!['primary', 'secondary', 'tertiary', 'residential'].includes(road.kind)) continue;
    for (let i = 0; i < road.points.length - 1; i++) {
      const a = road.points[i]!, b = road.points[i + 1]!;
      const degrees = ((Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI) % 90 + 90) % 90;
      histogram[Math.floor(degrees) % 90]! += Math.hypot(b[0] - a[0], b[1] - a[1]);
    }
  }
  const peak = histogram.indexOf(Math.max(...histogram)) + 0.5;
  return (peak > 45 ? peak - 90 : peak) * Math.PI / 180;
}

/** Joins mapped shore segments into one west-to-east line. */
export function joinShoreline(shores: readonly (readonly Point[])[]): Point[] {
  const base = shores.slice().sort((a, b) => b.length - a.length)[0];
  let line: Point[] = [...(base ?? [])];
  for (const s of shores) {
    if (!line.length || s === base) continue;
    const end = line[line.length - 1]!, first = s[0]!, last = s[s.length - 1]!;
    if (Math.hypot(end[0] - first[0], end[1] - first[1]) < 3) line = line.concat(s.slice(1));
    else if (Math.hypot(end[0] - last[0], end[1] - last[1]) < 3) line = line.concat(s.slice(0, -1).reverse());
  }
  if (line.length < 2) line = [[-4000, 1900], [4000, 900]];
  if (line[0]![0] > line[line.length - 1]![0]) line.reverse();
  return line;
}
/** Land north of the shoreline, extended flat beyond its mapped ends. */
export function landPolygon(shoreline: readonly Point[], reach: number): Point[] {
  const west = shoreline[0]!, east = shoreline[shoreline.length - 1]!;
  return [[-reach, -reach], [reach, -reach], [reach, east[1]], ...shoreline.slice().reverse(), [-reach, west[1]]];
}

/**
 * OSM maps tall buildings as an outline plus `building:part` pieces. Rendering
 * both stacks coplanar walls and roofs that flicker. Following Simple 3D
 * Buildings, an outline mostly covered by parts is dropped; parts inside an
 * outline that stays are inset so no faces coincide.
 */
export function resolveBuildingParts(buildings: readonly Building[]): Building[] {
  const info = buildings.map(b => ({ b, box: bounds(b.polygon), area: Math.abs(polygonArea(ring0(b.polygon))), c: centroid(b.polygon) }));
  const grid = new Map<string, number[]>();
  const cell = 80;
  info.forEach((item, i) => {
    for (let x = Math.floor(item.box.minX / cell); x <= Math.floor(item.box.maxX / cell); x++)
      for (let z = Math.floor(item.box.minZ / cell); z <= Math.floor(item.box.maxZ / cell); z++) {
        const key = x + ',' + z, bucket = grid.get(key);
        if (bucket) bucket.push(i); else grid.set(key, [i]);
      }
  });
  const dropped = new Set<number>(), insetIn = new Map<number, number>();
  info.forEach((outer, i) => {
    const candidates = new Set<number>();
    for (let x = Math.floor(outer.box.minX / cell); x <= Math.floor(outer.box.maxX / cell); x++)
      for (let z = Math.floor(outer.box.minZ / cell); z <= Math.floor(outer.box.maxZ / cell); z++)
        for (const j of grid.get(x + ',' + z) ?? []) if (j !== i) candidates.add(j);
    let covered = 0;
    const parts: number[] = [];
    for (const j of candidates) {
      const part = info[j]!;
      if (part.box.minX < outer.box.minX - 0.5 || part.box.maxX > outer.box.maxX + 0.5 ||
        part.box.minZ < outer.box.minZ - 0.5 || part.box.maxZ > outer.box.maxZ + 0.5) continue;
      const sameFootprint = part.area > outer.area * 0.97;
      if (sameFootprint) {
        // Identical footprints: keep the taller one; ties go to the lower index.
        if (part.b.height > outer.b.height || (part.b.height === outer.b.height && j < i)) dropped.add(i);
        continue;
      }
      // Parts usually share vertices with their outline, so test points nudged inward.
      const ring = ring0(part.b.polygon).map(p => [p[0] + (part.c[0] - p[0]) * 0.05, p[1] + (part.c[1] - p[1]) * 0.05] as const);
      if (!insidePolygon(part.c, outer.b.polygon) || ring.filter(p => insidePolygon(p, outer.b.polygon)).length < ring.length * 0.5) continue;
      // Raised parts (overhangs, upper storeys) don't stand in for the outline's lower floors.
      if (part.b.base <= outer.b.base + 1) covered += part.area;
      parts.push(j);
    }
    if (!parts.length) return;
    if (covered >= outer.area * 0.55) dropped.add(i);
    else for (const j of parts) insetIn.set(j, i);
  });
  const result: Building[] = [];
  info.forEach(({ b, box, c }, i) => {
    if (dropped.has(i)) return;
    const outerIndex = insetIn.get(i);
    if (outerIndex === undefined || dropped.has(outerIndex)) { result.push(b); return; }
    const outer = buildings[outerIndex]!;
    const scale = 1 - 0.7 / Math.max(2, box.maxX - box.minX, box.maxZ - box.minZ);
    const polygon = b.polygon.map(p => [c[0] + (p[0] - c[0]) * scale, c[1] + (p[1] - c[1]) * scale] as const);
    const height = Math.abs(b.height - outer.height) < 0.5 && b.height - 0.6 > b.base + 1 ? b.height - 0.6 : b.height;
    result.push({ ...b, polygon, height });
  });
  return result;
}

export type FillerKind = 'tower' | 'glass' | 'midrise' | 'brick' | 'house';
export type FillerBuilding = { x: number; z: number; width: number; depth: number; height: number; kind: FillerKind; seed: number };
export type FillerBlock = { x: number; z: number; width: number; depth: number; park: boolean };
export type Surroundings = { angle: number; blocks: FillerBlock[]; buildings: FillerBuilding[]; parkTrees: Point[] };

const BLOCK_U = 168, BLOCK_V = 118, STREET = 20;
/** Distance a point lies outside the mapped core, zero inside. */
export function outsideCore(x: number, z: number): number {
  return Math.max(0, CORE.minX - x, x - CORE.maxX, CORE.minZ - z, z - CORE.maxZ);
}
/** Approximate Don River valley centreline; it bends east toward the lake. */
export function donValleyX(z: number): number {
  return z < -890 ? 2256 + 0.4 * (z + 890) : 2256 + 0.08 * (z + 890);
}
export function inDonValley(x: number, z: number): boolean {
  return Math.abs(x - donValleyX(z)) < 190 && z < 1100;
}

/**
 * Procedural low-cost city around the mapped core, aligned to Toronto's grid.
 * Density follows the real pattern loosely: towers near the core edge, the
 * Yonge-Bloor cluster to the north, condos west, low-rise houses further out.
 */
export function buildSurroundings(angle: number, land: readonly Point[], seed = 2026): Surroundings {
  let state = seed >>> 0;
  const rand = () => { state = (state * 1664525 + 1013904223) >>> 0; return state / 4294967296; };
  const ux = Math.cos(angle), uz = Math.sin(angle), vx = -uz, vz = ux;
  const at = (u: number, v: number): Point => [u * ux + v * vx, u * uz + v * vz];
  const blocks: FillerBlock[] = [], buildings: FillerBuilding[] = [], parkTrees: Point[] = [];
  const reach = Math.hypot(FILL_LIMIT.maxX, FILL_LIMIT.maxZ);
  for (let i = Math.floor(-reach / BLOCK_U); i <= reach / BLOCK_U; i++) {
    for (let j = Math.floor(-reach / BLOCK_V); j <= reach / BLOCK_V; j++) {
      const width = BLOCK_U - STREET, depth = BLOCK_V - STREET;
      const [x, z] = at(i * BLOCK_U, j * BLOCK_V);
      if (x < FILL_LIMIT.minX || x > FILL_LIMIT.maxX || z < FILL_LIMIT.minZ || z > FILL_LIMIT.maxZ) continue;
      const corners = [at(i * BLOCK_U - width / 2, j * BLOCK_V - depth / 2), at(i * BLOCK_U + width / 2, j * BLOCK_V - depth / 2),
        at(i * BLOCK_U + width / 2, j * BLOCK_V + depth / 2), at(i * BLOCK_U - width / 2, j * BLOCK_V + depth / 2)];
      if (corners.some(([cx, cz]) => outsideCore(cx, cz) < 6 || !insidePolygon([cx, cz], land) || inDonValley(cx, cz))) continue;
      const edge = outsideCore(x, z);
      const park = rand() < 0.06;
      blocks.push({ x, z, width, depth, park });
      if (park) {
        for (let t = 0; t < 7; t++) parkTrees.push(at(i * BLOCK_U + (rand() - 0.5) * width * 0.85, j * BLOCK_V + (rand() - 0.5) * depth * 0.85));
        continue;
      }
      const yongeBloor = Math.hypot(x + 150, z + 2350), westCondos = Math.hypot(x + 2050, z - 650);
      const towerChance = 0.07 * Math.exp(-edge / 450) + 0.45 * Math.exp(-yongeBloor / 380) + 0.22 * Math.exp(-westCondos / 400);
      const suburban = edge > 900 && yongeBloor > 900;
      // Split the block into parcels along its long side, two rows deep.
      // Distant house rows read as one terrace, which keeps the instance count low.
      const lots = suburban ? (edge > 1700 ? 1 : 3) : 2 + Math.floor(rand() * 3);
      for (let row = 0; row < 2; row++) {
        let used = 0;
        for (let lot = 0; lot < lots; lot++) {
          const share = lot === lots - 1 ? width - used : width / lots * (0.75 + rand() * 0.5);
          const lotU = i * BLOCK_U - width / 2 + used + share / 2;
          used += share;
          const lotV = j * BLOCK_V + (row === 0 ? -1 : 1) * depth / 4;
          const r = rand();
          let kind: FillerKind, height: number;
          if (r < towerChance) { kind = rand() < 0.5 ? 'tower' : 'glass'; height = 55 + rand() * (yongeBloor < 600 ? 190 : 110); }
          else if (suburban) { kind = 'house'; height = 7 + rand() * 4; }
          else if (r < towerChance + 0.25 * Math.exp(-edge / 900)) { kind = 'midrise'; height = 16 + rand() * 20; }
          else { kind = 'brick'; height = 7 + rand() * 9; }
          const setback = kind === 'house' ? 3 + rand() * 3 : 1 + rand() * 2;
          const [bx, bz] = at(lotU, lotV);
          const isTall = kind === 'tower' || kind === 'glass';
          buildings.push({ x: bx, z: bz, width: Math.max(4, Math.min(share - setback * 2, isTall ? 38 : Infinity)),
            depth: Math.max(4, depth / 2 - setback * 2), height, kind, seed: rand() });
        }
      }
    }
  }
  return { angle, blocks, buildings, parkTrees };
}
