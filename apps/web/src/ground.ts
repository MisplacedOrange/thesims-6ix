import * as THREE from 'three';
import type { Point } from './district.ts';
import { ring0 } from './world.ts';

/**
 * Builds flat ground geometry in one buffer. UVs are world metres / `uvScale`
 * so tiling textures line up across every piece of a layer.
 */
export class GroundBuilder {
  private readonly position: number[] = [];
  private readonly uv: number[] = [];
  private readonly index: number[] = [];
  constructor(private readonly uvScale = 50) {}

  private vertex(x: number, y: number, z: number, u = x / this.uvScale, v = z / this.uvScale): number {
    this.position.push(x, y, z); this.uv.push(u, v);
    return this.position.length / 3 - 1;
  }
  /** Polyline ribbon with mitred joints, so bends have no gaps or overlaps. */
  ribbon(points: readonly Point[], width: number, y: number, alongScale = 0): void {
    const pts: Point[] = [];
    for (const p of points) { const last = pts[pts.length - 1]; if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) > 0.05) pts.push(p); }
    if (pts.length < 2) return;
    const half = width / 2;
    let previous = -1, distance = 0;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i]!, a = pts[Math.max(0, i - 1)]!, b = pts[Math.min(pts.length - 1, i + 1)]!;
      const inDir = i > 0 ? norm(p[0] - a[0], p[1] - a[1]) : norm(b[0] - p[0], b[1] - p[1]);
      const outDir = i < pts.length - 1 ? norm(b[0] - p[0], b[1] - p[1]) : inDir;
      const n0: Point = [-inDir[1], inDir[0]], n1: Point = [-outDir[1], outDir[0]];
      const miter = norm(n0[0] + n1[0], n0[1] + n1[1]);
      const length = half / Math.max(0.5, miter[0] * n1[0] + miter[1] * n1[1]);
      if (i > 0) distance += Math.hypot(p[0] - a[0], p[1] - a[1]);
      const lx = p[0] + miter[0] * length, lz = p[1] + miter[1] * length, rx = p[0] - miter[0] * length, rz = p[1] - miter[1] * length;
      const left = alongScale ? this.vertex(lx, y, lz, distance / alongScale, 0) : this.vertex(lx, y, lz);
      const right = alongScale ? this.vertex(rx, y, rz, distance / alongScale, 1) : this.vertex(rx, y, rz);
      if (previous >= 0) this.index.push(previous, left, previous + 1, left, right, previous + 1);
      previous = left;
    }
  }
  /** Round cap that fills the wedge where separate road ways meet. */
  disc(p: Point, radius: number, y: number, segments = 8): void {
    const centre = this.vertex(p[0], y, p[1]);
    for (let i = 0; i < segments; i++) {
      const a = i / segments * Math.PI * 2;
      this.vertex(p[0] + Math.cos(a) * radius, y, p[1] + Math.sin(a) * radius);
    }
    for (let i = 0; i < segments; i++) this.index.push(centre, centre + 1 + (i + 1) % segments, centre + 1 + i);
  }
  polygon(polygon: readonly Point[], y: number): void {
    const ring = ring0(polygon);
    if (ring.length < 3) return;
    const ids = ring.map(([x, z]) => this.vertex(x, y, z));
    for (const [a, b, c] of THREE.ShapeUtils.triangulateShape(ring.map(([x, z]) => new THREE.Vector2(x, z)), [])) {
      const pa = ring[a!]!, pb = ring[b!]!, pc = ring[c!]!;
      const up = (pb[1] - pa[1]) * (pc[0] - pa[0]) - (pb[0] - pa[0]) * (pc[1] - pa[1]) > 0;
      this.index.push(ids[a!]!, ...(up ? [ids[b!]!, ids[c!]!] : [ids[c!]!, ids[b!]!]));
    }
  }
  /** Vertical strip along a line, e.g. a quay wall; render double sided. */
  wall(points: readonly Point[], bottom: number, top: number): void {
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i]!, b = points[i + 1]!;
      const ids = [this.vertex(a[0], bottom, a[1]), this.vertex(b[0], bottom, b[1]), this.vertex(b[0], top, b[1]), this.vertex(a[0], top, a[1])];
      this.index.push(ids[0]!, ids[1]!, ids[2]!, ids[0]!, ids[2]!, ids[3]!);
    }
  }
  get empty(): boolean { return this.index.length === 0; }
  geometry(): THREE.BufferGeometry {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.position, 3));
    g.setAttribute('uv', new THREE.Float32BufferAttribute(this.uv, 2));
    g.setIndex(this.index);
    g.computeVertexNormals();
    g.computeBoundingSphere();
    return g;
  }
}
function norm(x: number, z: number): Point {
  const length = Math.hypot(x, z) || 1;
  return [x / length, z / length];
}

/**
 * Ground layers are painted in a fixed order without depth writes, so
 * overlapping roads, sidewalks and parks never fight over the same depth.
 */
export function groundLayer(builder: GroundBuilder, material: THREE.Material, order: number): THREE.Mesh | null {
  if (builder.empty) return null;
  material.depthWrite = false;
  material.polygonOffset = true; material.polygonOffsetFactor = -1; material.polygonOffsetUnits = -order;
  const mesh = new THREE.Mesh(builder.geometry(), material);
  mesh.renderOrder = order; mesh.receiveShadow = true;
  return mesh;
}
