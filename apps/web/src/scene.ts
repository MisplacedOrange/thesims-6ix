import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { landmarks } from './district.ts';
import type { District, Islands, Point } from './district.ts';
import type { Crowd, Inspection, Resident } from './pedestrians.ts';
import { firstPedestrianDeparture, foodCrowd, foodInspection, foodPose } from './interactables.ts';
import type { FoodTrace } from './interactables.ts';
import { buildRoadClearanceIndex, isCircleClearOfRoads, TREE_CANOPY_RADIUS, TREE_TRUNK_RADIUS } from './treePlacement.ts';
import { buildingGeometry, facadeMaterial, fillerMesh } from './facade.ts';
import type { FacadeUniforms } from './facade.ts';
import { buildSurroundings, CAMERA_LIMIT, clampToBox, CORE, donValleyX, FILL_LIMIT, insidePolygon, joinShoreline, landPolygon,
  MAX_DISTANCE, outsideCore, resolveBuildingParts, streetGridAngle, TARGET_LIMIT } from './world.ts';
import { GroundBuilder, groundLayer } from './ground.ts';
import { noiseTexture, sleeperTexture, waterNormalTexture } from './textures.ts';
import { Sky } from './atmosphere.ts';
import type { RunRef } from './runRef.ts';
import { RolloutSiteLayer } from './RolloutSiteLayer.ts';

export type Lighting = 'day' | 'golden' | 'blue';
export type Layer = 'buildings' | 'greenery' | 'paths' | 'traffic';
export type SceneTick = { seconds: number; walking: number; resting: number; selected: Inspection | null };
type CameraFlight = { from: THREE.Vector3; to: THREE.Vector3; targetFrom: THREE.Vector3; targetTo: THREE.Vector3; start: number };
type TrafficPath = { points: Point[]; cumulative: number[]; length: number; width: number };
type TrafficVehicle = { path: TrafficPath; offset: number; speed: number; lane: number; scale: number; color: string };
type TrafficRoadEdge = { length: number; width: number };
type TrafficNeighbor = { edge: TrafficRoadEdge; next: number };
type TrafficNetwork = { points: Point[]; adjacency: TrafficNeighbor[][] };
const initialCamera = { position: new THREE.Vector3(1900, 1720, 2850), target: new THREE.Vector3(-100, 100, 340) };
const pathKinds = new Set(['footway', 'path', 'pedestrian', 'steps', 'cycleway']);
const vehicleRoadKinds = new Set(['motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
  'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'unclassified', 'residential', 'living_street', 'road', 'service']);
const vehicleColors = ['#e2dfd2', '#748b91', '#b8775c', '#d2ad61', '#405965', '#87927e', '#c9c8bd', '#596e61'];
type Recipe = { top: string; horizon: string; sun: string; sunPower: number; ambient: number; exposure: number; water: string; azimuth: number; elevation: number };
const lightRecipes: Record<Lighting, Recipe> = {
  day: { top: '#5b8fcc', horizon: '#c9d7e0', sun: '#fff3df', sunPower: 3.1, ambient: 0.7, exposure: 0.95, water: '#2c5a68', azimuth: -0.55, elevation: 0.95 },
  golden: { top: '#6683ad', horizon: '#d8c6b0', sun: '#ffc685', sunPower: 3.4, ambient: 0.55, exposure: 0.95, water: '#2a4c58', azimuth: -1.75, elevation: 0.3 },
  blue: { top: '#13213a', horizon: '#4b5b78', sun: '#a9bde6', sunPower: 0.5, ambient: 0.8, exposure: 1.1, water: '#122233', azimuth: -2.0, elevation: 0.1 },
};
const WATER_Y = -1.6;
const PEDESTRIAN_SCALE = 0.75;
const PEDESTRIAN_GROUND_Y = 0.3;
const PEDESTRIAN_ORIGINAL_FOOT_Y = 1.45;
function pedestrianY(originalY: number): number {
  return PEDESTRIAN_GROUND_Y + (originalY - PEDESTRIAN_ORIGINAL_FOOT_Y) * PEDESTRIAN_SCALE;
}

/** Colours the base land: lot paving inside the mapped core, streets between procedural blocks outside it. */
function groundMaterial(map: THREE.Texture): THREE.MeshStandardMaterial {
  const material = new THREE.MeshStandardMaterial({ map, roughness: 1, envMapIntensity: 0.45 });
  material.onBeforeCompile = shader => {
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vGroundXZ;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvGroundXZ = (modelMatrix * vec4(transformed, 1.0)).xz;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>
        varying vec2 vGroundXZ;
        const vec4 groundCore = vec4(${CORE.minX.toFixed(1)}, ${CORE.minZ.toFixed(1)}, ${CORE.maxX.toFixed(1)}, ${CORE.maxZ.toFixed(1)});`)
      .replace('#include <map_fragment>', `
        vec2 groundOut = max(groundCore.xy - vGroundXZ, vGroundXZ - groundCore.zw);
        float groundStreet = smoothstep(80.0, 160.0, max(groundOut.x, groundOut.y));
        diffuseColor.rgb = mix(vec3(0.36, 0.33, 0.28), vec3(0.12, 0.115, 0.11), groundStreet);
        #include <map_fragment>`);
  };
  return material;
}
/** Splits a polyline into the runs that stay over the mapped core, so roads stop where the procedural blocks begin. */
function clipToCore(points: readonly Point[], margin = 30): Point[][] {
  const runs: Point[][] = [];
  let run: Point[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]!, b = points[i + 1]!;
    if (Math.min(outsideCore(a[0], a[1]), outsideCore(b[0], b[1])) <= margin) { if (!run.length) run.push(a); run.push(b); }
    else if (run.length) { runs.push(run); run = []; }
  }
  if (run.length) runs.push(run);
  return runs;
}
function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b[0] - a[0], dz = b[1] - a[1], l = dx * dx + dz * dz || 1;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / l));
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dz);
}
function trafficRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let value = Math.imul(state ^ state >>> 15, 1 | state);
    value ^= value + Math.imul(value ^ value >>> 7, 61 | value);
    return ((value ^ value >>> 14) >>> 0) / 4294967296;
  };
}
function trafficNetwork(district: District): TrafficNetwork {
  const points: Point[] = [];
  const adjacency: TrafficNeighbor[][] = [];
  const nodeIds = new Map<string, number>();
  const edgeKeys = new Set<string>();
  const nodeId = (point: Point): number => {
    const key = `${Math.round(point[0] * 10)}:${Math.round(point[1] * 10)}`;
    const existing = nodeIds.get(key);
    if (existing !== undefined) return existing;
    const id = points.length;
    nodeIds.set(key, id); points.push(point); adjacency.push([]);
    return id;
  };
  for (const road of district.roads) {
    if (!vehicleRoadKinds.has(road.kind) || pathKinds.has(road.kind) || road.width < 8) continue;
    for (const roadPoints of clipToCore(road.points)) {
      for (let i = 1; i < roadPoints.length; i++) {
        const previous = roadPoints[i - 1]!, current = roadPoints[i]!;
        const length = Math.hypot(current[0] - previous[0], current[1] - previous[1]);
        if (length < 0.5) continue;
        const a = nodeId(previous), b = nodeId(current);
        if (a === b) continue;
        const key = `${Math.min(a, b)}:${Math.max(a, b)}`;
        if (edgeKeys.has(key)) continue;
        edgeKeys.add(key);
        const edge = { length, width: road.width };
        adjacency[a]?.push({ edge, next: b }); adjacency[b]?.push({ edge, next: a });
      }
    }
  }
  return { points, adjacency };
}
function smoothTrafficRoute(points: Point[]): Point[] {
  if (points.length < 3) return points;
  const smooth: Point[] = [points[0]!];
  for (let i = 1; i < points.length - 1; i++) {
    const previous = points[i - 1]!, corner = points[i]!, next = points[i + 1]!;
    const incomingLength = Math.hypot(corner[0] - previous[0], corner[1] - previous[1]);
    const outgoingLength = Math.hypot(next[0] - corner[0], next[1] - corner[1]);
    if (incomingLength < 0.5 || outgoingLength < 0.5) { smooth.push(corner); continue; }
    const incoming: Point = [(corner[0] - previous[0]) / incomingLength, (corner[1] - previous[1]) / incomingLength];
    const outgoing: Point = [(next[0] - corner[0]) / outgoingLength, (next[1] - corner[1]) / outgoingLength];
    const turn = Math.acos(Math.max(-1, Math.min(1, incoming[0] * outgoing[0] + incoming[1] * outgoing[1])));
    const radius = Math.min(4, incomingLength * 0.35, outgoingLength * 0.35);
    if (turn < 0.28 || turn > 2.75 || radius < 1) { smooth.push(corner); continue; }
    const before: Point = [corner[0] - incoming[0] * radius, corner[1] - incoming[1] * radius];
    const after: Point = [corner[0] + outgoing[0] * radius, corner[1] + outgoing[1] * radius];
    smooth.push(before);
    for (let step = 1; step <= 4; step++) {
      const t = step / 4, inverse = 1 - t;
      smooth.push([
        inverse * inverse * before[0] + 2 * inverse * t * corner[0] + t * t * after[0],
        inverse * inverse * before[1] + 2 * inverse * t * corner[1] + t * t * after[1],
      ]);
    }
  }
  smooth.push(points[points.length - 1]!);
  return smooth;
}
function shortestTrafficRoute(network: TrafficNetwork, start: number, destination: number): number[] {
  const previous = new Int32Array(network.points.length).fill(-1);
  const queue = [start];
  previous[start] = start;
  for (let head = 0; head < queue.length && previous[destination] === -1; head++) {
    const current = queue[head]!;
    for (const neighbor of network.adjacency[current] ?? []) {
      if (previous[neighbor.next] !== -1) continue;
      previous[neighbor.next] = current;
      queue.push(neighbor.next);
      if (neighbor.next === destination) break;
    }
  }
  if (previous[destination] === -1) return [];
  const route = [destination];
  while (route[route.length - 1] !== start) route.push(previous[route[route.length - 1]!]!);
  return route.reverse();
}
function rotateTrafficLoop(points: Point[]): Point[] {
  if (points.length < 4) return points;
  const loop = points.slice(0, -1);
  let start = 0, bestStraightness = -Infinity;
  for (let i = 0; i < loop.length; i++) {
    const previous = loop[(i + loop.length - 1) % loop.length]!, current = loop[i]!, next = loop[(i + 1) % loop.length]!;
    const beforeLength = Math.hypot(current[0] - previous[0], current[1] - previous[1]) || 1;
    const afterLength = Math.hypot(next[0] - current[0], next[1] - current[1]) || 1;
    const straightness = ((current[0] - previous[0]) * (next[0] - current[0]) +
      (current[1] - previous[1]) * (next[1] - current[1])) / (beforeLength * afterLength);
    if (straightness > bestStraightness) { bestStraightness = straightness; start = i; }
  }
  const rotated = [...loop.slice(start), ...loop.slice(0, start)];
  rotated.push(rotated[0]!);
  return rotated;
}
function buildTrafficPath(network: TrafficNetwork, start: number, random: () => number): TrafficPath | null {
  let current = start, previousNode = -1, width = Infinity, length = 0;
  const lastVisitedDistance = new Map<number, number>([[start, 0]]);
  const route: Point[] = [network.points[start]!];
  const targetLength = 45000 + random() * 15000;
  for (let step = 0; step < 7000 && length < targetLength; step++) {
    const neighbors = network.adjacency[current] ?? [];
    const forward = neighbors.filter(neighbor => neighbor.next !== previousNode);
    const fresh = forward.filter(neighbor => length - (lastVisitedDistance.get(neighbor.next) ?? -Infinity) >= 2500);
    const continuing = fresh.filter(neighbor => (network.adjacency[neighbor.next] ?? []).some(next =>
      next.next !== current && length + neighbor.edge.length - (lastVisitedDistance.get(next.next) ?? -Infinity) >= 2500));
    const choices = continuing.length ? continuing : fresh.length ? fresh : forward.length ? forward : neighbors;
    if (!choices.length) break;
    const here = network.points[current]!;
    const previous = previousNode < 0 ? null : network.points[previousNode]!;
    const weighted = choices.map(neighbor => {
      let weight = neighbor.edge.length;
      if (previous) {
        const before = Math.hypot(here[0] - previous[0], here[1] - previous[1]) || 1;
        const next = network.points[neighbor.next]!;
        const after = Math.hypot(next[0] - here[0], next[1] - here[1]) || 1;
        const straightness = ((here[0] - previous[0]) * (next[0] - here[0]) +
          (here[1] - previous[1]) * (next[1] - here[1])) / (before * after);
        weight *= straightness > 0.8 ? 1.8 : straightness < -0.4 ? 0.45 : 1;
      }
      return { neighbor, weight };
    });
    let selection = random() * weighted.reduce((sum, choice) => sum + choice.weight, 0);
    let chosen = weighted[weighted.length - 1]!.neighbor;
    for (const choice of weighted) {
      selection -= choice.weight;
      if (selection <= 0) { chosen = choice.neighbor; break; }
    }
    route.push(network.points[chosen.next]!);
    previousNode = current; current = chosen.next;
    width = Math.min(width, chosen.edge.width); length += chosen.edge.length; lastVisitedDistance.set(current, length);
  }
  if (route.length < 2) return null;
  const returnRoute = shortestTrafficRoute(network, current, start);
  if (returnRoute.length < 2) return null;
  let closureNode = current;
  for (const next of returnRoute.slice(1)) {
    const edge = (network.adjacency[closureNode] ?? []).find(neighbor => neighbor.next === next)?.edge;
    if (edge) width = Math.min(width, edge.width);
    route.push(network.points[next]!);
    closureNode = next;
  }
  const smoothed = smoothTrafficRoute(rotateTrafficLoop(route));
  const cumulative = [0];
  for (let i = 1; i < smoothed.length; i++) {
    const previous = smoothed[i - 1]!, next = smoothed[i]!;
    cumulative.push(cumulative[i - 1]! + Math.hypot(next[0] - previous[0], next[1] - previous[1]));
  }
  const routeLength = cumulative[cumulative.length - 1]!;
  return routeLength > 0 ? { points: smoothed, cumulative, length: routeLength, width } : null;
}
function trafficPaths(district: District, count: number, random: () => number): TrafficPath[] {
  const network = trafficNetwork(district);
  const starts = network.adjacency.flatMap((edges, id) => edges.length > 0 ? [id] : []);
  if (!starts.length) return [];
  const paths: TrafficPath[] = [];
  for (let vehicle = 0; vehicle < count; vehicle++) {
    let best: TrafficPath | null = null;
    for (let attempt = 0; attempt < 4 && (!best || best.length < 45000); attempt++) {
      const start = starts[Math.floor(random() * starts.length)]!;
      const candidate = buildTrafficPath(network, start, random);
      if (candidate && (!best || candidate.length > best.length)) best = candidate;
    }
    if (best) paths.push(best);
  }
  return paths;
}
function sampleTraffic(vehicle: TrafficVehicle, seconds: number): { x: number; z: number; heading: number } {
  const { path } = vehicle;
  const distance = (vehicle.offset + seconds * vehicle.speed) % path.length;
  let low = 0, high = path.cumulative.length - 1;
  while (low < high - 1) {
    const middle = (low + high) >> 1;
    if (path.cumulative[middle]! <= distance) low = middle; else high = middle;
  }
  const a = path.points[low]!, b = path.points[Math.min(low + 1, path.points.length - 1)]!;
  const segment = Math.max(0.001, path.cumulative[Math.min(low + 1, path.cumulative.length - 1)]! - path.cumulative[low]!);
  const fraction = Math.max(0, Math.min(1, (distance - path.cumulative[low]!) / segment));
  const dx = (b[0] - a[0]) / segment, dz = (b[1] - a[1]) / segment;
  const lane = Math.min(2.2, Math.max(1.25, path.width * 0.22)) * vehicle.lane;
  const x = a[0] + (b[0] - a[0]) * fraction - dz * lane;
  const z = a[1] + (b[1] - a[1]) * fraction + dx * lane;
  return { x, z, heading: Math.atan2(dx, dz) };
}

export class TorontoScene {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly scene = new THREE.Scene();
  readonly controls: OrbitControls;
  readonly buildings = new THREE.Group();
  readonly greenery = new THREE.Group();
  readonly paths = new THREE.Group();
  readonly traffic = new THREE.Group();
  private readonly city = new THREE.Group();
  private readonly people = new THREE.Group();
  private readonly light = new THREE.DirectionalLight('#ffd9a0', 3.4);
  private readonly ambient = new THREE.HemisphereLight('#dfe8ef', '#8a8274', 0.55);
  private readonly sky: Sky;
  private readonly waterNormals = waterNormalTexture();
  private readonly noise = noiseTexture();
  private readonly waterMaterial: THREE.MeshStandardMaterial;
  private readonly slipWater: THREE.MeshStandardMaterial;
  private fillTrees: Point[] = [];
  private readonly resizeObserver: ResizeObserver;
  private readonly dummy = new THREE.Object3D();
  private readonly facadeUniforms: FacadeUniforms = { uNight: { value: 0 } };
  private readonly ring: THREE.Mesh;
  private readonly route = new THREE.Group();
  private readonly proposedLocationMarker = new THREE.Group();
  private readonly rolloutSites = new RolloutSiteLayer();
  private readonly shoreline: Point[];
  private readonly land: Point[];
  private readonly atmosphere = { top: new THREE.Color(), horizon: new THREE.Color(), sun: new THREE.Color(), sunDirection: new THREE.Vector3(), azimuth: 0, elevation: 0 };
  private bodies: THREE.InstancedMesh | null = null;
  private heads: THREE.InstancedMesh | null = null;
  private legs: THREE.InstancedMesh | null = null;
  private trafficBodies: THREE.InstancedMesh | null = null;
  private trafficCabins: THREE.InstancedMesh | null = null;
  private trafficWheels: THREE.InstancedMesh | null = null;
  private trafficVehicles: TrafficVehicle[] = [];
  private crowd: Crowd;
  private selected: number | null = null;
  private following = false;
  private paused = false;
  private speed = 10;
  private seconds = 0;
  private lastTime = 0;
  private lastTick = 0;
  private backgroundTimer = 0;
  private backgroundLastTime = 0;
  private flight: CameraFlight | null = null;
  private lighting: Lighting = 'golden';
  private environmentFrames = 0;
  private disposed = false;
  private pointerStart = new THREE.Vector2();
  private reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  private readonly visibilityChanged = () => {
    if (document.hidden) this.startBackgroundClock();
    else this.stopBackgroundClock();
  };

  constructor(private readonly container: HTMLDivElement, private readonly district: District, private readonly islands: Islands,
    private readonly onTick: (tick: SceneTick) => void, private readonly onSelect: (id: number | null) => void,
    private trace: FoodTrace, private readonly onSelectSite: (id: string | null) => void, private runRef: RunRef) {
    this.crowd = foodCrowd(trace, district);
    this.rolloutSites.setTrace(trace);
    this.shoreline = joinShoreline(district.shores);
    this.land = landPolygon(this.shoreline, 30000);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = lightRecipes.golden.exposure;
    this.renderer.domElement.setAttribute('aria-label', 'Interactive 3D view of downtown Toronto. Drag to orbit, right drag to pan, scroll to zoom.');
    this.renderer.domElement.setAttribute('role', 'img');
    this.updateRunRefLabel();
    container.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(38, 1, 2, 16000);
    this.camera.position.copy(initialCamera.position);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.copy(initialCamera.target);
    this.controls.enableDamping = true; this.controls.dampingFactor = 0.075;
    this.controls.minDistance = 55; this.controls.maxDistance = MAX_DISTANCE;
    this.controls.minPolarAngle = 0.15; this.controls.maxPolarAngle = Math.PI / 2.08;
    this.controls.addEventListener('start', this.cancelFlight);

    const recipe = lightRecipes.golden;
    Object.assign(this.atmosphere, { azimuth: recipe.azimuth, elevation: recipe.elevation });
    this.atmosphere.top.set(recipe.top); this.atmosphere.horizon.set(recipe.horizon); this.atmosphere.sun.set(recipe.sun);
    this.sky = new Sky(this.renderer);
    this.updateAtmosphere();
    this.scene.environment = this.sky.refreshEnvironment();
    this.scene.fog = new THREE.Fog(this.atmosphere.horizon.clone(), 3000, 12500);
    this.waterMaterial = new THREE.MeshStandardMaterial({ color: recipe.water, roughness: 0.12, metalness: 0, normalMap: this.waterNormals, normalScale: new THREE.Vector2(0.18, 0.18) });
    this.waterNormals.repeat.set(50 / 230, 50 / 230);
    this.slipWater = this.waterMaterial.clone();

    this.light.castShadow = true; this.light.shadow.mapSize.set(2048, 2048);
    Object.assign(this.light.shadow.camera, { near: 50, far: 9000 });
    this.light.shadow.normalBias = 0.8; this.light.shadow.bias = -0.0002;
    this.scene.add(this.sky.mesh, this.light, this.light.target, this.ambient, this.city, this.people, this.route);
    this.city.add(this.buildings, this.greenery, this.paths, this.traffic, this.proposedLocationMarker, this.rolloutSites.group); this.paths.visible = false;
    this.buildProposedLocationMarker();
    this.buildLandscape(); this.buildTraffic(); this.buildArchitecture(); this.buildSurroundings(); this.buildTrees(); this.buildLandmarks(); this.buildPeople();
    this.ring = new THREE.Mesh(new THREE.RingGeometry(5.25, 7.5, 48), new THREE.MeshBasicMaterial({ color: '#e5f5b7', side: THREE.DoubleSide }));
    this.ring.rotation.x = -Math.PI / 2; this.ring.visible = false; this.ring.renderOrder = 10; this.scene.add(this.ring);
    this.resizeObserver = new ResizeObserver(this.resize); this.resizeObserver.observe(container); this.resize();
    this.renderer.domElement.addEventListener('pointerdown', this.pointerDown);
    this.renderer.domElement.addEventListener('pointerup', this.pointerUp);
    this.renderer.domElement.addEventListener('webglcontextlost', this.contextLost);
    this.renderer.setAnimationLoop(this.animate);
    document.addEventListener('visibilitychange', this.visibilityChanged);
    if (document.hidden) this.startBackgroundClock();
    if (import.meta.env.DEV) Object.assign(window, { toronto: this, THREE });
  }

  private buildLandscape(): void {
    const lake = new THREE.Mesh(new THREE.PlaneGeometry(60000, 60000), this.waterMaterial);
    lake.rotation.x = -Math.PI / 2; lake.position.y = WATER_Y; lake.receiveShadow = true; this.city.add(lake);
    // Match GroundBuilder's world-metre UVs so ripples line up with the harbour slips.
    const lakeUv = lake.geometry.getAttribute('uv');
    for (let i = 0; i < lakeUv.count; i++) lakeUv.setXY(i, (lakeUv.getX(i) - 0.5) * 1200, (0.5 - lakeUv.getY(i)) * 1200);

    const surface = (color: string, extra: THREE.MeshStandardMaterialParameters = {}) =>
      new THREE.MeshStandardMaterial({ color, roughness: 0.95, map: this.noise, envMapIntensity: 0.45, ...extra });
    const solid = (builder: GroundBuilder, material: THREE.Material, group = this.city) => {
      const mesh = new THREE.Mesh(builder.geometry(), material); mesh.receiveShadow = true; group.add(mesh); return mesh;
    };
    const layer = (builder: GroundBuilder, material: THREE.Material, order: number, group = this.city) => {
      const mesh = groundLayer(builder, material, order); if (mesh) group.add(mesh);
    };
    const ground = new GroundBuilder(); ground.polygon(this.land, 0);
    solid(ground, groundMaterial(this.noise));
    const quay = new GroundBuilder(); quay.wall(this.shoreline, WATER_Y - 0.5, 0);
    for (const island of this.islands.islands) quay.wall(island.polygon, WATER_Y - 0.5, 0.3);
    solid(quay, new THREE.MeshStandardMaterial({ color: '#7d7a72', roughness: 0.9, side: THREE.DoubleSide }));
    const islandGround = new GroundBuilder();
    for (const island of this.islands.islands) islandGround.polygon(island.polygon, 0.3);
    solid(islandGround, surface('#6e8150'), this.greenery);

    const valleyLeft: Point[] = [], valleyRight: Point[] = [], river: Point[] = [], parkway: Point[] = [];
    for (let z = FILL_LIMIT.minZ; z <= 1100; z += 80) {
      const x = donValleyX(z);
      valleyLeft.push([x - 190, z]); valleyRight.push([x + 190, z]); river.push([x - 55, z]); parkway.push([x + 75, z]);
    }
    const parks = new GroundBuilder();
    for (const park of this.district.parks) parks.polygon(park.polygon, 0.1);
    parks.polygon([...valleyLeft, ...valleyRight.slice().reverse()], 0.1);
    layer(parks, surface('#5f7a45'), 1, this.greenery);

    const water = new GroundBuilder();
    for (const area of this.district.water) water.polygon(area.polygon, 0.15);
    water.ribbon(river, 30, 0.15);
    layer(water, this.slipWater, 2);

    const sidewalks = new GroundBuilder(), footpaths = new GroundBuilder(), streets = new GroundBuilder();
    const yellow = new GroundBuilder(), white = new GroundBuilder();
    for (const road of this.district.roads) for (const line of clipToCore(road.points)) {
      if (pathKinds.has(road.kind)) { footpaths.ribbon(line, road.width, 0.25); continue; }
      sidewalks.ribbon(line, road.width + 6, 0.2);
      streets.ribbon(line, road.width, 0.3);
      const ends = [line[0]!, line[line.length - 1]!];
      for (const end of ends) { sidewalks.disc(end, road.width / 2 + 3, 0.2); streets.disc(end, road.width / 2, 0.3); }
      if (road.width >= 13 && !road.kind.includes('link')) yellow.ribbon(line, 0.45, 0.4);
      if (road.width < 16) continue;
      for (let i = 0; i < line.length - 1; i++) {
        const a = line[i]!, b = line[i + 1]!, d = Math.hypot(b[0] - a[0], b[1] - a[1]);
        if (d < 0.05) continue;
        const dx = (b[0] - a[0]) / d, dz = (b[1] - a[1]) / d;
        for (const side of [-1, 1]) for (let m = 6; m < d - 6; m += 12) {
          const ox = -dz * side * road.width / 4, oz = dx * side * road.width / 4;
          white.ribbon([[a[0] + dx * m + ox, a[1] + dz * m + oz], [a[0] + dx * (m + 3) + ox, a[1] + dz * (m + 3) + oz]], 0.18, 0.4);
        }
      }
    }
    streets.ribbon(parkway, 26, 0.3);
    for (const runway of this.islands.runways) {
      streets.ribbon(runway.points, runway.width, 0.55);
      const a = runway.points[0]!, b = runway.points[runway.points.length - 1]!, d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      for (let m = 60; m < d - 60; m += 50) {
        const t = m / d;
        white.ribbon([[a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], [a[0] + (b[0] - a[0]) * (t + 25 / d), a[1] + (b[1] - a[1]) * (t + 25 / d)]], 0.9, 0.6);
      }
    }
    layer(sidewalks, surface('#a9a69d'), 3);
    layer(footpaths, surface('#b3aa95'), 4);
    layer(streets, surface('#3f4346', { roughness: 0.9 }), 5);
    const sleepers = sleeperTexture();
    const rails = new GroundBuilder();
    for (const rail of this.district.rails) for (const line of clipToCore(rail)) rails.ribbon(line, 3.2, 0.45, 1.3);
    layer(rails, new THREE.MeshStandardMaterial({ map: sleepers, roughness: 0.95 }), 6);
    layer(yellow, new THREE.MeshBasicMaterial({ color: '#b39a4a' }), 7);
    layer(white, new THREE.MeshBasicMaterial({ color: '#c9c8c0' }), 7);

    const points: number[] = [];
    for (const [a, b, kind] of this.district.walkEdges) {
      if (kind === 'crossing') continue;
      const p = this.district.walkNodes[a]!, q = this.district.walkNodes[b]!;
      points.push(p[0], 0.4, p[1], q[0], 0.4, q[1]);
    }
    const pathGeometry = new THREE.BufferGeometry(); pathGeometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
    this.paths.add(new THREE.LineSegments(pathGeometry, new THREE.LineBasicMaterial({ color: '#c3f2be', transparent: true, opacity: 0.65 })));
  }

  /** Adds decorative cars on long road circuits, animated independently of the simulation playhead. */
  private buildTraffic(): void {
    const random = trafficRandom(20261017);
    const paths = trafficPaths(this.district, 360, random);
    const count = paths.length;
    if (!count) return;
    this.trafficVehicles = paths.map(path => ({
        path,
        offset: random() * Math.min(2500, path.length * 0.08),
        speed: 8 + random() * 4,
        lane: 0.9 + random() * 0.2,
        scale: random() < 0.1 ? 1.12 : 0.92 + random() * 0.12,
        color: vehicleColors[Math.floor(random() * vehicleColors.length)]!,
      }));

    this.trafficBodies = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1.9, 0.9, 4.7),
      new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 0.7, metalness: 0.03 }), count,
    );
    this.trafficCabins = new THREE.InstancedMesh(
      new THREE.BoxGeometry(1.52, 1.9, 2.65),
      new THREE.MeshStandardMaterial({ color: '#283940', roughness: 0.38, metalness: 0.08 }), count,
    );
    const wheelGeometry = new THREE.CylinderGeometry(0.34, 0.34, 0.22, 10);
    wheelGeometry.rotateZ(Math.PI / 2);
    this.trafficWheels = new THREE.InstancedMesh(
      wheelGeometry,
      new THREE.MeshStandardMaterial({ color: '#25282a', roughness: 0.95 }), count * 4,
    );
    for (let i = 0; i < count; i++) this.trafficBodies.setColorAt(i, new THREE.Color(this.trafficVehicles[i]!.color));
    for (const mesh of [this.trafficBodies, this.trafficCabins, this.trafficWheels]) {
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.frustumCulled = false;
      this.traffic.add(mesh);
    }
  }

  private updateTraffic(): void {
    if (!this.trafficBodies || !this.trafficCabins || !this.trafficWheels) return;
    for (let i = 0; i < this.trafficVehicles.length; i++) {
      const vehicle = this.trafficVehicles[i]!;
      const pose = sampleTraffic(vehicle, this.seconds);
      this.dummy.rotation.set(0, pose.heading, 0);
      this.dummy.scale.set(vehicle.scale, vehicle.scale, vehicle.scale);
      this.dummy.position.set(pose.x, 0.3 + 0.75 * vehicle.scale, pose.z);
      this.dummy.updateMatrix(); this.trafficBodies.setMatrixAt(i, this.dummy.matrix);
      this.dummy.position.y = 0.3 + 2.15 * vehicle.scale;
      this.dummy.position.x += Math.sin(pose.heading) * -0.1 * vehicle.scale;
      this.dummy.position.z += Math.cos(pose.heading) * -0.1 * vehicle.scale;
      this.dummy.updateMatrix(); this.trafficCabins.setMatrixAt(i, this.dummy.matrix);
      let wheel = i * 4;
      for (const x of [-0.82, 0.82]) for (const z of [-1.35, 1.35]) {
        const wheelX = x * vehicle.scale, wheelZ = z * vehicle.scale;
        const wx = pose.x + Math.cos(pose.heading) * wheelX + Math.sin(pose.heading) * wheelZ;
        const wz = pose.z - Math.sin(pose.heading) * wheelX + Math.cos(pose.heading) * wheelZ;
        this.dummy.position.set(wx, 0.3 + 0.34 * vehicle.scale, wz);
        this.dummy.updateMatrix(); this.trafficWheels.setMatrixAt(wheel++, this.dummy.matrix);
      }
    }
    this.trafficBodies.instanceMatrix.needsUpdate = true;
    this.trafficCabins.instanceMatrix.needsUpdate = true;
    this.trafficWheels.instanceMatrix.needsUpdate = true;
  }

  private buildArchitecture(): void {
    const cn = landmarks[0]!.point, rogers = landmarks[1]!.point;
    const geometry = buildingGeometry(resolveBuildingParts(this.district.buildings), building => {
      const poly = building.polygon;
      const centre = poly.reduce((p, q) => [p[0] + q[0] / poly.length, p[1] + q[1] / poly.length], [0, 0]);
      return Math.hypot(centre[0]! - cn[0], centre[1]! - cn[1]) < 37 ||
        (Math.abs(centre[0]! - rogers[0]) < 135 && Math.abs(centre[1]! - rogers[1]) < 115);
    });
    const mesh = new THREE.Mesh(geometry, facadeMaterial(this.facadeUniforms, false));
    mesh.castShadow = true; mesh.receiveShadow = true;
    this.buildings.add(mesh);
  }

  /** Cheap instanced city beyond the mapped core so the view never ends in empty ground. */
  private buildSurroundings(): void {
    const angle = streetGridAngle(this.district.roads);
    const fill = buildSurroundings(angle, this.land);
    const pads = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0),
      new THREE.MeshStandardMaterial({ roughness: 0.95, envMapIntensity: 0.45 }), fill.blocks.length);
    const paving = new THREE.Color('#9f9c94'), grass = new THREE.Color('#5f7a45');
    fill.blocks.forEach((block, i) => {
      this.dummy.position.set(block.x, 0, block.z); this.dummy.rotation.set(0, -angle, 0); this.dummy.scale.set(block.width, 0.3, block.depth);
      this.dummy.updateMatrix(); pads.setMatrixAt(i, this.dummy.matrix); pads.setColorAt(i, block.park ? grass : paving);
    });
    pads.receiveShadow = true;
    this.city.add(pads);
    this.buildings.add(fillerMesh(fill.buildings, angle, facadeMaterial(this.facadeUniforms, true)));
    this.fillTrees = fill.parkTrees;
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
        if (insidePolygon(point, park.polygon) && treeIsClear(point, size)) locations.push({ point, size });
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
          if (Math.abs(p[0]) < 1700 && p[1] > -1700 && p[1] < 1500 && treeIsClear(p, size)) locations.push({ point: p, size });
        }
      }
    }
    // Distant trees use a coarser crown: islands, the Don Valley and procedural parks.
    const far: { point: Point; size: number }[] = this.fillTrees.map(point => ({ point, size: 1.1 + rand() * 0.8 }));
    for (const island of this.islands.islands) {
      const xs = island.polygon.map(p => p[0]), zs = island.polygon.map(p => p[1]);
      const minX = Math.min(...xs), maxX = Math.max(...xs), minZ = Math.min(...zs), maxZ = Math.max(...zs);
      const attempts = Math.min(9000, Math.floor((maxX - minX) * (maxZ - minZ) / 450));
      for (let i = 0; i < attempts; i++) {
        const point: Point = [minX + rand() * (maxX - minX), minZ + rand() * (maxZ - minZ)];
        if (!insidePolygon(point, island.polygon)) continue;
        if (this.islands.runways.some(r => r.points.some((q, k) => k > 0 && distanceToSegment(point, r.points[k - 1]!, q) < 110))) continue;
        far.push({ point, size: 1.2 + rand() * 0.9 });
      }
    }
    for (let z = FILL_LIMIT.minZ; z < 1050; z += 9) {
      const x = donValleyX(z) + (rand() - 0.5) * 360;
      if (Math.abs(x - donValleyX(z) + 55) > 24 && Math.abs(x - donValleyX(z) - 75) > 20) far.push({ point: [x, z], size: 1 + rand() * 0.7 });
    }
    const crownMaterial = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: 1, flatShading: true });
    const trunkMaterial = new THREE.MeshStandardMaterial({ color: '#5c5144', roughness: 1 });
    const plant = (list: typeof locations, detail: number, groundY: (p: Point) => number) => {
      const crowns = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(TREE_CANOPY_RADIUS, detail), crownMaterial, list.length);
      const trunks = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.6, 0.9, 7, 5), trunkMaterial, list.length);
      list.forEach(({ point, size }, i) => {
        const y = groundY(point);
        this.dummy.position.set(point[0], y + 10 * size, point[1]); this.dummy.rotation.set(0, rand() * 6, 0); this.dummy.scale.set(size, size * 1.15, size); this.dummy.updateMatrix();
        crowns.setMatrixAt(i, this.dummy.matrix); crowns.setColorAt(i, new THREE.Color().setHSL(0.2 + rand() * 0.08, 0.3 + rand() * 0.15, 0.17 + rand() * 0.1));
        this.dummy.position.y = y + 4 * size; this.dummy.updateMatrix(); trunks.setMatrixAt(i, this.dummy.matrix);
      });
      crowns.castShadow = true; crowns.receiveShadow = true; trunks.castShadow = true;
      this.greenery.add(crowns, trunks);
    };
    plant(locations.slice(0, 4500), 1, () => 0);
    plant(far, 0, p => (insidePolygon(p, this.land) ? 0 : 0.3));
  }

  private buildLandmarks(): void {
    const concrete = new THREE.MeshStandardMaterial({ color: '#cfc8b8', roughness: 0.72 });
    const glass = new THREE.MeshStandardMaterial({ color: '#3d5a63', metalness: 0.6, roughness: 0.15 });
    const roof = new THREE.MeshStandardMaterial({ color: '#e6e2d6', metalness: 0.12, roughness: 0.5 });
    const cn = new THREE.Group(); cn.position.set(landmarks[0]!.point[0], 0, landmarks[0]!.point[1]); this.buildings.add(cn);
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
    stadium.position.set(r[0], 0, r[1]); stadium.rotation.y = -0.25; this.buildings.add(stadium);
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
  }

  private buildPeople(): void {
    for (const child of [...this.people.children]) {
      if (child instanceof THREE.Mesh) { child.geometry.dispose(); if (child.material instanceof THREE.Material) child.material.dispose(); }
      this.people.remove(child);
    }
    const count = this.crowd.residents.length;
    this.bodies = new THREE.InstancedMesh(new THREE.CapsuleGeometry(1.3 * PEDESTRIAN_SCALE, 2.4 * PEDESTRIAN_SCALE, 3, 5), new THREE.MeshStandardMaterial({ roughness: 0.85 }), count);
    this.heads = new THREE.InstancedMesh(new THREE.SphereGeometry(1.25 * PEDESTRIAN_SCALE, 7, 5), new THREE.MeshStandardMaterial({ color: '#eed2ae', roughness: 1 }), count);
    this.legs = new THREE.InstancedMesh(new THREE.BoxGeometry(0.9 * PEDESTRIAN_SCALE, 2.7 * PEDESTRIAN_SCALE, 1 * PEDESTRIAN_SCALE), new THREE.MeshStandardMaterial({ color: '#465f5a', roughness: 1 }), count * 2);
    for (const resident of this.crowd.residents) this.bodies.setColorAt(resident.id, new THREE.Color(resident.color));
    this.bodies.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.heads.instanceMatrix.setUsage(THREE.DynamicDrawUsage); this.legs.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.bodies.frustumCulled = false; this.heads.frustumCulled = false; this.legs.frustumCulled = false;
    this.people.add(this.bodies, this.heads, this.legs);
  }

  private pose(resident: Resident) { return foodPose(this.trace, resident, this.seconds); }

  private updateAtmosphere(): void {
    const a = this.atmosphere, c = Math.cos(a.elevation);
    a.sunDirection.set(Math.sin(a.azimuth) * c, Math.sin(a.elevation), Math.cos(a.azimuth) * c);
    this.sky.update({ ...a, sun: a.sun.clone().multiplyScalar(Math.min(1, this.light.intensity / 3)) });
  }
  /** Keeps the target over the city and the camera inside the filled surroundings. */
  private confine(): void {
    const t = this.controls.target, c = this.camera.position;
    const target = clampToBox(t, TARGET_LIMIT), dx = target.x - t.x, dz = target.z - t.z;
    if (dx || dz) { t.x = target.x; t.z = target.z; c.x += dx; c.z += dz; }
    t.y = THREE.MathUtils.clamp(t.y, 0, 450);
    const camera = clampToBox(c, CAMERA_LIMIT);
    c.x = camera.x; c.z = camera.z;
  }
  /** Shadow frustum follows the view so street level gets crisp shadows and the skyline stays covered. */
  private updateShadows(): void {
    const t = this.controls.target, size = THREE.MathUtils.clamp(this.camera.position.distanceTo(t) * 0.8, 260, 2400);
    const shadow = this.light.shadow.camera;
    if (Math.abs(shadow.right - size) > size * 0.05) {
      Object.assign(shadow, { left: -size, right: size, top: size, bottom: -size }); shadow.updateProjectionMatrix();
    }
    const step = size * 2 / 2048, x = Math.round(t.x / step) * step, z = Math.round(t.z / step) * step, d = this.atmosphere.sunDirection;
    this.light.target.position.set(x, 0, z);
    this.light.position.set(x + d.x * 4000, d.y * 4000, z + d.z * 4000);
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
      const p = this.pose(resident);
      if (this.camera.position.distanceTo(new THREE.Vector3(p.x, pedestrianY(8), p.z)) > obstruction + 3) continue;
      point.set(p.x, pedestrianY(8), p.z).project(this.camera);
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
  private publishTick(now: number, walking?: number): void {
    if (now - this.lastTick <= 350) return;
    let walkingCount = walking;
    if (walkingCount === undefined) {
      walkingCount = 0;
      for (const resident of this.crowd.residents) if (this.pose(resident).walking) walkingCount++;
    }
    const resident = this.selected === null ? undefined : this.crowd.residents[this.selected];
    this.rolloutSites.update(this.seconds);
    this.onTick({ seconds: this.seconds, walking: walkingCount, resting: this.crowd.residents.length - walkingCount,
      selected: resident ? foodInspection(this.trace, resident, this.seconds) : null });
    this.lastTick = now;
  }
  private startBackgroundClock(): void {
    if (this.backgroundTimer || this.disposed) return;
    this.backgroundLastTime = performance.now();
    this.lastTime = 0;
    this.backgroundTimer = window.setInterval(() => {
      const now = performance.now();
      const elapsed = Math.max(0, (now - this.backgroundLastTime) / 1000);
      this.backgroundLastTime = now;
      if (!this.paused) this.seconds = Math.min(this.trace.horizon_seconds, this.seconds + elapsed * this.speed);
      this.publishTick(now);
    }, 250);
  }
  private stopBackgroundClock(): void {
    if (this.backgroundTimer) window.clearInterval(this.backgroundTimer);
    this.backgroundTimer = 0;
    this.backgroundLastTime = 0;
    this.lastTime = 0;
    this.lastTick = 0;
  }
  private animate = (now: number): void => {
    if (this.disposed) return;
    const elapsed = this.lastTime ? Math.max(0, (now - this.lastTime) / 1000) : 0;
    const delta = Math.min(elapsed, 0.1); this.lastTime = now;
    if (!this.paused && !document.hidden) this.seconds = Math.min(this.trace.horizon_seconds, this.seconds + delta * this.speed);
    let walking = 0;
    this.dummy.scale.setScalar(1);
    for (const resident of this.crowd.residents) {
      const p = this.pose(resident);
      if (p.walking) walking++;
      const gait = p.walking ? Math.sin(this.seconds * resident.speed * 3.8 + resident.id) * PEDESTRIAN_SCALE : 0;
      this.dummy.rotation.set(0, p.heading, 0);
      const bounce = Math.abs(gait) * 0.2;
      this.dummy.position.set(p.x, pedestrianY(5.2) + bounce, p.z); this.dummy.updateMatrix(); this.bodies?.setMatrixAt(resident.id, this.dummy.matrix);
      this.dummy.position.y = pedestrianY(8.8) + bounce; this.dummy.updateMatrix(); this.heads?.setMatrixAt(resident.id, this.dummy.matrix);
      for (let side = 0; side < 2; side++) {
        const off = (side === 0 ? -0.75 : 0.75) * PEDESTRIAN_SCALE, swing = gait * (side === 0 ? -1 : 1);
        this.dummy.position.set(p.x + Math.cos(p.heading) * off + Math.sin(p.heading) * swing, pedestrianY(2.8), p.z - Math.sin(p.heading) * off + Math.cos(p.heading) * swing);
        this.dummy.rotation.set(swing * 0.4, p.heading, 0); this.dummy.updateMatrix(); this.legs?.setMatrixAt(resident.id * 2 + side, this.dummy.matrix);
      }
      if (this.selected === resident.id) {
        this.ring.position.set(p.x, 0.34, p.z); this.ring.scale.setScalar(1 + Math.sin(now / 600) * 0.08);
        if (this.following && !this.flight) {
          const difference = new THREE.Vector3(p.x, pedestrianY(8), p.z).sub(this.controls.target);
          this.camera.position.addScaledVector(difference, 0.05); this.controls.target.addScaledVector(difference, 0.05);
        }
      }
    }
    this.updateTraffic();
    if (this.bodies) this.bodies.instanceMatrix.needsUpdate = true;
    if (this.heads) this.heads.instanceMatrix.needsUpdate = true;
    if (this.legs) this.legs.instanceMatrix.needsUpdate = true;
    if (this.flight) {
      const t = Math.min(1, (now - this.flight.start) / (this.reducedMotion ? 1 : 1600)), eased = t * t * (3 - 2 * t);
      this.camera.position.lerpVectors(this.flight.from, this.flight.to, eased); this.controls.target.lerpVectors(this.flight.targetFrom, this.flight.targetTo, eased);
      if (t === 1) this.flight = null;
    }
    this.controls.update();
    this.confine();
    // Depth precision follows zoom so ground layers and walls never z-fight from afar.
    const near = THREE.MathUtils.clamp(this.camera.position.distanceTo(this.controls.target) * 0.015, 1.5, 45);
    if (Math.abs(near - this.camera.near) > 0.5) { this.camera.near = near; this.camera.updateProjectionMatrix(); }
    const recipe = lightRecipes[this.lighting], k = 0.035, a = this.atmosphere;
    a.top.lerp(new THREE.Color(recipe.top), k); a.horizon.lerp(new THREE.Color(recipe.horizon), k); a.sun.lerp(new THREE.Color(recipe.sun), k);
    a.azimuth = THREE.MathUtils.lerp(a.azimuth, recipe.azimuth, k); a.elevation = THREE.MathUtils.lerp(a.elevation, recipe.elevation, k);
    this.updateAtmosphere();
    if (this.scene.fog instanceof THREE.Fog) this.scene.fog.color.copy(a.horizon);
    this.waterMaterial.color.lerp(new THREE.Color(recipe.water), k); this.slipWater.color.copy(this.waterMaterial.color);
    this.light.color.copy(a.sun);
    this.light.intensity = THREE.MathUtils.lerp(this.light.intensity, recipe.sunPower, k);
    this.ambient.intensity = THREE.MathUtils.lerp(this.ambient.intensity, recipe.ambient, k);
    this.ambient.color.copy(a.top).lerp(a.horizon, 0.5);
    this.renderer.toneMappingExposure = THREE.MathUtils.lerp(this.renderer.toneMappingExposure, recipe.exposure, k);
    this.facadeUniforms.uNight.value = THREE.MathUtils.lerp(this.facadeUniforms.uNight.value, this.lighting === 'blue' ? 1 : 0, k);
    if (this.environmentFrames > 0 && this.environmentFrames-- % 15 === 0) this.scene.environment = this.sky.refreshEnvironment();
    this.waterNormals.offset.set(now * 0.0000035, now * 0.0000021);
    this.updateShadows();
    this.sky.follow(this.camera);
    this.renderer.render(this.scene, this.camera);
    this.publishTick(now, walking);
  };

  setPaused(paused: boolean): void { this.paused = paused; }
  setSpeed(speed: number): void { this.speed = speed; }
  setLighting(value: Lighting): void { this.lighting = value; this.environmentFrames = 150; }
  setLayer(layer: Layer, visible: boolean): void {
    this[layer].visible = visible;
  }
  setFoodTrace(trace: FoodTrace, runRef: RunRef): void {
    this.rolloutSites.setTrace(trace);
    this.trace = trace; this.runRef = runRef; this.updateRunRefLabel(); this.crowd = foodCrowd(trace, this.district);
    this.reset(); this.buildPeople(); this.onSelectSite(null);
  }
  reset(): void { this.seconds = firstPedestrianDeparture(this.trace); this.lastTime = 0; this.backgroundLastTime = performance.now(); this.lastTick = 0; this.select(null); }
  continueFoodTrace(trace: FoodTrace): void {
    this.trace = trace;
    this.crowd = foodCrowd(trace, this.district);
    this.seek(0);
    const following = this.following;
    this.select(this.selected);
    this.following = following;
  }
  seek(seconds: number): void { this.seconds = Math.max(0, Math.min(this.trace.horizon_seconds, seconds)); this.lastTime = 0; this.backgroundLastTime = performance.now(); this.lastTick = 0; }
  focusSite(id: string): void {
    const site = this.trace.sites.find(s => s.id === id);
    if (!site || this.seconds < site.active_from) return;
    this.select(null); this.onSelectSite(id);
    this.fly(new THREE.Vector3(site.point[0] + 180, 300, site.point[1] + 230), new THREE.Vector3(site.point[0], 8, site.point[1]));
  }
  setProposedLocation(point: Point | null): void {
    this.proposedLocationMarker.visible = point !== null;
    if (point) this.proposedLocationMarker.position.set(point[0], 0, point[1]);
  }
  focusProposedSite(point: Point): void {
    this.select(null); this.onSelectSite(null);
    this.fly(new THREE.Vector3(point[0] + 180, 300, point[1] + 230), new THREE.Vector3(point[0], 8, point[1]));
  }
  /** Project a rollout label above its mapped site, including camera movement while paused. */
  projectSite(point: Point): { x: number; y: number; visible: boolean } {
    const anchor = new THREE.Vector3(point[0], 38, point[1]).project(this.camera);
    const width = this.renderer.domElement.clientWidth, height = this.renderer.domElement.clientHeight;
    return { x: (anchor.x + 1) * width / 2, y: (1 - anchor.y) * height / 2,
      visible: anchor.z >= -1 && anchor.z <= 1 && Math.abs(anchor.x) < 1.12 && Math.abs(anchor.y) < 1.12 };
  }
  resetCamera(): void { this.following = false; this.fly(initialCamera.position.clone(), initialCamera.target.clone()); }
  zoom(direction: number): void {
    const offset = this.camera.position.clone().sub(this.controls.target).multiplyScalar(direction > 0 ? 0.75 : 1.3);
    offset.clampLength(55, MAX_DISTANCE); this.fly(this.controls.target.clone().add(offset), this.controls.target.clone());
  }
  select(id: number | null): void {
    this.selected = id; this.ring.visible = id !== null; this.following = false; this.onSelect(id);
    for (const child of [...this.route.children]) {
      if (child instanceof THREE.Mesh) { child.geometry.dispose(); if (child.material instanceof THREE.Material) child.material.dispose(); }
      this.route.remove(child);
    }
    const resident = id === null ? undefined : this.crowd.residents[id];
    if (resident) {
      const route = new GroundBuilder(); route.ribbon(resident.route, 3, 0.45);
      this.route.add(new THREE.Mesh(route.geometry(), new THREE.MeshBasicMaterial({ color: '#d6f3a3', transparent: true, opacity: 0.9 })));
    }
    this.lastTick = 0;
  }
  meetResident(): void {
    const union = landmarks.find(l => l.id === 'waterfront')!.point;
    let best = 0, nearest = Infinity;
    for (const resident of this.crowd.residents) {
      const p = this.pose(resident), d = Math.hypot(p.x - union[0], p.z - union[1]);
      if (d < nearest && p.walking) { nearest = d; best = resident.id; }
    }
    this.select(best); this.followSelected();
  }
  followSelected(): void {
    const resident = this.selected === null ? undefined : this.crowd.residents[this.selected];
    if (!resident) return;
    const p = this.pose(resident);
    this.fly(new THREE.Vector3(p.x + 35, 30, p.z + 35), new THREE.Vector3(p.x, pedestrianY(8), p.z));
    this.following = true;
  }
  private fly(position: THREE.Vector3, target: THREE.Vector3): void {
    this.flight = { from: this.camera.position.clone(), to: position, targetFrom: this.controls.target.clone(), targetTo: target, start: performance.now() };
  }
  private buildProposedLocationMarker(): void {
    const halo = new THREE.Mesh(new THREE.CircleGeometry(17, 40), new THREE.MeshBasicMaterial({
      color: '#d8f08a', transparent: true, opacity: 0.78, depthWrite: false, side: THREE.DoubleSide,
    }));
    halo.rotation.x = -Math.PI / 2; halo.position.y = 0.45; halo.renderOrder = 9;
    const pin = new THREE.Mesh(new THREE.ConeGeometry(5, 22, 14), new THREE.MeshBasicMaterial({ color: '#315d42' }));
    pin.position.y = 12; pin.renderOrder = 10;
    const head = new THREE.Mesh(new THREE.SphereGeometry(3.7, 16, 12), new THREE.MeshBasicMaterial({ color: '#e7f5ad' }));
    head.position.y = 23; head.renderOrder = 11;
    this.proposedLocationMarker.add(halo, pin, head);
    this.proposedLocationMarker.visible = false;
  }
  private updateRunRefLabel(): void {
    const identity = this.runRef.kind === 'council'
      ? `Council run ${this.runRef.run_id}, ${this.runRef.arm} arm`
      : `${this.runRef.population} resident ${this.runRef.policy} preset`;
    this.renderer.domElement.setAttribute('aria-label', `Interactive 3D view of downtown Toronto showing ${identity}. Drag to orbit, right drag to pan, scroll to zoom.`);
  }
  dispose(): void {
    this.rolloutSites.dispose();
    this.disposed = true; this.renderer.setAnimationLoop(null);
    this.stopBackgroundClock(); document.removeEventListener('visibilitychange', this.visibilityChanged);
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
          if (material instanceof THREE.MeshStandardMaterial) for (const t of [material.map, material.normalMap]) if (t) textures.add(t);
        }
      }
    });
    geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose());
    this.sky.dispose(); this.renderer.dispose(); this.container.replaceChildren();
  }
}
