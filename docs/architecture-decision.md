# Architecture decision: Toronto world runtime

## Decision status

The earlier architecture choice made Python the world authority and Three.js a browser renderer. It was made for an economic research prototype before the product priority was clarified. This record supersedes that choice as the proposed direction.

The clarified product starts with a 3D Toronto simulation where residents move through streets and public solutions are rolled out over time. The leading design is **Godot 4 .NET/C# for world time, navigation, pedestrian positions, and visible/headless stepping; Python for economic state, the planner, and research workflows**. This is a proposed direction, not an implementation commitment. A movement-focused vertical slice must prove the bridge and replay contract before the engine is final. Browser delivery remains an open requirement that could change the choice.

## Alternatives

| Option | Strength for this product | Main cost or risk |
| --- | --- | --- |
| Godot world runtime + Python economic worker | Integrated 3D scene and navigation for embodied pedestrians; reuses the tested Python economic kernel | Two processes and languages; the bridge, synchronization, and recovery must be reliable |
| Python world authority + browser Three.js client | Direct Python research flow and easy browser distribution | Makes the 3D world a projection of a Python simulation; movement and navigation are less central in the runtime |
| Godot owns world and economics | One in-engine simulation loop and fewer process boundaries | Rewrites or duplicates the existing Python economics and experiment logic |

Independent design review favored the Godot-world/Python-economy split because movement and 3D geography are primary product behavior. That review was a design judgment, not a benchmark. The highest risk is synchronizing two authoritative state domains without duplicate or partial transactions.

## Ownership rule

| State | Owner |
| --- | --- |
| Simulation clock, pedestrian and vehicle positions, paths, activity, and world occupancy | Godot |
| Money, food, household accounts, procurement, public costs, policy budgets, and settled service outcomes | Python economic kernel |
| Plan drafts, source references, deterministic validation, review records, and scenario definitions | Python coordinator |
| Durable ordered run archive and comparison export | Python coordinator |
| Meshes, camera, interpolation, selection, and visual detail | Godot |

The bridge carries run ID, logical time, world and economic revisions, and idempotency keys. Godot waits for Python receipts before showing a purchase, changing an economic display, or marking a rollout stage active. Pedestrian intent is not an economic transaction. The Python kernel remains the sole writer of cash and food.

## Proposed stack

- **World:** Godot 4 .NET with C#; native and headless builds share logical stepping.
- **Economy, agents, planner, studies:** existing Python 3.10+ code, extended through typed boundaries.
- **Bridge:** a private local Python service using a versioned request/receipt protocol; FastAPI with WebSocket transport is a candidate, not a fixed requirement.
- **Local persistence:** SQLite transactional archive with immutable, content-hashed input and result files.
- **Geospatial ingestion:** Python pipeline; GIS libraries and exact Toronto layers are selected after auditing download formats, CRS, licensing, and coverage.
- **Models:** deterministic rules first; optional small-model runtime and bounded server-side LLM adapter after replay and budgets exist.
- **Browser option:** Three.js remains a possible client if browser access is required, but it is no longer the default architecture.

The repository currently contains Python packages and terminal exports. It does not yet contain Godot, the bridge, FastAPI, SQLite run storage, Toronto map ingestion, a planner, or pedestrian model calls.

## First proof

Build the smallest runnable slice before expanding the city:

1. Load one frozen Toronto map area and source-feature IDs.
2. Move one synthetic resident on a valid pedestrian graph in visible and headless Godot runs.
3. Submit a legal trip or purchase intent across the bridge.
4. Receive one Python economic receipt and show its effect only after acceptance.
5. Replay the same inputs and compare world, economic, and bridge hashes.

If this proof cannot preserve ordering and replay, reconsider the runtime split before adding population or policy complexity. If browser delivery is required, prototype the same movement slice in the browser before making the engine choice final.

## Scope implications

The city scene is the primary environment. A school meal expansion can demonstrate infrastructure planning, but a school calendar does not define the simulation horizon. The planner may design kitchen, storage, staffing, procurement, and delivery stages for that case after the service rules are defined. Municipal groceries and food rescue/processing remain separate solution entries. Drone delivery is an optional logistics comparison.

The prior 16-week plan, CAD 252,480 illustrative budget, Python-owned world clock, and browser-only scene are superseded. No replacement schedule or budget is approved in this document.
