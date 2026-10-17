# Toronto environment implementation

## Scope

The current deliverable is a visually polished browser environment for Toronto with moving synthetic pedestrians. Public solutions, infrastructure planning, and economic outcomes are deferred. The existing Python economic fixture remains separate.

## Work plan

1. Ground: inspect God's Plan at Hack the North 2026, current repository, and available geographic sources.
2. Sketch: compare two independent environment and pedestrian designs, then record the chosen shape.
3. Agree: proceed within the user's visual environment scope without a checkpoint.
4. Implement: build the scene, pedestrian paths, camera and display controls, and source attribution.
5. Verify and simplify: drive the running app, inspect rendered output, check movement and controls, and remove unused pieces.

## Acceptance criteria

- Opens directly into a recognizable, attractive 3D Toronto scene.
- Displays geographically sourced streets and building footprints with explicit attribution and labeled approximations.
- Pedestrians move along walkable routes with visible activity, selectable details, pause, speed, and reset controls.
- Camera navigation and place presets make the environment easy to explore.
- Runs locally without API keys or the economic simulator.
- Contains no public solution controls or economic outcome views.

## Design comparison

Candidate A is the base: a standalone Vite, React, TypeScript and Three.js application, with immutable pedestrian itineraries sampled by one browser clock. Candidate B proposed Worker ownership and snapshots. The independent comparison favored A because time sampling makes pause, speed changes, seeking, and deterministic reset exact without a transport lifecycle. A Worker is unnecessary for the bounded population.

From B, retain explicit sidewalk/crossing edge kinds and resident metadata with a stable inspection lookup. Reject the Worker and Python service for this visual milestone. No candidate dropped out.

The app loads a frozen, attributed downtown map, constructs seeded routes once, and renders poses at any simulation time. Three.js owns scene geometry, instancing, camera, and picking. React owns the overlay controls and selection. The simulation module has no DOM, rendering, network, or economic imports.

### Caller and module sketch

```ts
const district = await loadDistrict();
const crowd = createCrowd(district, { seed: 2026, count: 600 });
const view = new TorontoScene(container, district, crowd, onResidentSelect);
view.setPlayback({ paused: false, speed: 10 });
view.setPreset('skyline');
```

- `district.ts`: validated data, local metre coordinates, building footprints/heights, streets, parks, walking graph and landmarks.
- `pedestrians.ts`: seeded connected routes, itinerary metadata, and pure time sampling.
- `scene.ts`: rendered geometry, landmarks, instanced residents, selection, camera and lighting.
- `App.tsx` and `style.css`: composed visual interface, layers, playback, resident details and attribution.
- `scripts/prepare_toronto.py`: repeatable geographic acquisition and normalization; output is checked in for offline runtime.

Main risk: a connected graph can still route across water, railway barriers or buildings. Prefer explicit mapped footpaths and valid street intersections, and inspect routes in the running scene.

## Implementation and acceptance record

Implemented in apps/web on October 17, 2026. The frozen downtown snapshot contains 8,549 building forms, sourced roads and parks, railway geometry, and joined Lake Ontario shoreline segments. Landmark artwork is newly created and stylized. The map database retains ODbL attribution.

The preparation script excludes indoor passages and service lanes without explicit pedestrian access. It also samples candidate paths against ground-level building footprints and rejects obstructed edges. The browser populates the largest connected outdoor graph with 200, 600, or 1,200 synthetic residents.

Four movement tests passed: graph edge membership, seeded replay, continuous walking and full-cycle reset, and routing on the actual shipped map. The production build passed. The Three.js bundle retains a size advisory at approximately 523 kB minified; this is not a frame-rate measurement.

Browser review used the local Chromium-based preview at desktop 1440 by 900 and mobile 390 by 844. Reviewed city framing, waterfront and resident follow views, route visibility, lighting, population changes, speed, pause, reset, settings, and source attribution. Pause retained its exact displayed time across interactions, and reset returned to 08:30:00. Mobile content width matched the viewport. The browser reported no console errors or warnings during these checks.

The review found and corrected indoor routes beneath roofs, a duplicated shoreline join, and a narrow mobile camera composition. Target-device performance, other browser engines, and a surveyed accessibility network remain unverified.
