# Toronto in motion

A browser environment for exploring Toronto and a bounded household food-access scenario. Pedestrians visit illustrative retailers, food-support sites, and school nutrition sites; the dashboard replays purchases, service, food use, and an optional emergency-site intervention settled in Python.

## Start the environment

Use Node.js 24 or newer, npm, and Python 3.10 or newer.

    cd apps/web
    npm install
    npm run dev

Open the Local URL printed by Vite. The development command starts Vite and the Python Council service together on loopback, and exports cached preset traces when inputs change. The bounded Council workflow requires no API key or external model call. Production builds include preset traces as static data but do not include a Python Council service.

For a production build:

    npm run build
    npm run preview

## Explore

Drag to orbit, right drag to pan, and scroll to zoom. Choose a camera composition from the view panel. Click a visible pedestrian or choose **Meet a resident** to inspect and follow a journey.

Pause, change speed, restart, or seek through the six-hour food-access day. Select a food scenario and quiet (200), everyday (600), or lively (1200) household population in city settings; changing either resets the day. Click a food-site marker to select it, then open its record in the dedicated dashboard. Resident inspection includes household cash, pantry, carried food, legal choices, and event history. Switch lighting and building, greenery, and walking-network layers through city settings.

Open the full-page analytics workspace from **Run dashboard** in the simulation header or at /dashboard. Choose a scenario and population, scrub the run timeline, review summary metrics and recent events, search and filter the interaction log, inspect service sites, and drill into household outcomes. Export the selected run as JSON. The dashboard replays cached presets and, when selected from Council, the exact stored six-hour paired-run trace. Its playhead stays paired with the open city tab; seeking does not settle transactions or create persistent multi-day reporting.

Keys 1 through 4 choose views. Space pauses movement. R restarts the pedestrian timeline. H hides the interface.

## Data and limitations

The checked-in snapshot covers the downtown area from longitude -79.405 to -79.365 and latitude 43.635 to 43.665. OpenStreetMap supplies building footprints and parts, streets, parks, railways, and shoreline. Source IDs and raw tile hashes remain in the snapshot. The data license is documented in public/data/LICENSE.md and attributed in the app.

Mapped heights and floor-count tags take precedence over estimates. CN Tower and Rogers Centre are newly created stylized models. Facades, trees, and decorative details are illustrative.

Mapped outdoor footpaths and derived parallel sidewalks form a connected walking graph. The preparation script removes paths inside ground-level building massing. These paths are a visual approximation, not a surveyed accessibility network.

Residents follow Python-generated food trips sampled at playback time. Crossing waits, queues, service, and trips home constrain food access. Household cash and food are committed by `sim.core`; browser seeking never settles transactions. Food is carried home before pantry use, and school portions are consumed at school. The day ends at 14:30 and does not loop. Names, homes, eligibility and all site operations are synthetic. See [scenario assumptions and boundaries](../../sim/interactables/README.md). No live LLM or observed mobility data controls them.

Decorative cars move along mapped road centerlines as a toggleable visual layer. Their routes and density are illustrative; they do not represent observed traffic or affect pedestrian travel, congestion, or economic outcomes.

The visual direction takes inspiration from [God's Plan at Hack the North 2026](https://devpost.com/software/shift-t15x3m). No application code or creative models were copied from that project.

## Rebuild the map

Python 3.10 or newer can rebuild the snapshot from the public OpenStreetMap map API:

    npm run data:prepare

Raw XML tiles are cached in .data-cache. Cached tiles retain their hashes and retrieval times. Remove the cache only when intentionally acquiring a newer map snapshot. The prepared database retains ODbL licensing.

## Check movement and build

    npm test
    npm run build

Tests cover legacy geometry and walking utilities plus food-trace replay, backward seeking, carried food, day boundaries, and dashboard group totals. Python interaction checks run from the root with `python -m unittest sim.interactables.test_simulation -v`. Visual acceptance also requires driving the running app.
