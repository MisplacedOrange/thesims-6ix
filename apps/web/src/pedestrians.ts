import { landmarks } from './district.ts';
import type { District, Point } from './district.ts';

type Neighbor = { to: number; distance: number };
export type Resident = {
  id: number; name: string; purpose: string; color: string; destination: string;
  route: Point[]; cumulative: number[]; length: number; speed: number; pause: number; offset: number;
};
export type Pose = { x: number; z: number; heading: number; walking: boolean; returning: boolean; progress: number; distance: number };
export type Crowd = { residents: Resident[]; usableNodes: number[] };
export type Inspection = {
  id: number; name: string; purpose: string; color: string; destination: string; activity: string;
  speed: number; progress: number; routeLength: number; x: number; z: number;
};
const names = ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan', 'Avery', 'Robin', 'Jamie', 'Casey', 'Riley', 'Cameron', 'Devon'];
const purposes = ['Out for a walk', 'Exploring downtown', 'Meeting a friend', 'On the way to work', 'Taking the scenic route'];
const colors = ['#daf3a6', '#f4c680', '#78c8be', '#e89d85', '#90b9d4', '#c3acd9'];

function random(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let n = Math.imul(state ^ state >>> 15, 1 | state);
    n ^= n + Math.imul(n ^ n >>> 7, 61 | n);
    return ((n ^ n >>> 14) >>> 0) / 4294967296;
  };
}
function length(a: Point, b: Point): number { return Math.hypot(a[0] - b[0], a[1] - b[1]); }

class Heap {
  values: { node: number; distance: number }[] = [];
  push(node: number, distance: number): void {
    const item = { node, distance };
    this.values.push(item);
    let i = this.values.length - 1;
    while (i > 0) {
      const p = (i - 1) >> 1, parent = this.values[p];
      if (!parent || parent.distance <= distance) break;
      this.values[i] = parent; i = p;
    }
    this.values[i] = item;
  }
  pop(): { node: number; distance: number } | undefined {
    const top = this.values[0], tail = this.values.pop();
    if (!top || !tail || this.values.length === 0) return top;
    let i = 0;
    while (true) {
      let c = i * 2 + 1;
      const left = this.values[c];
      if (!left) break;
      const right = this.values[c + 1];
      if (right && right.distance < left.distance) c++;
      const child = this.values[c];
      if (!child || child.distance >= tail.distance) break;
      this.values[i] = child; i = c;
    }
    this.values[i] = tail;
    return top;
  }
}

function shortestTree(graph: Neighbor[][], target: number): Int32Array {
  const distance = new Float64Array(graph.length).fill(Infinity);
  const next = new Int32Array(graph.length).fill(-1);
  const heap = new Heap();
  distance[target] = 0; heap.push(target, 0);
  while (heap.values.length) {
    const item = heap.pop();
    if (!item || item.distance > distance[item.node]!) continue;
    for (const edge of graph[item.node] ?? []) {
      const candidate = item.distance + edge.distance;
      if (candidate < distance[edge.to]!) {
        distance[edge.to] = candidate; next[edge.to] = item.node; heap.push(edge.to, candidate);
      }
    }
  }
  return next;
}

export function createCrowd(district: Pick<District, 'walkNodes' | 'walkEdges'>, count: number, seed = 2026): Crowd {
  const graph: Neighbor[][] = Array.from({ length: district.walkNodes.length }, () => []);
  for (const [a, b] of district.walkEdges) {
    const p = district.walkNodes[a], q = district.walkNodes[b];
    if (!p || !q) continue;
    const distance = length(p, q);
    graph[a]?.push({ to: b, distance }); graph[b]?.push({ to: a, distance });
  }
  const seen = new Set<number>();
  let usableNodes: number[] = [];
  graph.forEach((_, start) => {
    if (seen.has(start)) return;
    const component = [start]; seen.add(start);
    for (let i = 0; i < component.length; i++) {
      for (const e of graph[component[i]!] ?? []) {
        if (!seen.has(e.to)) { seen.add(e.to); component.push(e.to); }
      }
    }
    if (component.length > usableNodes.length) usableNodes = component;
  });
  if (usableNodes.length < 2) throw new Error('The Toronto walking network is not connected.');
  const destinations = landmarks.map(l => {
    let node = usableNodes[0]!;
    for (const id of usableNodes) {
      if (length(district.walkNodes[id]!, l.point) < length(district.walkNodes[node]!, l.point)) node = id;
    }
    return { name: l.name, node, tree: shortestTree(graph, node) };
  });
  const rand = random(seed);
  const residents: Resident[] = [];
  for (let id = 0; id < count; id++) {
    const dest = destinations[Math.floor(rand() * destinations.length)]!;
    let current = usableNodes[Math.floor(rand() * usableNodes.length)]!;
    if (current === dest.node) current = usableNodes.find(n => n !== dest.node)!;
    const route: Point[] = [district.walkNodes[current]!];
    const cumulative = [0];
    while (current !== dest.node) {
      const next = dest.tree[current];
      if (next === undefined || next < 0 || route.length > usableNodes.length) throw new Error('Incomplete pedestrian route');
      const p = district.walkNodes[next]!;
      cumulative.push(cumulative[cumulative.length - 1]! + length(route[route.length - 1]!, p));
      route.push(p); current = next;
    }
    const speed = 0.95 + rand() * 0.65;
    const distance = cumulative[cumulative.length - 1]!;
    const pause = 30 + rand() * 80;
    residents.push({
      id, name: names[id % names.length]! + ' ' + String(id + 1).padStart(3, '0'),
      purpose: purposes[Math.floor(rand() * purposes.length)]!, color: colors[id % colors.length]!,
      destination: dest.name, route, cumulative, length: distance, speed, pause,
      offset: rand() * (distance / speed * 2 + pause * 2),
    });
  }
  return { residents, usableNodes };
}

export function sampleResident(resident: Resident, seconds: number): Pose {
  const travel = resident.length / resident.speed;
  const cycle = travel * 2 + resident.pause * 2;
  const time = ((seconds + resident.offset) % cycle + cycle) % cycle;
  const returning = time >= travel + resident.pause;
  const walking = time < travel || (returning && time < travel * 2 + resident.pause);
  const position = time < travel ? time * resident.speed : !returning ? resident.length
    : time < travel * 2 + resident.pause ? resident.length - (time - travel - resident.pause) * resident.speed : 0;
  let low = 0, high = resident.cumulative.length - 1;
  while (low < high - 1) {
    const mid = (low + high) >> 1;
    if (resident.cumulative[mid]! <= position) low = mid; else high = mid;
  }
  const a = resident.route[low]!, b = resident.route[Math.min(low + 1, resident.route.length - 1)]!;
  const segment = Math.max(0.001, resident.cumulative[Math.min(low + 1, resident.cumulative.length - 1)]! - resident.cumulative[low]!);
  const fraction = Math.max(0, Math.min(1, (position - resident.cumulative[low]!) / segment));
  return { x: a[0] + (b[0] - a[0]) * fraction, z: a[1] + (b[1] - a[1]) * fraction,
    heading: Math.atan2(b[0] - a[0], b[1] - a[1]) + (returning ? Math.PI : 0),
    walking, returning, progress: resident.length ? position / resident.length : 0, distance: position };
}

export function inspectResident(resident: Resident, seconds: number): Inspection {
  const p = sampleResident(resident, seconds);
  return { id: resident.id, name: resident.name, purpose: resident.purpose, color: resident.color,
    destination: p.returning ? 'Downtown neighbourhood' : resident.destination,
    activity: p.walking ? 'Walking' : 'Taking a break', speed: resident.speed,
    progress: p.returning ? 1 - p.progress : p.progress, routeLength: resident.length, x: p.x, z: p.z };
}
