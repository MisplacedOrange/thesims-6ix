import * as THREE from 'three';
import type { Building, Point } from './district.ts';
import { insidePolygon, polygonArea, ring0 } from './world.ts';
import type { FillerBuilding, FillerKind } from './world.ts';

/** Facade styles understood by the shader; the value is stored per vertex. */
export const Style = { glass: 0, concrete: 1, brick: 2, condo: 3, plain: 4, house: 5 } as const;
type StyleId = typeof Style[keyof typeof Style];
export type FacadeUniforms = { uNight: { value: number } };

const hex = (values: string[]) => values.map(v => new THREE.Color(v));
const palettes: Record<StyleId, THREE.Color[]> = {
  [Style.glass]: hex(['#5d7684', '#4d6670', '#6b8a92', '#56646e', '#7b8f99', '#476070', '#6f7570']),
  [Style.concrete]: hex(['#b8b2a6', '#a9a49a', '#c9c2b2', '#9c9890', '#bdb6a8', '#a39a8c', '#d0cbc0']),
  [Style.brick]: hex(['#8f4f3b', '#9d5c44', '#7f4636', '#b07a57', '#a8876a', '#94644c', '#6f4a3c', '#b69c7c']),
  [Style.condo]: hex(['#dedbd2', '#cfd2d0', '#e4e1d8', '#bfc4c4', '#d2cbbd', '#a9b0b2']),
  [Style.plain]: hex(['#b4b0a7', '#a6a39c', '#c0bcb2']),
  [Style.house]: hex(['#8e4f3c', '#a46b4f', '#b9a283', '#6f5a4e', '#c9bfae', '#9a5a46', '#d8d2c4']),
};
const flatRoofs = hex(['#8d8b86', '#7d7b77', '#9a978f', '#6e6d6a', '#a3a199', '#5f5e5b', '#b3b0a6']);
const greenRoof = new THREE.Color('#6d7f58');
const pitchedRoofs = hex(['#4a4643', '#5b524c', '#3f3d3c', '#6a5a50', '#5a5e60', '#734f40']);
const houseUses = new Set(['house', 'detached', 'semidetached_house', 'terrace', 'bungalow']);
const plainUses = new Set(['parking', 'garage', 'garages', 'roof', 'column', 'steps', 'bridge', 'service', 'construction', 'carport', 'shed']);
const shopUses = new Set(['retail', 'commercial', 'hotel', 'supermarket', 'office']);

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967296;
}
const pick = <T,>(list: readonly T[], r: number): T => list[Math.floor(r * list.length) % list.length]!;

type Look = { style: StyleId; shop: boolean; wall: THREE.Color; roof: THREE.Color; seed: number };
export function buildingLook(b: Building, top: number): Look {
  const r = hash(b.id), r2 = hash(b.id + '#'), use = b.use;
  let style: StyleId;
  if (plainUses.has(use)) style = Style.plain;
  else if (houseUses.has(use)) style = Style.house;
  else if (['church', 'cathedral', 'chapel', 'university', 'school', 'college'].includes(use)) style = Style.brick;
  else if (top >= 70) style = use === 'apartments' || use === 'residential' ? (r < 0.8 ? Style.condo : Style.glass)
    : use === 'office' || use === 'hotel' || use === 'commercial' ? (r < 0.75 ? Style.glass : Style.concrete)
    : r < 0.5 ? Style.glass : r < 0.85 ? Style.condo : Style.concrete;
  else if (top >= 24) style = use === 'apartments' ? (r < 0.55 ? Style.condo : Style.concrete)
    : r < 0.4 ? Style.concrete : r < 0.65 ? Style.brick : r < 0.82 ? Style.glass : Style.condo;
  else style = r < 0.68 ? Style.brick : Style.concrete;
  const wall = pick(palettes[style], r2).clone();
  if (['church', 'cathedral', 'chapel'].includes(use)) wall.set('#a39684');
  const shop = b.base < 1 && top >= 7 && style !== Style.plain && style !== Style.house &&
    (shopUses.has(use) || (use === 'yes' && r2 < 0.45) || (use === 'apartments' && r2 < 0.5));
  const roof = style === Style.house ? pick(pitchedRoofs, r2) : top > 30 && r2 > 0.9 ? greenRoof : pick(flatRoofs, hash(b.id + 'roof'));
  return { style, shop, wall, roof: roof.clone(), seed: r };
}

type V3 = readonly [number, number, number];
/** Accumulates flat-shaded faces with the per-vertex facade attributes. */
class Mesher {
  private readonly position: number[] = [];
  private readonly normal: number[] = [];
  private readonly color: number[] = [];
  private readonly facade: number[] = [];
  private readonly index: number[] = [];
  private colorNow: THREE.Color = new THREE.Color();
  private facadeNow: [number, number, number, number] = [0, 0, 0, 0];

  use(color: THREE.Color, style: number, shop: boolean, seed: number, base: number, top: number): void {
    this.colorNow = color; this.facadeNow = [style + (shop ? 10 : 0), seed, base, top];
  }
  private vertex(p: V3, n: V3): number {
    this.position.push(p[0], p[1], p[2]); this.normal.push(n[0], n[1], n[2]);
    this.color.push(this.colorNow.r, this.colorNow.g, this.colorNow.b); this.facade.push(...this.facadeNow);
    return this.position.length / 3 - 1;
  }
  /** Convex face; the winding is flipped as needed so its normal follows `hint`. */
  face(points: V3[], hint: V3): void {
    const [a, b, c] = points as [V3, V3, V3];
    let nx = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]);
    let ny = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]);
    let nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    const flip = nx * hint[0] + ny * hint[1] + nz * hint[2] < 0, length = Math.hypot(nx, ny, nz) || 1;
    if (flip) { nx = -nx; ny = -ny; nz = -nz; }
    const n: V3 = [nx / length, ny / length, nz / length];
    const ids = points.map(p => this.vertex(p, n));
    if (flip) ids.reverse();
    for (let i = 1; i < ids.length - 1; i++) this.index.push(ids[0]!, ids[i]!, ids[i + 1]!);
  }
  /** Horizontal polygon facing up at height y. */
  cap(ring: readonly Point[], y: number): void {
    const contour = ring.map(([x, z]) => new THREE.Vector2(x, z));
    const ids = ring.map(([x, z]) => this.vertex([x, y, z], [0, 1, 0]));
    for (const [a, b, c] of THREE.ShapeUtils.triangulateShape(contour, [])) {
      const pa = ring[a!]!, pb = ring[b!]!, pc = ring[c!]!;
      const up = (pb[1] - pa[1]) * (pc[0] - pa[0]) - (pb[0] - pa[0]) * (pc[1] - pa[1]) > 0;
      this.index.push(ids[a!]!, ...(up ? [ids[b!]!, ids[c!]!] : [ids[c!]!, ids[b!]!]));
    }
  }
  geometry(): THREE.BufferGeometry {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(this.position, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(this.normal, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(this.color, 3));
    g.setAttribute('facade', new THREE.Float32BufferAttribute(this.facade, 4));
    g.setIndex(this.index);
    g.computeBoundingSphere();
    return g;
  }
}

function cleanRing(polygon: readonly Point[]): Point[] {
  const ring: Point[] = [];
  for (const p of ring0(polygon)) {
    const last = ring[ring.length - 1];
    if (!last || Math.hypot(p[0] - last[0], p[1] - last[1]) > 0.05) ring.push(p);
  }
  return ring;
}
function walls(m: Mesher, ring: readonly Point[], bottom: number, top: number): void {
  const orientation = Math.sign(polygonArea(ring)) || 1;
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i]!, b = ring[(i + 1) % ring.length]!;
    const dx = b[0] - a[0], dz = b[1] - a[1];
    // Outward is to the right of travel for counter-clockwise rings in (x, z).
    const out: V3 = [dz * orientation, 0, -dx * orientation];
    m.face([[a[0], bottom, a[1]], [b[0], bottom, b[1]], [b[0], top, b[1]], [a[0], top, a[1]]], out);
  }
}
/** Gabled roof for small rectangular houses; returns false if the footprint isn't one. */
function gable(m: Mesher, ring: readonly Point[], bottom: number, top: number, roof: THREE.Color): boolean {
  if (ring.length !== 4) return false;
  const edge = (i: number) => { const a = ring[i]!, b = ring[(i + 1) % 4]!; return [b[0] - a[0], b[1] - a[1]] as const; };
  for (let i = 0; i < 4; i++) {
    const e = edge(i), f = edge((i + 1) % 4);
    if (Math.abs(e[0] * f[0] + e[1] * f[1]) > 0.2 * Math.hypot(...e) * Math.hypot(...f)) return false;
  }
  const long = Math.hypot(...edge(0)) >= Math.hypot(...edge(1)) ? 0 : 1;
  const span = Math.hypot(...edge(long + 1));
  const rise = Math.min(span * 0.42, 4.5), eave = top - rise;
  if (span > 16 || eave < bottom + 2.5) return false;
  const [p0, p1, p2, p3] = [0, 1, 2, 3].map(i => ring[(i + long) % 4]!) as [Point, Point, Point, Point];
  const mid = (a: Point, b: Point): Point => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const r0 = mid(p0, p3), r1 = mid(p1, p2);
  walls(m, ring, bottom, eave);
  const at = (p: Point, y: number): V3 => [p[0], y, p[1]];
  const outward = (a: Point, b: Point): V3 => { const c = mid(a, b), o = mid(r0, r1); return [c[0] - o[0], 0, c[1] - o[1]]; };
  m.face([at(p1, eave), at(p2, eave), at(r1, top)], outward(p1, p2));
  m.face([at(p3, eave), at(p0, eave), at(r0, top)], outward(p3, p0));
  m.use(roof, Style.plain, false, 0, bottom, top);
  m.face([at(p0, eave), at(p1, eave), at(r1, top), at(r0, top)], [0, 1, 0]);
  m.face([at(p2, eave), at(p3, eave), at(r0, top), at(r1, top)], [0, 1, 0]);
  return true;
}
/** Small mechanical penthouse centred on the roof when it fits inside the footprint. */
function rooftopUnit(m: Mesher, ring: readonly Point[], top: number, seed: number): void {
  let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity, cx = 0, cz = 0;
  for (const [x, z] of ring) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z); cx += x / ring.length; cz += z / ring.length; }
  const half = Math.min(18, Math.max(3, Math.min(maxX - minX, maxZ - minZ) * 0.17));
  const box: Point[] = [[cx - half, cz - half], [cx + half, cz - half], [cx + half, cz + half], [cx - half, cz + half]];
  if (!box.every(p => insidePolygon(p, ring)) || !insidePolygon([cx, cz], ring)) return;
  const height = 3.5 + seed * 3;
  m.use(palettes[Style.plain][Math.floor(seed * 3)]!, Style.plain, false, seed, top, top + height);
  walls(m, box, top, top + height);
  m.cap(box, top + height);
}

/** One merged mesh for every mapped building: walls and roofs only, no hidden floors. */
export function buildingGeometry(buildings: readonly Building[], skip: (b: Building) => boolean): THREE.BufferGeometry {
  const m = new Mesher();
  for (const b of buildings) {
    if (skip(b)) continue;
    const ring = cleanRing(b.polygon);
    if (ring.length < 3) continue;
    const top = Math.max(b.base + 3, b.height), bottom = b.base;
    const look = buildingLook(b, top);
    m.use(look.wall, look.style, look.shop, look.seed, bottom, top);
    if (look.style === Style.house && top < 16 && gable(m, ring, bottom, top, look.roof)) continue;
    walls(m, ring, bottom, top);
    m.use(look.roof, Style.plain, false, look.seed, bottom, top);
    m.cap(ring, top);
    if (top >= 30 && top - bottom > 12 && look.style !== Style.house) rooftopUnit(m, ring, top, look.seed);
  }
  return m.geometry();
}

const fillerStyles: Record<FillerKind, StyleId> = { tower: Style.condo, glass: Style.glass, midrise: Style.concrete, brick: Style.brick, house: Style.house };
/** Instanced boxes for the procedural surroundings; one draw call. */
export function fillerMesh(items: readonly FillerBuilding[], angle: number, material: THREE.Material): THREE.InstancedMesh {
  const box = new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
  const facade = new Float32Array(items.length * 4);
  const mesh = new THREE.InstancedMesh(box, material, items.length);
  const dummy = new THREE.Object3D();
  items.forEach((item, i) => {
    const style = fillerStyles[item.kind];
    dummy.position.set(item.x, 0, item.z); dummy.rotation.set(0, -angle, 0); dummy.scale.set(item.width, item.height, item.depth);
    dummy.updateMatrix(); mesh.setMatrixAt(i, dummy.matrix);
    mesh.setColorAt(i, pick(palettes[style], item.seed));
    facade.set([style + (item.kind === 'brick' && item.seed < 0.5 ? 10 : 0), item.seed, 0, item.height], i * 4);
  });
  box.setAttribute('facade', new THREE.InstancedBufferAttribute(facade, 4));
  mesh.castShadow = true; mesh.receiveShadow = true;
  return mesh;
}

/**
 * Standard PBR material with a procedural facade: windows per floor and bay,
 * storefronts, parapets and ground contact shading. Patterns fade to their
 * average once a window spans under ~2 pixels, so distant towers don't shimmer.
 */
export function facadeMaterial(uniforms: FacadeUniforms, instanced: boolean): THREE.MeshStandardMaterial {
  const material = new THREE.MeshStandardMaterial({ vertexColors: !instanced, roughness: 0.88, metalness: 0 });
  material.onBeforeCompile = shader => {
    shader.uniforms.uNight = uniforms.uNight;
    if (instanced) shader.fragmentShader = '#define FACADE_INSTANCED\n' + shader.fragmentShader;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec4 facade;\nvarying vec4 vFacade;\nvarying vec3 vFacadePos;\nvarying vec3 vFacadeNormal;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        mat4 facadeModel = modelMatrix;
        #ifdef USE_INSTANCING
          facadeModel = modelMatrix * instanceMatrix;
        #endif
        vFacade = facade;
        vFacadePos = (facadeModel * vec4(transformed, 1.0)).xyz;
        vFacadeNormal = normalize(mat3(facadeModel) * objectNormal);`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>
        uniform float uNight;
        varying vec4 vFacade;
        varying vec3 vFacadePos;
        varying vec3 vFacadeNormal;
        float facadeHash(vec2 p) {
          vec3 p3 = fract(vec3(p.xyx) * 0.1031);
          p3 += dot(p3, p3.yzx + 33.33);
          return fract((p3.x + p3.y) * p3.z);
        }
        float facadeBlur(vec2 cell) { vec2 w = fwidth(cell); return clamp(max(w.x, w.y) * 1.6 - 0.35, 0.0, 1.0); }
        float facadeWindows(vec2 cell, vec2 size) {
          vec2 w = max(fwidth(cell), vec2(1e-4));
          vec2 d = abs(fract(cell) - 0.5) - size * 0.5;
          vec2 m = 1.0 - smoothstep(-w, w, d);
          return mix(m.x * m.y, size.x * size.y, facadeBlur(cell));
        }`)
      .replace('#include <color_fragment>', `#include <color_fragment>
        vec3 fN = normalize(vFacadeNormal);
        float fShop = step(9.5, vFacade.x);
        float fStyle = floor(vFacade.x - fShop * 10.0 + 0.5);
        float fSeed = vFacade.y;
        float fWall = 1.0 - step(0.6, abs(fN.y));
        float fH = vFacadePos.y - vFacade.z;
        float fU = dot(vFacadePos.xz, vec2(-fN.z, fN.x));
        vec3 fBase = diffuseColor.rgb;
        float fGlass = 0.0, fLit = 0.0, fShopLit = 0.0;
        if (fWall > 0.5) {
          vec2 bay = vec2(3.3, 3.4), win = vec2(0.4, 0.5);
          if (fStyle < 0.5) { bay = vec2(1.6, 4.0); win = vec2(0.93, 0.72); }
          else if (fStyle < 1.5) { bay = vec2(3.0, 3.7); win = vec2(0.56, 0.52); }
          else if (fStyle < 2.5) { bay = vec2(3.3, 3.4); win = vec2(0.40, 0.50); }
          else if (fStyle < 3.5) { bay = vec2(3.6, 3.0); win = vec2(0.90, 0.68); }
          else if (fStyle < 4.5) { win = vec2(0.0); }
          else { bay = vec2(4.2, 3.0); win = vec2(0.30, 0.42); }
          float inShop = fShop * (1.0 - step(4.6, fH));
          vec2 cell = inShop > 0.5 ? vec2(fU / 5.5, fH / 4.6) : vec2(fU / bay.x, (fH - fShop * 4.6) / bay.y);
          vec2 size = inShop > 0.5 ? vec2(0.86, 0.72) : win;
          float m = facadeWindows(cell, size);
          float cellRand = facadeHash(floor(cell) + fSeed * 91.7);
          float blur = facadeBlur(cell);
          vec3 frame = fStyle < 0.5 ? fBase * 0.72 + 0.03 : fBase;
          vec3 glass = fStyle < 0.5 ? mix(fBase * 0.45, vec3(0.03, 0.05, 0.06), 0.35) : vec3(0.03, 0.045, 0.055);
          glass *= mix(0.75 + 0.5 * cellRand, 1.0, blur);
          float cap = (1.0 - step(0.9, vFacade.w - vFacadePos.y)) * step(0.5, fStyle) * (1.0 - step(3.5, fStyle));
          m *= 1.0 - cap;
          diffuseColor.rgb = mix(mix(frame, frame * 1.12 + 0.02, cap), glass, m);
          fGlass = m;
          float on = step(0.72, facadeHash(floor(cell) + fSeed * 53.1 + 7.0));
          fLit = m * mix(on, 0.12, blur) * (1.0 - inShop);
          fShopLit = m * inShop;
          diffuseColor.rgb *= mix(0.6, 1.0, smoothstep(0.0, 7.0, vFacadePos.y));
        } else {
          #ifdef FACADE_INSTANCED
            fBase = fStyle > 4.5 ? vec3(0.05, 0.045, 0.042) * (0.8 + 0.6 * fSeed) : vec3(0.13 + 0.16 * fSeed) * vec3(1.0, 0.98, 0.94);
          #endif
          vec2 grit = vFacadePos.xz * 0.5;
          float gritFade = 1.0 - clamp(max(fwidth(grit).x, fwidth(grit).y) * 2.0, 0.0, 1.0);
          diffuseColor.rgb = fBase * (1.0 + (facadeHash(floor(grit)) - 0.5) * 0.12 * gritFade);
        }`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = mix(roughnessFactor, 0.14, fGlass);`)
      .replace('#include <metalnessmap_fragment>', `#include <metalnessmap_fragment>
        metalnessFactor = mix(metalnessFactor, fStyle < 0.5 ? 0.7 : 0.45, fGlass);`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        totalEmissiveRadiance += uNight * (fLit * vec3(1.0, 0.62, 0.3) * 0.9 + fShopLit * vec3(1.0, 0.75, 0.45) * 1.2);
      `);
  };
  material.customProgramCacheKey = () => 'facade-' + instanced;
  return material;
}
