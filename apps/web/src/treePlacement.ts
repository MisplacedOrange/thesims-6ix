import type { Point, Road } from './district.ts';

export const TREE_CANOPY_RADIUS = 3;
export const TREE_TRUNK_RADIUS = 1.2;

const MAX_TREE_SIZE = 1.45;
const MAX_CANOPY_RADIUS = TREE_CANOPY_RADIUS * MAX_TREE_SIZE;
const ROAD_CLEARANCE = 0.5;
const CELL_SIZE = 64;

type Segment = { a: Point; b: Point; halfWidth: number };
export type RoadClearanceIndex = Map<string, Segment[]>;

function cellKey(x: number, z: number): string {
  return `${x},${z}`;
}

export function buildRoadClearanceIndex(roads: readonly Pick<Road, 'width' | 'points'>[]): RoadClearanceIndex {
  const cells: RoadClearanceIndex = new Map();
  for (const road of roads) {
    const halfWidth = Math.max(0, road.width) / 2;
    const expansion = halfWidth + MAX_CANOPY_RADIUS + ROAD_CLEARANCE;
    for (let i = 0; i < road.points.length - 1; i++) {
      const a = road.points[i]!, b = road.points[i + 1]!;
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 0.05) continue;
      const segment: Segment = { a, b, halfWidth };
      const minX = Math.floor((Math.min(a[0], b[0]) - expansion) / CELL_SIZE);
      const maxX = Math.floor((Math.max(a[0], b[0]) + expansion) / CELL_SIZE);
      const minZ = Math.floor((Math.min(a[1], b[1]) - expansion) / CELL_SIZE);
      const maxZ = Math.floor((Math.max(a[1], b[1]) + expansion) / CELL_SIZE);
      for (let x = minX; x <= maxX; x++) for (let z = minZ; z <= maxZ; z++) {
        const key = cellKey(x, z);
        const bucket = cells.get(key);
        if (bucket) bucket.push(segment);
        else cells.set(key, [segment]);
      }
    }
  }
  return cells;
}

function distanceSquaredToSegment(point: Point, { a, b }: Segment): number {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const lengthSquared = dx * dx + dz * dz;
  const t = Math.max(0, Math.min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dz) / lengthSquared));
  const x = a[0] + t * dx, z = a[1] + t * dz;
  return (point[0] - x) ** 2 + (point[1] - z) ** 2;
}

export function isCircleClearOfRoads(point: Point, radius: number, roads: RoadClearanceIndex): boolean {
  const candidates = roads.get(cellKey(Math.floor(point[0] / CELL_SIZE), Math.floor(point[1] / CELL_SIZE)));
  if (!candidates) return true;
  return candidates.every(segment => {
    const clearance = segment.halfWidth + radius + ROAD_CLEARANCE;
    return distanceSquaredToSegment(point, segment) >= clearance * clearance;
  });
}
