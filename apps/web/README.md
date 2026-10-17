# Toronto in motion

A browser environment for exploring downtown Toronto, its waterfront, and moving synthetic pedestrians. This milestone focuses on the visual world. Public solution scenarios and economic outcomes are deferred.

## Start the environment

Use Node.js 24 or newer and npm.

    cd apps/web
    npm install
    npm run dev

Open the Local URL printed by Vite. The frozen geographic snapshot is included. The app requires no API key, Python service, or live map request.

For a production build:

    npm run build
    npm run preview

## Explore

Drag to orbit, right drag to pan, and scroll to zoom. Choose a camera composition from the view panel. Click a visible pedestrian or choose **Meet a resident** to inspect and follow a journey.

Pause, change speed, or restart the same seeded population. Choose quiet, everyday, or lively population density. Switch between daylight, golden hour, and blue hour. Toggle building massing, greenery, walking routes, and labels.

Keys 1 through 4 choose views. Space pauses movement. R restarts the pedestrian timeline. H hides the interface.

## Data and limitations

The checked-in snapshot covers the downtown area from longitude -79.405 to -79.365 and latitude 43.635 to 43.665. OpenStreetMap supplies building footprints and parts, streets, parks, railways, and shoreline. Source IDs and raw tile hashes remain in the snapshot. The data license is documented in public/data/LICENSE.md and attributed in the app.

Mapped heights and floor-count tags take precedence over estimates. CN Tower and Rogers Centre are newly created stylized models. Facades, trees, and decorative details are illustrative.

Mapped outdoor footpaths and derived parallel sidewalks form a connected walking graph. The preparation script removes paths inside ground-level building massing. These paths are a visual approximation, not a surveyed accessibility network.

Residents follow seeded itineraries sampled directly at simulation time. They pause at destinations, turn, return, and repeat. Names and routines are synthetic. No live LLM or observed mobility data controls them.

The visual direction takes inspiration from [God's Plan at Hack the North 2026](https://devpost.com/software/shift-t15x3m). No application code or creative models were copied from that project.

## Rebuild the map

Python 3.10 or newer can rebuild the snapshot from the public OpenStreetMap map API:

    npm run data:prepare

Raw XML tiles are cached in .data-cache. Cached tiles retain their hashes and retrieval times. Remove the cache only when intentionally acquiring a newer map snapshot. The prepared database retains ODbL licensing.

## Check movement and build

    npm test
    npm run build

Tests exercise route connectivity, seeded replay, continuous walking speed, a full loop, and parsing and routing on the actual shipped Toronto snapshot. Visual acceptance also requires driving the running app.
