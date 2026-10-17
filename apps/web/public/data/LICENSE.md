# Toronto map data

The derived database in toronto.json contains information from OpenStreetMap,
which is made available under the Open Database License, ODbL 1.0.

Copyright OpenStreetMap contributors.

- Attribution and source: https://www.openstreetmap.org/copyright
- License: https://opendatacommons.org/licenses/odbl/1-0/
- Geographic extent: longitude -79.405 to -79.365, latitude 43.635 to 43.665.

The source block in toronto.json records each public OSM API tile URL and SHA-256
hash. Coordinates are a local metre approximation around longitude -79.385,
latitude 43.65. Missing building heights, parallel sidewalk offsets, and
intersection connectors are illustrative derived values. Ground-level building
footprints exclude outdoor routes that would pass through the rendered massing.

The application code and newly created procedural landmark artwork follow the
repository's MIT license. The map database retains its separate ODbL license.
