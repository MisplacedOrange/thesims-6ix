# Toronto in motion

A browser environment for exploring Toronto and a bounded household food-access scenario. Pedestrians visit illustrative retailers, food-support sites, and school nutrition sites; the dashboard replays purchases, service, food use, and an optional emergency-site intervention settled in Python.

## Start the environment

Council runs now have a map project tracker: floating stage icons, simulated-time
progress bars, countdowns, and illustrative site furniture that appears at recorded
readiness/commissioning/opening milestones. New matched runs open on the map;
saved runs can be opened with **Watch rollout on map**. Use **Locate site**, the
timeline slider or milestone arrows to inspect a stage, and switch between
**Baseline** and **Approved changes**. Rewinding restores the earlier recorded
state. Progress bars interpolate schedule time; they do not measure construction
work or activate service. This view covers the existing single municipal food-site
action and its capacity changes, with no new infrastructure simulation effects.

Use Node.js 24 or newer, npm, and Python 3.10 or newer.

    cd apps/web
    npm install
    npm run dev

Open the Local URL printed by Vite. The development command starts Vite and the Python Council service together on loopback, and exports cached preset traces when inputs change. The service requires no API key or external model call. The Council panel supports proposal intake, proposal-linked organization records, stakeholder-input records, and inspection of organization links on saved rollout events. Scope, plan, decision, and stored-run controls remain unfinished in the UI. Organization references are contextual; they do not yet change simulated organization behavior. The stakeholder form records user-provided evidence and does not conduct outreach or verify representativeness.

The Simulation tab also offers optional [OpenAI plan drafts](../../docs/openai-planner.md). Configure the root `.env` locally to enable generation, save a scope, review sharing limits, generate and adopt a draft, then use the infrastructure planner's separate decision and run controls. Deterministic/manual planning and replay require no API key. Department-role notes remain deterministic advice. Model generation is disabled on the public Vercel service until Council authentication exists.

The repository also defines separate Vercel services for the browser app and Python Council API. The shared `/api/` path routes to the Council service. Its SQLite database defaults to `/tmp/council.sqlite` on Vercel, which is temporary and local to a function instance; saved records are not durable or shared across instances. Use a persistent database before relying on Council records in production.

For a production build:

    npm run build
    npm run preview

## Explore

Drag to orbit, right drag to pan, and scroll to zoom. Use the camera controls to reset or zoom the view. Click a visible pedestrian to inspect and follow a journey.

Preset simulations continue through successive Toronto calendar days while the city page is open. Pause, change speed, or restart from the scenario's first day. At midnight Python generates the next day with cash, remaining household/site/supplier food, and prices carried forward. Daily trips and service capacity renew; the emergency grant is paid only on the first day. New income, imports, and annual appropriations are not assumed, so resources can deplete. The dashboard follows the current day and reports daily totals. Council comparison runs remain bounded replays.

Continuation requires the Python service started by `npm run dev` (or a separately hosted Council service). Sessions live in that service's memory; refreshing starts a new run, and service restarts lose sessions. Only the latest trace and close checkpoint are retained, so this is not a durable history or checkpoint/resume system. Browser suspension and machine sleep can delay progress. Static preview alone cannot run live sessions.

Open the full-page analytics workspace from **Run dashboard** in the simulation header or at /dashboard. Review summary metrics and recent events, search and filter the interaction log, inspect service sites, and drill into household outcomes. Export the selected run as JSON. The dashboard replays cached preset traces. The Council API stores paired traces, but the current browser does not yet let a reviewer create or select them through the Council panel. Seeking does not settle transactions or create persistent multi-day reporting.

Keys 1 through 4 choose views. Space pauses movement. R restarts the pedestrian timeline. H hides the interface.

## Data and limitations

The checked-in snapshot covers the downtown area from longitude -79.405 to -79.365 and latitude 43.635 to 43.665. OpenStreetMap supplies building footprints and parts, streets, parks, railways, and shoreline. Source IDs and raw tile hashes remain in the snapshot. The data license is documented in public/data/LICENSE.md and attributed in the app.

Mapped heights and floor-count tags take precedence over estimates. CN Tower and Rogers Centre are newly created stylized models. Facades, trees, and decorative details are illustrative.

Mapped outdoor footpaths and derived parallel sidewalks form a connected walking graph. The preparation script removes paths inside ground-level building massing. These paths are a visual approximation, not a surveyed accessibility network.

Residents follow Python-generated food trips sampled at playback time. Crossing waits, queues, service, and trips home constrain food access. Household cash and food are committed by `sim.core`; browser seeking never settles transactions. Food is carried home before pantry use, and school portions are consumed at school. Daily activity begins at 08:30; food consumption closes each local day before continuation. Names, homes, eligibility and all site operations are synthetic. See [scenario assumptions and boundaries](../../sim/interactables/README.md). No live LLM or observed mobility data controls them.

Decorative cars move along mapped road centerlines. Their routes and density are illustrative; they do not represent observed traffic or affect pedestrian travel, congestion, or economic outcomes. A traffic model is outside the active roadmap.

The visual direction takes inspiration from [God's Plan at Hack the North 2026](https://devpost.com/software/shift-t15x3m). No application code or creative models were copied from that project.

## Rebuild the map

Python 3.10 or newer can rebuild the snapshot from the public OpenStreetMap map API:

    npm run data:prepare

Raw XML tiles are cached in .data-cache. Cached tiles retain their hashes and retrieval times. Remove the cache only when intentionally acquiring a newer map snapshot. The prepared database retains ODbL licensing.

## Check movement and build

    npm test
    npm run build

Tests cover legacy geometry and walking utilities plus food-trace replay, backward seeking, carried food, day boundaries, and dashboard group totals. Python interaction checks run from the root with `python -m unittest sim.interactables.test_simulation -v`. Visual acceptance also requires driving the running app.
