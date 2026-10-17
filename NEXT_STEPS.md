# Next steps for The Sims 6ix

Updated October 17, 2026. The active deliverable is a polished 3D Toronto environment with pedestrian agents. Public solutions and economic outcomes are deferred.

## Implemented visual environment

The browser application in apps/web displays a sourced downtown Toronto snapshot with building massing, street geometry, shoreline, parks, railways, and stylized landmark models. Seeded pedestrians walk connected outdoor routes, rest at destinations, and repeat their journeys.

Camera presets, orbit and zoom, resident inspection and follow, population density, daylight settings, layer controls, pause, speed, and reset are implemented. The app runs without API keys or the Python simulator. The environment guide records source attribution and approximation limits.

## Visual work to prioritize next

1. Review the environment with the team and choose the preferred camera composition, materials, and visual scale.
2. Inspect more pedestrian routes at close range, especially crossings, waterfront paths, and the railway corridor. Improve the derived sidewalk network where visual review finds gaps.
3. Profile scene load, frame time, and memory on the lowest-powered intended device. Set the browser and device support range from those results.
4. Add more accurate landmark detail or official Toronto massing where it improves the visual. Keep mapped, estimated, and stylized geometry identifiable.
5. Expand the geographic area after the current district's navigation and performance are satisfactory.

## Scope held for a later milestone

Public solution scenarios, infrastructure rollout planning, economic integration, outcomes, live LLM decisions, and long-running simulation storage are outside the current work. The existing Python food-policy fixture remains available separately.

No revised production schedule, budget, hosting topology, or device performance target is approved.
