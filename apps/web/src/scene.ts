import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { landmarks } from './district.ts';
import type { District, Point } from './district.ts';
import { createCrowd, inspectResident, sampleResident } from './pedestrians.ts';
import type { Crowd, Inspection } from './pedestrians.ts';
import { buildRoadClearanceIndex, isCircleClearOfRoads, TREE_CANOPY_RADIUS, TREE_TRUNK_RADIUS } from './treePlacement.ts';

export type Preset = 'skyline' | 'waterfront' | 'oldtown' | 'street';
export type Lighting = 'day' | 'golden' | 'blue';
export type Layer = 'buildings' | 'greenery' | 'paths' | 'labels';
export type SceneTick = { seconds: number; walking: number; resting: number; selected: Inspection | null };
type CameraFlight = { from: THREE.Vector3; to: THREE.Vector3; targetFrom: THREE.Vector3; targetTo: THREE.Vector3; start: number };
const presets: Record<Preset, { position: [number, number, number]; target: [number, number, number] }> = {
  skyline: { position: [1900, 1720, 2850], target: [-100, 100, 340] },
  waterfront: { position: [1250, 1050, 2500], target: [-80, 160, 780] },
  oldtown: { position: [1700, 930, 1470], target: [910, 25, 160] },
  street: { position: [430, 240, 965], target: [180, 10, 520] },
};
const palette = ['#c7c7b7', '#c6cbbf', '#a7bcba', '#b5bdba', '#dbd6c1', '#d5c7b3', '#a5b0a9', '#bfbdad'];
const pathKinds = new Set(['footway', 'path', 'pedestrian', 'steps', 'cycleway']);
const lightRecipes = {
  day: { sky: '#e0eced', water: '#699995', sun: '#fff2d4', sunPower: 3.0, ambient: 2.2, exposure: 1.06 },
  golden: { sky: '#dce5df', water: '#467d7d', sun: '#ffdeb0', sunPower: 3.4, ambient: 1.7, exposure: 1.03 },
  blue: { sky: '#253e4b', water: '#254d5b', sun: '#b0c8ef', sunPower: 1.2, ambient: 1.4, exposure: 0.95 },
};

function shape(points: readonly Point[]): THREE.Shape {
  const result = new THREE.Shape();
  points.forEach((p, i) => { if (i === 0) result.moveTo(p[0], -p[1]); else result.lineTo(p[0], -p[1]); });
  result.closePath();
  return result;
}
function flat(points: readonly Point[], y: number): THREE.BufferGeometry {
  const geometry = new THREE.ShapeGeometry(shape(points));
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, y, 0);
  return geometry;
}
function ribbon(points: readonly Point[], width: number, y: number): THREE.BufferGeometry {
  const positions: number[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]!, b = points[i + 1]!, length = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (length < 0.05) continue;
    const nx = -(b[1] - a[1]) / length * width / 2, nz = (b[0] - a[0]) / length * width / 2;
    positions.push(a[0] + nx, y, a[1] + nz, b[0] + nx, y, b[1] + nz, a[0] - nx, y, a[1] - nz,
      b[0] + nx, y, b[1] + nz, b[0] - nx, y, b[1] - nz, a[0] - nx, y, a[1] - nz);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  g.computeVertexNormals();
  return g;
}
function batch(geometries: THREE.BufferGeometry[], material: THREE.Material, group: THREE.Group, shadows = false): THREE.Mesh | null {
  const populated = geometries.filter(g => g.getAttribute('position')?.count > 0);
  if (!populated.length) return null;
  const normalized = populated.map(g => g.index ? g.toNonIndexed() : g);
  const merged = mergeGeometries(normalized);
  for (const g of new Set([...geometries, ...normalized])) g.dispose();
  if (!merged) return null;
  const mesh = new THREE.Mesh(merged, material);
  mesh.receiveShadow = true; mesh.castShadow = shadows; group.add(mesh);
  return mesh;
}
function insidePolygon(point: Point, polygon: readonly Point[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i]!, b = polygon[j]!;
    if ((a[1] > point[1]) !== (b[1] > point[1]) && point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}
function facadeTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas'); canvas.width = 128; canvas.height = 128;
  const c = canvas.getContext('2d');
  if (!c) throw new Error('Canvas is unavailable');
  c.fillStyle = '#e9ede7'; c.fillRect(0, 0, 128, 128);
  for (let y = 3; y < 126; y += 16) for (let x = 3; x < 126; x += 16) {
    c.fillStyle = (x + y) % 3 === 0 ? '#b7c7c5' : '#c3cecb';
    c.fillRect(x, y, 11, 12);
    c.fillStyle = '#d9e1d9'; c.fillRect(x, y, 11, 1);
  }
  c.fillStyle = '#e9ede7'; c.fillRect(0, 0, 3, 3);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

export class TorontoScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly scene = new THREE.Scene();
  readonly controls: OrbitControls;
  readonly buildings = new THREE.Group();
  readonly greenery = new THREE.Group();
  readonly paths = new THREE.Group();
  private readonly city = new THREE.Group();
  private readonly people = new THREE.Group();
  private readonly light = new THREE.DirectionalLight('#ffd9a0', 3.8);
  private readonly ambient = new THREE.HemisphereLight('#eaf3e3', '#b5a58a', 1.9);
  private readonly waterMaterial = new THREE.MeshStandardMaterial({ color: '#5f8f88', roughness: 0.36, metalness: 0.32 });
  private readonly resizeObserver: ResizeObserver;
  private readonly labels: { element: HTMLButtonElement; point: THREE.Vector3 }[] = [];
  private readonly labelContainer = document.createElement('div');
  private readonly dummy = new THREE.Object3D();
  private readonly ring: THREE.Mesh;
  private readonly route = new THREE.Group();
  private bodies: THREE.InstancedMesh | null = null;
  private heads: THREE.InstancedMesh | null = null;
  private legs: THREE.InstancedMesh | null = null;
  private crowd: Crowd;
  private selected: number | null = null;
  private following = false;
  private paused = false;
  private speed = 10;
  private seconds = 0;
  private lastTime = 0;
  private lastTick = 0;
  private flight: CameraFlight | null = null;
  private lighting: Lighting = 'golden';
  private disposed = false;
  private pointerStart = new THREE.Vector2();
  private reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor(private readonly container: HTMLDivElement, private readonly district: District,
    private readonly onTick: (tick: SceneTick) => void, private readonly onSelect: (id: number | null) => void) {
    this.crowd = createCrowd(district, 600);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.03;
    this.renderer.domElement.setAttribute('aria-label', 'Interactive 3D view of downtown Toronto. Drag to orbit, right drag to pan, scroll to zoom.');
    this.renderer.domElement.setAttribute('role', 'img');
    container.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(38, 1, 2, 20000);
    const p = presets.skyline;
    this.camera.position.set(...p.position);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(...p.target);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.075;
    this.controls.minDistance = 55; this.controls.maxDistance = 6200;
    this.controls.minPolarAngle = 0.15; this.controls.maxPolarAngle = Math.PI / 2.08;
    this.controls.maxTargetRadius = 3200;
    this.controls.addEventListener('start', this.cancelFlight);
    this.scene.background = new THREE.Color(lightRecipes.golden.sky);
    this.scene.fog = new THREE.Fog(lightRecipes.golden.sky, 4700, 11000);
    this.light.position.set(-1700, 2400, 900);
    this.light.castShadow = true; this.light.shadow.mapSize.set(2048, 2048);
    Object.assign(this.light.shadow.camera, { left: -2200, right: 2200, top: 2200, bottom: -2200, near: 100, far: 6500 });
    this.light.shadow.normalBias = 1.1; this.light.shadow.bias = -0.0002;
    this.scene.add(this.light, this.ambient, this.city, this.people, this.route);
    this.city.add(this.buildings, this.greenery, this.paths); this.paths.visible = false;
    this.buildLandscape(); this.buildArchitecture(); this.buildTrees(); this.buildLandmarks(); this.buildPeople();
    this.ring = new THREE.Mesh(new THREE.RingGeometry(7, 10, 48), new THREE.MeshBasicMaterial({ color: '#e5f5b7', side: THREE.DoubleSide }));
    this.ring.rotation.x = -Math.PI / 2; this.ring.visible = false; this.ring.renderOrder = 10; this.scene.add(this.ring);
    this.labelContainer.className = 'scene-labels'; container.appendChild(this.labelContainer);
    for (const id of ['cn', 'union', 'stlawrence', 'waterfront']) {
      const l = landmarks.find(l => l.id === id)!;
      const label = document.createElement('button');
      label.className = 'place-label label-' + id; label.textContent = l.short;
      label.setAttribute('aria-label', 'View ' + l.name);
      label.addEventListener('click', () => this.focusLandmark(id));
      this.labelContainer.appendChild(label);
      this.labels.push({ element: label, point: new THREE.Vector3(l.point[0], l.height + 28, l.point[1]) });
    }
    this.resizeObserver = new ResizeObserver(this.resize); this.resizeObserver.observe(container); this.resize();
    this.renderer.domElement.addEventListener('pointerdown', this.pointerDown);
    this.renderer.domElement.addEventListener('pointerup', this.pointerUp);
    this.renderer.domElement.addEventListener('webglcontextlost', this.contextLost);
    this.renderer.setAnimationLoop(this.animate);
  }

  private buildLandscape(): void {
    const lake = new THREE.Mesh(new THREE.PlaneGeometry(22000, 22000), this.waterMaterial);
    lake.rotation.x = -Math.PI / 2; lake.position.y = -2; lake.receiveShadow = true; this.city.add(lake);
    const baseShore = this.district.shores.slice().sort((a, b) => b.length - a.length)[0];
    let shoreline = [...(baseShore ?? [])];
    for (const s of this.district.shores) {
      if (!shoreline.length || s === baseShore) continue;
      const end = shoreline[shoreline.length - 1]!, first = s[0]!, last = s[s.length - 1]!;
      if (Math.hypot(end[0] - first[0], end[1] - first[1]) < 3) shoreline = shoreline.concat(s.slice(1));
      else if (Math.hypot(end[0] - last[0], end[1] - last[1]) < 3) shoreline = shoreline.concat(s.slice(0, -1).reverse());
    }
    if (shoreline.length < 2) shoreline = [[-4000, 1900], [4000, 900]];
    if (shoreline[0]![0] > shoreline[shoreline.length - 1]![0]) shoreline.reverse();
    const west = shoreline[0]!, east = shoreline[shoreline.length - 1]!;
    const land = [[-6500, -7000], [6500, -7000], [6500, east[1]], ...shoreline.slice().reverse(), [-6500, west[1]]] satisfies Point[];
    const ground = new THREE.Mesh(flat(land, 0), new THREE.MeshStandardMaterial({ color: '#bcc3ac', roughness: 1 }));
    ground.receiveShadow = true; this.city.add(ground);
    batch([ribbon(shoreline, 6, 1.8)], new THREE.MeshStandardMaterial({ color: '#e4ddc4', roughness: 0.9 }), this.city);
    batch(this.district.parks.map(a => flat(a.polygon, 0.8)), new THREE.MeshStandardMaterial({ color: '#92aa7b', roughness: 1 }), this.greenery);
    batch(this.district.water.map(a => flat(a.polygon, 1)), this.waterMaterial, this.city);
    const sidewalks: THREE.BufferGeometry[] = [], streets: THREE.BufferGeometry[] = [], footpaths: THREE.BufferGeometry[] = [], markings: THREE.BufferGeometry[] = [];
    for (const road of this.district.roads) {
      const isPath = pathKinds.has(road.kind);
      if (isPath) { footpaths.push(ribbon(road.points, road.width, 1.5)); continue; }
      sidewalks.push(ribbon(road.points, road.width + 6, 1.05));
      streets.push(ribbon(road.points, road.width, 1.3));
      if (road.width < 10) continue;
      for (let i = 0; i < road.points.length - 1; i++) {
        const a = road.points[i]!, b = road.points[i + 1]!, d = Math.hypot(b[0] - a[0], b[1] - a[1]);
        const dx = (b[0] - a[0]) / d, dz = (b[1] - a[1]) / d;
        for (let m = 7; m < Math.min(d - 5, 500); m += 18) {
          markings.push(ribbon([[a[0] + dx * m, a[1] + dz * m], [a[0] + dx * (m + 7), a[1] + dz * (m + 7)]], 0.45, 1.55));
        }
      }
    }
    batch(sidewalks, new THREE.MeshStandardMaterial({ color: '#d3d0b9', roughness: 0.95 }), this.city);
    batch(streets, new THREE.MeshStandardMaterial({ color: '#6f7e78', roughness: 0.95 }), this.city);
    batch(footpaths, new THREE.MeshStandardMaterial({ color: '#c6c5ab', roughness: 0.95 }), this.city);
    batch(markings, new THREE.MeshBasicMaterial({ color: '#c3c5ac' }), this.city);
    batch(this.district.rails.map(p => ribbon(p, 1.5, 2.2)), new THREE.MeshStandardMaterial({ color: '#87908a', metalness: 0.4, roughness: 0.7 }), this.city);
    const points: number[] = [];
    for (const [a, b, kind] of this.district.walkEdges) {
      if (kind === 'crossing') continue;
      const p = this.district.walkNodes[a]!, q = this.district.walkNodes[b]!;
      points.push(p[0], 3, p[1], q[0], 3, q[1]);
    }
    const pathGeometry = new THREE.BufferGeometry(); pathGeometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    this.paths.add(new THREE.LineSegments(pathGeometry, new THREE.LineBasicMaterial({ color: '#c3f2be', transparent: true, opacity: 0.65 })));
    // Small, deterministic glints give the harbour texture without an external image.
    const glints: number[] = [];
    for (let i = 0; i < 500; i++) {
      const x = Math.sin(i * 37.7) * 3800, z = 2500 + ((i * 199) % 3800);
      glints.push(x, -1.8, z, x + 5 + i % 15, -1.8, z);
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(glints, 3));
    this.city.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: '#b4d1bd', transparent: true, opacity: 0.18 })));
  }

  private buildArchitecture(): void {
    const texture = facadeTexture();
    const material = new THREE.MeshStandardMaterial({ map: texture, vertexColors: true, roughness: 0.7, metalness: 0.12 });
    const geometries: THREE.BufferGeometry[] = [], edges: number[] = [];
    const cn = landmarks[0]!.point, rogers = landmarks[1]!.point;
    for (const building of this.district.buildings) {
      const poly = building.polygon;
      const centre = poly.reduce((p, q) => [p[0] + q[0] / poly.length, p[1] + q[1] / poly.length], [0, 0]);
      if (Math.hypot(centre[0]! - cn[0], centre[1]! - cn[1]) < 37 ||
        (Math.abs(centre[0]! - rogers[0]) < 135 && Math.abs(centre[1]! - rogers[1]) < 115)) continue;
      const top = Math.max(building.base + 3, building.height);
      const geometry = new THREE.ExtrudeGeometry(shape(poly), { depth: top - building.base, bevelEnabled: false, steps: 1, curveSegments: 1 });
      geometry.rotateX(-Math.PI / 2); geometry.translate(0, building.base + 1, 0);
      const position = geometry.getAttribute('position'), normals = geometry.getAttribute('normal');
      const uvs = geometry.getAttribute('uv');
      const color = new THREE.Color(palette[parseInt(building.id.slice(4), 10) % palette.length]!);
      if (top < 23) color.lerp(new THREE.Color('#d3c5ad'), 0.5);
      if (top < 35 && centre[0]! > 600 && centre[1]! < 600) color.lerp(new THREE.Color('#b8967d'), 0.4);
      if (top > 110) color.lerp(new THREE.Color('#99b6b3'), 0.45);
      const roof = color.clone().lerp(new THREE.Color('#f1ecda'), 0.34), colors: number[] = [];
      for (let i = 0; i < position.count; i++) {
        const isRoof = Math.abs(normals.getY(i)) > 0.7;
        const c = isRoof ? roof : color;
        colors.push(c.r, c.g, c.b);
        if (isRoof || top < 18) uvs.setXY(i, 0.005, 0.005);
        else uvs.setXY(i, (Math.abs(normals.getX(i)) > 0.5 ? position.getZ(i) : position.getX(i)) / 32, position.getY(i) / 32);
      }
      geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
      geometry.clearGroups(); geometries.push(geometry);
      if (top > 25) for (let i = 0; i < poly.length - 1; i++) {
        const a = poly[i]!, b = poly[i + 1]!;
        edges.push(a[0], top + 1.2, a[1], b[0], top + 1.2, b[1]);
      }
    }
    batch(geometries, material, this.buildings, true);
    const edgeGeometry = new THREE.BufferGeometry(); edgeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(edges, 3));
    this.buildings.add(new THREE.LineSegments(edgeGeometry, new THREE.LineBasicMaterial({ color: '#657d77', transparent: true, opacity: 0.17 })));
  }

  private buildTrees(): void {
    const locations: { point: Point; size: number }[] = [];
    const allRoadClearance = buildRoadClearanceIndex(this.district.roads);
    const streetClearance = buildRoadClearanceIndex(this.district.roads.filter(road => !pathKinds.has(road.kind)));
    const treeIsClear = (point: Point, size: number) =>
      isCircleClearOfRoads(point, TREE_CANOPY_RADIUS * size, streetClearance) &&
      isCircleClearOfRoads(point, TREE_TRUNK_RADIUS * size, allRoadClearance);
    let seed = 42;
    const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
    for (const park of this.district.parks) {
      const xs = park.polygon.map(p => p[0]), zs = park.polygon.map(p => p[1]);
      const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
      const attempts = Math.min(40, Math.floor((maxX - minX) * (maxZ - minZ) / 500));
      for (let i = 0; i < attempts; i++) {
        const point: Point = [minX + rand() * (maxX - minX), minZ + rand() * (maxZ - minZ)];
        const size = 0.75 + rand() * 0.7;
        if (insidePolygon(point, park.polygon) && treeIsClear(point, size)) {
          locations.push({ point, size });
        }
      }
    }
    for (const road of this.district.roads) {
      if (!['primary', 'secondary', 'tertiary', 'residential'].includes(road.kind)) continue;
      for (let i = 0; i < road.points.length - 1; i++) {
        const a = road.points[i]!, b = road.points[i + 1]!, d = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (d < 0.05) continue;
        const dx = (b[0] - a[0]) / d, dz = (b[1] - a[1]) / d;
        for (let m = 18; m < Math.min(d, 300); m += 43) {
          const side = rand() < 0.5 ? -1 : 1, size = 0.7 + rand() * 0.4, off = (road.width / 2 + 4.4) * side;
          const p: Point = [a[0] + dx * m - dz * off, a[1] + dz * m + dx * off];
          if (Math.abs(p[0]) < 1700 && p[1] > -1700 && p[1] < 1500 &&
            treeIsClear(p, size)) locations.push({ point: p, size });
        }
      }
    }
    const positions = locations.slice(0, 4500);
    const crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(TREE_CANOPY_RADIUS, 1), new THREE.MeshStandardMaterial({ color: '#72956b', roughness: 1, flatShading: true }), positions.length);
    const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.9, 1.2, 7, 5), new THREE.MeshStandardMaterial({ color: '#8e8a6c', roughness: 1 }), positions.length);
    positions.forEach(({ point, size }, i) => {
      this.dummy.position.set(point[0], 10 * size, point[1]); this.dummy.rotation.set(0, rand() * 6, 0); this.dummy.scale.set(size, size * 1.1, size); this.dummy.updateMatrix();
      crowns.setMatrixAt(i, this.dummy.matrix); crowns.setColorAt(i, new THREE.Color().setHSL(0.21 + rand() * 0.06, 0.17 + rand() * 0.12, 0.36 + rand() * 0.15));
      this.dummy.position.y = 4 * size; this.dummy.updateMatrix(); trunks.setMatrixAt(i, this.dummy.matrix);
    });
    crowns.castShadow = true; crowns.receiveShadow = true; trunks.castShadow = true;
    this.greenery.add(crowns, trunks);
  }

  private buildLandmarks(): void {
    const concrete = new THREE.MeshStandardMaterial({ color: '#e5ddc6', roughness: 0.72 });
    const glass = new THREE.MeshStandardMaterial({ color: '#527d7e', metalness: 0.45, roughness: 0.3 });
    const roof = new THREE.MeshStandardMaterial({ color: '#f0ecda', metalness: 0.12, roughness: 0.5 });
    const cn = new THREE.Group(); cn.position.set(landmarks[0]!.point[0], 1, landmarks[0]!.point[1]); this.buildings.add(cn);
    const add = (g: THREE.BufferGeometry, m: THREE.Material, y: number, parent = cn) => {
      const mesh = new THREE.Mesh(g, m); mesh.position.y = y; mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
    };
    add(new THREE.CylinderGeometry(5.5, 16, 344, 3), concrete, 172).rotation.y = Math.PI / 3;
    add(new THREE.CylinderGeometry(29, 11, 24, 48), concrete, 337);
    add(new THREE.CylinderGeometry(32, 32, 9, 48), glass, 353);
    add(new THREE.CylinderGeometry(35, 32, 4, 48), roof, 359.5);
    add(new THREE.CylinderGeometry(8, 34, 12, 48), roof, 367);
    add(new THREE.CylinderGeometry(2.8, 4.5, 82, 12), concrete, 408);
    add(new THREE.CylinderGeometry(8.2, 7.2, 8, 32), glass, 447);
    add(new THREE.CylinderGeometry(3, 8, 8, 32), roof, 453);
    add(new THREE.CylinderGeometry(1.1, 2.8, 96, 12), concrete, 505);
    add(new THREE.CylinderGeometry(0.6, 0.8, 10, 8), new THREE.MeshBasicMaterial({ color: '#c68e6e' }), 553);
    const stadium = new THREE.Group(); const r = landmarks[1]!.point;
    stadium.position.set(r[0], 1, r[1]); stadium.rotation.y = -0.25; this.buildings.add(stadium);
    const base = add(new THREE.CylinderGeometry(118, 120, 27, 64), concrete, 14, stadium); base.scale.z = 0.84;
    const dome = add(new THREE.SphereGeometry(1, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2), roof, 27, stadium);
    dome.scale.set(116, 42, 99);
    for (const offset of [-0.46, 0, 0.46]) {
      const points: THREE.Vector3[] = [];
      for (let i = 0; i <= 32; i++) {
        const angle = i / 32 * Math.PI, section = Math.sqrt(1 - offset * offset);
        points.push(new THREE.Vector3(offset * 116, 27 + Math.sin(angle) * 42 * section, Math.cos(angle) * 99 * section));
      }
      stadium.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 32, 0.65, 4, false), concrete));
    }
    const waterName = document.createElement('div');
    waterName.className = 'lake-name'; waterName.textContent = 'L A K E  O N T A R I O'; this.container.appendChild(waterName);
  }

  private buildPeople(): void {
    for (const child of [...this.people.children]) {
      if (child instanceof THREE.Mesh) { child.geometry.dispose(); if (child.material instanceof THREE.Material) child.material.dispose(); }
      this.people.remove(child);
    }
    const count = this.crowd.residents.length;
    this.bodies = new THREE.InstancedMesh(new THREE.CapsuleGeometry(1.3, 2.4, 3, 5), new THREE.MeshStandardMaterial({ roughness: 0.85 }), count);
    this.heads = new THREE.InstancedMesh(new THREE.SphereGeometry(1.25, 7, 5), new THREE.MeshStandardMaterial({ color: '#eed2ae', roughness: 1 }), count);
    this.legs = new THREE.InstancedMesh(new THREE.BoxGeometry(0.9, 2.7, 1), new THREE.MeshStandardMaterial({ color: '#465f5a', roughness: 1 }), count * 2);
    for (const resident of this.crowd.residents) this.bodies.setColorAt(resident.id, new THREE.Color(resident.color));
    this.bodies.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.heads.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.legs.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.bodies.frustumCulled = false; this.heads.frustumCulled = false; this.legs.frustumCulled = false;
    this.people.add(this.bodies, this.heads, this.legs);
  }

  private resize = (): void => {
    const w = this.container.clientWidth, h = this.container.clientHeight;
    this.camera.fov = w < 800 ? 52 : 38;
    this.camera.aspect = w / Math.max(1, h); this.camera.updateProjectionMatrix(); this.renderer.setSize(w, h);
  };
  private cancelFlight = (): void => { this.flight = null; this.following = false; };
  private pointerDown = (event: PointerEvent): void => { this.pointerStart.set(event.clientX, event.clientY); };
  private pointerUp = (event: PointerEvent): void => {
    if (this.pointerStart.distanceTo(new THREE.Vector2(event.clientX, event.clientY)) > 5 || event.button !== 0) return;
    const rect = this.renderer.domElement.getBoundingClientRect(), point = new THREE.Vector3();
    const normalized = new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    const raycaster = new THREE.Raycaster(); raycaster.setFromCamera(normalized, this.camera);
    const obstruction = raycaster.intersectObjects(this.buildings.children, true)[0]?.distance ?? Infinity;
    let picked: number | null = null, nearest = 18;
    for (const resident of this.crowd.residents) {
      const p = sampleResident(resident, this.seconds);
      if (this.camera.position.distanceTo(new THREE.Vector3(p.x, 8, p.z)) > obstruction + 8) continue;
      point.set(p.x, 8, p.z).project(this.camera);
      if (point.z > 1) continue;
      const distance = Math.hypot((point.x + 1) / 2 * rect.width - event.clientX + rect.left, (1 - point.y) / 2 * rect.height - event.clientY + rect.top);
      if (distance < nearest) { nearest = distance; picked = resident.id; }
    }
    this.select(picked);
  };
  private contextLost = (event: Event): void => {
    event.preventDefault(); this.setPaused(true);
    this.container.dispatchEvent(new CustomEvent('scene-error', { detail: 'The 3D graphics connection was lost. Reload to restore the environment.' }));
  };
  private animate = (now: number): void => {
    if (this.disposed) return;
    const delta = this.lastTime ? Math.min((now - this.lastTime) / 1000, 0.1) : 0; this.lastTime = now;
    if (!this.paused && !document.hidden) this.seconds += delta * this.speed;
    let walking = 0;
    this.dummy.scale.setScalar(1);
    for (const resident of this.crowd.residents) {
      const p = sampleResident(resident, this.seconds);
      if (p.walking) walking++;
      const gait = p.walking ? Math.sin(this.seconds * resident.speed * 3.8 + resident.id) : 0;
      this.dummy.rotation.set(0, p.heading, 0);
      this.dummy.position.set(p.x, 5.2 + Math.abs(gait) * 0.2, p.z); this.dummy.updateMatrix(); this.bodies?.setMatrixAt(resident.id, this.dummy.matrix);
      this.dummy.position.y = 8.8; this.dummy.updateMatrix(); this.heads?.setMatrixAt(resident.id, this.dummy.matrix);
      for (let side = 0; side < 2; side++) {
        const off = side === 0 ? -0.75 : 0.75, swing = gait * (side === 0 ? -1 : 1);
        this.dummy.position.set(p.x + Math.cos(p.heading) * off + Math.sin(p.heading) * swing, 2.8, p.z - Math.sin(p.heading) * off + Math.cos(p.heading) * swing);
        this.dummy.rotation.set(swing * 0.4, p.heading, 0); this.dummy.updateMatrix(); this.legs?.setMatrixAt(resident.id * 2 + side, this.dummy.matrix);
      }
      if (this.selected === resident.id) {
        this.ring.position.set(p.x, 2, p.z); this.ring.scale.setScalar(1 + Math.sin(now / 600) * 0.08);
        if (this.following && !this.flight) {
          const difference = new THREE.Vector3(p.x, 8, p.z).sub(this.controls.target);
          this.camera.position.addScaledVector(difference, 0.05); this.controls.target.addScaledVector(difference, 0.05);
        }
      }
    }
    if (this.bodies) this.bodies.instanceMatrix.needsUpdate = true;
    if (this.heads) this.heads.instanceMatrix.needsUpdate = true;
    if (this.legs) this.legs.instanceMatrix.needsUpdate = true;
    if (this.flight) {
      const t = Math.min(1, (now - this.flight.start) / (this.reducedMotion ? 1 : 1600)), eased = t * t * (3 - 2 * t);
      this.camera.position.lerpVectors(this.flight.from, this.flight.to, eased); this.controls.target.lerpVectors(this.flight.targetFrom, this.flight.targetTo, eased);
      if (t === 1) this.flight = null;
    }
    this.controls.update();
    for (const label of this.labels) {
      const p = label.point.clone().project(this.camera);
      label.element.style.transform = 'translate(-50%, -100%) translate(' + ((p.x + 1) / 2 * this.container.clientWidth) + 'px, ' + ((1 - p.y) / 2 * this.container.clientHeight) + 'px)';
      label.element.style.visibility = p.z > 1 || p.x < -0.95 || p.x > 0.95 || p.y < -0.95 || p.y > 0.95 ? 'hidden' : 'visible';
    }
    const recipe = lightRecipes[this.lighting];
    const color = new THREE.Color(recipe.sky);
    if (this.scene.background instanceof THREE.Color) this.scene.background.lerp(color, 0.035);
    if (this.scene.fog instanceof THREE.Fog) this.scene.fog.color.lerp(color, 0.035);
    this.waterMaterial.color.lerp(new THREE.Color(recipe.water), 0.035);
    this.light.color.lerp(new THREE.Color(recipe.sun), 0.035);
    this.light.intensity = THREE.MathUtils.lerp(this.light.intensity, recipe.sunPower, 0.035);
    this.ambient.intensity = THREE.MathUtils.lerp(this.ambient.intensity, recipe.ambient, 0.035);
    this.renderer.toneMappingExposure = THREE.MathUtils.lerp(this.renderer.toneMappingExposure, recipe.exposure, 0.035);
    this.renderer.render(this.scene, this.camera);
    if (now - this.lastTick > 350) {
      const resident = this.selected === null ? undefined : this.crowd.residents[this.selected];
      this.onTick({ seconds: this.seconds, walking, resting: this.crowd.residents.length - walking,
        selected: resident ? inspectResident(resident, this.seconds) : null }); this.lastTick = now;
    }
  };

  setPaused(paused: boolean): void { this.paused = paused; }
  setSpeed(speed: number): void { this.speed = speed; }
  setLighting(value: Lighting): void { this.lighting = value; }
  setLayer(layer: Layer, visible: boolean): void {
    if (layer === 'labels') this.labelContainer.style.display = visible ? '' : 'none';
    else this[layer === 'greenery' ? 'greenery' : layer].visible = visible;
  }
  setPopulation(count: number): void {
    this.crowd = createCrowd(this.district, count); this.select(null); this.buildPeople();
  }
  reset(): void { this.seconds = 0; this.lastTick = 0; this.select(null); }
  seek(seconds: number): void { this.seconds = seconds; this.lastTick = 0; }
  setPreset(preset: Preset): void {
    const p = presets[preset]; this.following = false;
    this.fly(new THREE.Vector3(...p.position), new THREE.Vector3(...p.target));
  }
  focusLandmark(id: string): void {
    const landmark = landmarks.find(l => l.id === id);
    if (!landmark) return;
    const [x, z] = landmark.point; const distance = id === 'cn' ? 850 : 540;
    this.following = false; this.fly(new THREE.Vector3(x + distance * 0.7, distance * 0.65, z + distance), new THREE.Vector3(x, landmark.height * 0.3, z));
  }
  zoom(direction: number): void {
    const offset = this.camera.position.clone().sub(this.controls.target).multiplyScalar(direction > 0 ? 0.75 : 1.3);
    offset.clampLength(55, 6200); this.fly(this.controls.target.clone().add(offset), this.controls.target.clone());
  }
  select(id: number | null): void {
    this.selected = id; this.ring.visible = id !== null; this.following = false; this.onSelect(id);
    for (const child of [...this.route.children]) {
      if (child instanceof THREE.Mesh) { child.geometry.dispose(); if (child.material instanceof THREE.Material) child.material.dispose(); }
      this.route.remove(child);
    }
    const resident = id === null ? undefined : this.crowd.residents[id];
    if (resident) batch([ribbon(resident.route, 3, 2.8)], new THREE.MeshBasicMaterial({ color: '#d6f3a3', transparent: true, opacity: 0.9 }), this.route);
    this.lastTick = 0;
  }
  meetResident(): void {
    const union = landmarks.find(l => l.id === 'waterfront')!.point;
    let best = 0, nearest = Infinity;
    for (const resident of this.crowd.residents) {
      const p = sampleResident(resident, this.seconds), d = Math.hypot(p.x - union[0], p.z - union[1]);
      if (d < nearest && p.walking) { nearest = d; best = resident.id; }
    }
    this.select(best); this.followSelected();
  }
  followSelected(): void {
    const resident = this.selected === null ? undefined : this.crowd.residents[this.selected];
    if (!resident) return;
    const p = sampleResident(resident, this.seconds);
    this.fly(new THREE.Vector3(p.x + 130, 190, p.z + 190), new THREE.Vector3(p.x, 8, p.z));
    this.following = true;
  }
  private fly(position: THREE.Vector3, target: THREE.Vector3): void {
    this.flight = { from: this.camera.position.clone(), to: position, targetFrom: this.controls.target.clone(), targetTo: target, start: performance.now() };
  }
  dispose(): void {
    this.disposed = true; this.renderer.setAnimationLoop(null);
    this.resizeObserver.disconnect(); this.controls.dispose();
    this.renderer.domElement.removeEventListener('pointerdown', this.pointerDown);
    this.renderer.domElement.removeEventListener('pointerup', this.pointerUp);
    this.renderer.domElement.removeEventListener('webglcontextlost', this.contextLost);
    const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
    this.scene.traverse(object => {
      if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
        geometries.add(object.geometry);
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
          materials.add(material);
          if (material instanceof THREE.MeshStandardMaterial && material.map) textures.add(material.map);
        }
      }
    });
    geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose());
    this.renderer.dispose(); this.container.replaceChildren();
  }
}
