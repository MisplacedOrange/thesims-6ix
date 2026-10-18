export type Point = readonly [x: number, z: number];
export type Building = {
  id: string; name: string; polygon: Point[]; height: number; base: number;
  basis: 'tag' | 'levels' | 'estimate'; use: string;
};
export type Road = {
  id: string; name: string; kind: string; width: number; points: Point[]; bridge: boolean;
};
export type Area = { id: string; name: string; polygon: Point[] };
export type Runway = { id: string; width: number; points: Point[] };
export type Islands = { islands: Area[]; runways: Runway[] };
export type WalkEdge = readonly [from: number, to: number, kind: 'footpath' | 'sidewalk' | 'crossing'];
export type Landmark = {
  id: string; name: string; short: string; point: Point; height: number; description: string;
};
export type District = {
  buildings: Building[]; roads: Road[]; parks: Area[]; water: Area[]; shores: Point[][]; rails: Point[][];
  walkNodes: Point[]; walkEdges: WalkEdge[];
  source: { publisher: string; url: string; license: string; retrievedAt: string; note: string };
};

export function project(lon: number, lat: number): Point {
  return [(lon + 79.385) * 111320 * Math.cos(43.65 * Math.PI / 180), (43.65 - lat) * 111320];
}

export const landmarks: Landmark[] = [
  { id: 'cn', name: 'CN Tower', short: 'CN TOWER', point: project(-79.387054, 43.642567), height: 553,
    description: 'Toronto’s unmistakable landmark above the railway lands.' },
  { id: 'rogers', name: 'Rogers Centre', short: 'ROGERS CENTRE', point: project(-79.38935, 43.64165), height: 75,
    description: 'The dome at the heart of the Entertainment District.' },
  { id: 'union', name: 'Union Station', short: 'UNION STATION', point: project(-79.3806, 43.64535), height: 35,
    description: 'A downtown meeting point where the city comes and goes.' },
  { id: 'waterfront', name: 'Harbourfront', short: 'HARBOURFRONT', point: project(-79.3824, 43.6389), height: 12,
    description: 'Lakeside paths, open space, and a slower pace along Queens Quay.' },
  { id: 'financial', name: 'Financial District', short: 'FINANCIAL DISTRICT', point: project(-79.3816, 43.6486), height: 310,
    description: 'A layered skyline of downtown towers and narrow streets.' },
  { id: 'stlawrence', name: 'St. Lawrence Market', short: 'ST. LAWRENCE', point: project(-79.3716, 43.6487), height: 24,
    description: 'Historic streets and brick blocks on the east side of downtown.' },
  { id: 'cityhall', name: 'Nathan Phillips Square', short: 'CITY HALL', point: project(-79.3839, 43.6525), height: 90,
    description: 'An open civic square between Old City Hall and the curved towers.' },
  { id: 'berczy', name: 'Berczy Park', short: 'BERCZY PARK', point: project(-79.3755, 43.6482), height: 9,
    description: 'A small green pocket tucked into the historic city.' },
];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}
function record(v: unknown): Record<string, unknown> {
  if (!isRecord(v)) throw new Error('Invalid map record');
  return v;
}
function num(v: unknown): number {
  if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error('Invalid map coordinate');
  return v;
}
function text(v: unknown): string {
  if (typeof v !== 'string') throw new Error('Invalid map text');
  return v;
}
function list<T>(v: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(v)) throw new Error('Invalid map collection');
  return v.map(parse);
}
function point(v: unknown): Point {
  if (!Array.isArray(v) || v.length !== 2) throw new Error('Invalid map point');
  return [num(v[0]), num(v[1])];
}
function area(v: unknown): Area {
  const a = record(v);
  return { id: text(a.id), name: text(a.name), polygon: list(a.polygon, point) };
}
export function parseDistrict(v: unknown): District {
  const d = record(v);
  if (d.schema !== 1) throw new Error('Unsupported Toronto map version');
  const walkNodes = list(d.walkNodes, point);
  const source = record(d.source);
  return {
    buildings: list(d.buildings, v => {
      const b = record(v);
      if (b.basis !== 'tag' && b.basis !== 'levels' && b.basis !== 'estimate') throw new Error('Invalid height basis');
      const polygon = list(b.polygon, point);
      if (polygon.length < 4) throw new Error('Incomplete building footprint');
      const height = num(b.height), base = num(b.base);
      if (height <= 0 || base < 0) throw new Error('Invalid building height');
      return { id: text(b.id), name: text(b.name), polygon, height, base, basis: b.basis, use: text(b.use) };
    }),
    roads: list(d.roads, v => {
      const r = record(v);
      if (typeof r.bridge !== 'boolean') throw new Error('Invalid bridge flag');
      return { id: text(r.id), name: text(r.name), kind: text(r.kind), width: num(r.width), points: list(r.points, point), bridge: r.bridge };
    }),
    parks: list(d.parks, area), water: list(d.water, area),
    shores: list(d.shores, v => list(v, point)), rails: list(d.rails, v => list(v, point)), walkNodes,
    walkEdges: list(d.walkEdges, v => {
      if (!Array.isArray(v) || v.length !== 3) throw new Error('Invalid walking edge');
      const a = num(v[0]), b = num(v[1]), kind: unknown = v[2];
      if (!Number.isInteger(a) || !Number.isInteger(b) || !walkNodes[a] || !walkNodes[b]) throw new Error('Missing walking node');
      if (kind !== 'footpath' && kind !== 'sidewalk' && kind !== 'crossing') throw new Error('Invalid walking edge kind');
      return [a, b, kind];
    }),
    source: { publisher: text(source.publisher), url: text(source.url), license: text(source.license),
      retrievedAt: text(source.retrievedAt), note: text(source.note) },
  };
}
export async function loadDistrict(): Promise<District> {
  const response = await fetch('/data/toronto.json');
  if (!response.ok) throw new Error('The Toronto map could not be loaded. Please reload the page.');
  const value: unknown = await response.json();
  return parseDistrict(value);
}
export function parseIslands(v: unknown): Islands {
  const d = record(v);
  if (d.schema !== 1) throw new Error('Unsupported islands map version');
  return {
    islands: list(d.islands, v => {
      const a = area(v);
      if (a.polygon.length < 4) throw new Error('Incomplete island outline');
      return a;
    }),
    runways: list(d.runways, v => {
      const r = record(v);
      const width = num(r.width), points = list(r.points, point);
      if (width <= 0 || points.length < 2) throw new Error('Invalid runway');
      return { id: text(r.id), width, points };
    }),
  };
}
export async function loadIslands(): Promise<Islands> {
  const response = await fetch('/data/islands.json');
  if (!response.ok) throw new Error('The Toronto Islands could not be loaded. Please reload the page.');
  const value: unknown = await response.json();
  return parseIslands(value);
}
