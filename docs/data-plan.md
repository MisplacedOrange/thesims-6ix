# Data plan

## 3D Toronto first

The first data milestone is a licensed, versioned Toronto world package with recognizable building massing, a usable street and pedestrian graph, stable feature IDs, and an explicit coordinate transform. Show lower-detail Toronto context outside the first active simulation area. Concentrate detailed destinations, pedestrian paths, and intervention sites inside that area. A geometry layer alone does not establish occupancy, rent, ownership, service capacity, or economic activity.

## Evidence states

Current implementation: the connected district uses the content-hashed illustrative snapshot under `sim/district/data`. Its exports include that source manifest and explicit synthetic labels. The API acquisition and refresh workflow below remains required implementation work; public-source links are not evidence that observations have been ingested.

Each parameter carries one of four states: observed, announced, estimated, or illustrative. Unknown is a missing value with a reason, not a zero. A source can be verified while its input remains unsuitable for calibration because geography, timing, or definition does not match.

No complete raw data ingestion has been performed in this planning task. Public sources have been located and selected claims checked. Partner-held prices, costs, utilization, and behavior still require access. The initial runnable dataset must identify every illustrative substitute.

## Priority data register

| Priority | Primary source | Required fields | Use and known gap |
| --- | --- | --- | --- |
| P0 | [Toronto 3D massing](https://open.toronto.ca/dataset/3d-massing/) | Building or tile IDs, geometry, height, coordinate system, licence, vintage | Primary 3D context. Inspect actual resource formats and coverage before choosing a renderer or converter. |
| P0 | [Toronto Centreline](https://ckan0.cf.opendata.inter.prod-toronto.ca/en/dataset/toronto-centreline-tcl) | Segment IDs, geometry, feature codes, mode eligibility, source vintage | Street foundation. Filter non-traversable features; it is not by itself a sidewalk or pedestrian graph. |
| P0 | Pedestrian links, crossings, barriers, and access | Stable link IDs, geometry, permitted modes, accessibility tags, source and quality flag | Build and validate the walkable graph for the active area. Identify gaps and synthetic links instead of silently routing across them. |
| P0 | [Toronto supermarket layer](https://gis.toronto.ca/arcgis/rest/services/cot_geospatial26/MapServer/4), [TDSB school directory](https://www.tdsb.on.ca/find-your/school) | Place IDs, names, coordinates, type, update date, status | Anchor the first active area and test feature-to-scene alignment. Verify current status and add non-supermarket food services separately. |
| P0 | Coordinate reference and map attribution | CRS, transform, local origin, licence, attribution, feature-ID mapping | Keep scene, route graph, services, and rollout sites spatially aligned and traceable to source records. |
| P1 | [TTC schedules](https://open.toronto.ca/dataset/ttc-routes-and-schedules/) | Stops, trips, stop times, service dates, accessibility | Add transit access where supported. Schedules do not establish observed reliability. Freeze feed validity. |
| P1 | [2021 Census income backgrounder](https://www.toronto.ca/wp-content/uploads/2022/07/9877-City-Planning-2021-Census-Backgrounder-Families-Hhlds-Marital-Status-Income.pdf) | Household size, age, tenure, income bands, geography | Aggregate controls for a synthetic population. Obtain underlying tables and disclosure metadata; income generally refers to 2020. |
| P1 | [CPI table 18-10-0004-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401), [retail prices 18-10-0245-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810024501), [Toronto cost of living](https://open.toronto.ca/dataset/cost-of-living-in-toronto-for-low-income-households/) | Geography, product, package size, month, price, household costs, vintage | Add economic attributes after the world is aligned. Confirm supported geographies and publication periods; supplement with dated local store audits. |
| P1 | [Second Harvest reports](https://www.secondharvest.ca/about/reports) and school or food-hub operators | Sites, eligible input, rescued versus purchased mass, shifts, yields, menus, uptake, costs | Model service and rollout constraints. Request local operating records; national reports do not establish local daily capacity. |
| P1 | [Who's Hungry 2025](https://www.dailybread.ca/wp-content/uploads/2025/12/DB-WHR-2025-Final_Nov-3_reader.pdf) | Visits, survey methods, program geography | Demand context and hardship constraints; daily unmet requests and supply need partner records. |
| P2 | Consented local behavior or sentiment study | Sampling, question wording, geography, date, consent, response rate | Optional validation stream. Keep observations separate from synthetic agent state and generated dialogue. |
| P2 | [Transport Canada site guidance](https://tc.canada.ca/en/aviation/drone-safety/learn-rules-you-fly-your-drone/where-fly-your-drone) | Constraints, route-assessment references, date | Only needed for a drone delivery scenario. Eligibility checks are not route approvals or an operational airspace feed. |

Weather, energy, vehicle specifications, and emission factors are additional datasets for a drone or environmental study, not prerequisites for the first Toronto pedestrian scene. Use dated authoritative measurements and vehicle-specific tests when available. Otherwise expose downtime and energy as illustrative ranges and suppress unsupported emissions claims.

## Snapshot contract

Each raw or derived dataset records:

```text
dataset_id, publisher, source_url, resource_url
retrieved_at, published_at, reference_period_start, reference_period_end
geography_id, boundary_vintage, units, price_base_month
licence_url, attribution, raw_sha256, transform_revision
row_count, missingness, quality_flags, evidence_state
```

Unknown publication dates remain null. Do not use retrieval time as publication time. Current pages with unverified vintages stay outside a strict historical baseline until an archived or dated resource confirms availability.

Store raw files immutably, normalized tables separately, and a manifest that pins both. Never refresh an old run's source data in place. Corrections create a new snapshot and a new run.

Toronto's Open Government Licence permits reuse subject to its conditions. Track attribution and inspect each resource's terms. School, survey, mapping, and partner data can have different restrictions. [Toronto licence](https://open.toronto.ca/open-data-licence/).

## Acquisition and transformation workflow

1. Resolve the downloadable resource and its licence, rather than stopping at a catalog page.
2. Save the raw bytes and metadata. Calculate a content hash.
3. Validate fields, geography, units, dates, uniqueness, and source quality flags.
4. Normalize products and geographic IDs using explicit mapping tables.
5. Produce quality reports and a rejected-row file. Do not silently discard failures.
6. Build the scenario input snapshot and preserve all source lineage.
7. Compare aggregate outputs against source totals before making the snapshot selectable.

External APIs and files are validation boundaries. Keep transforms deterministic and rerunnable. A changed upstream schema must fail clearly. A refresh produces a candidate snapshot for review and does not alter published experiments.

Use checks for duplicate store or school IDs, implausible package mass, mixed dollars and cents, geometry outside the chosen area, prices outside their reference period, and missing input shares. A facility maximum is an upper bound, not an observed row repeated across every day.

## Synthetic population

Create synthetic households and resident pedestrians that match available aggregate controls across household size, age bands, income, tenure, and area. Attach homes and initial positions to eligible residential areas or clearly synthetic buildings. Give each simulated person a synthetic ID and only the schedule and attributes needed for the modeled activity. Use a documented fitting method such as iterative proportional fitting once compatible controls and seed distributions are obtained. Retain the seed, convergence diagnostics, and residuals.

Aggregate controls do not identify the true joint distribution. Test several plausible household populations. If rent burden and income correlation are unknown, vary that correlation rather than inventing precise household budgets.

Reweight historic controls with dated newer evidence where justified. Do not inflate one historic median and describe the result as a measured 2026 income distribution. Keep demographic and price-year transformations separate.

Household IDs, names, appearance, and routines are synthetic. Do not reconstruct actual household addresses from food-bank or school records. Sensitive individual intake data are unnecessary for the first release.

## Local price and behavior measurements

Public averages cannot identify store-level prices, travel choices, or uptake. Prepare a small measurement protocol covering a fixed basket, date, store, package size, promotions, availability, and unit price. Record taxes where applicable and separate loyalty-only prices.

For behavior, request aggregate shopping frequency, program participation, travel modes, queue times, and changes after a price or service change. Consent-based surveys can ask what prevented uptake. Collect only fields needed for calibration and use an appropriate review process before a real study.

The first LLM evaluation panel uses synthetic cases. It does not need real names, chats, or private records. Real survey comments and generated comments have separate provenance and storage.

## Partner requests to prepare

| Partner category | Minimum aggregate request | Why it matters |
| --- | --- | --- |
| Municipal pilot team | Candidate sites, capital and operating budgets, supplier assumptions, planned dates | Feasibility and fiscal accounting |
| Processor | Daily input by source, rejects, output by recipe, shifts, storage, cost allocation | Usable capacity and delivered cost |
| School and food-hub operators | Active schools, days, uptake, menus, orders, prices, waste, delivery failures | Real service, procurement, and substitution |
| Food-bank network | Daily aggregate requests, served demand, unmet demand, stock, opening hours | Demand and capacity constraints |
| Carriers or drone operators | Payload, handling, downtime, maintenance, route and site costs, failed deliveries | Fair comparison against ground service |

These are proposed requests. No organization has been contacted and no private data access is implied.

## Tracking after the first snapshot

For an operational research workflow, ingest CPI and labor releases monthly, school provision by term and delivery day, store audits at a declared interval, and processor or hub logs at their actual reporting cadence. Keep both planned and actual dates.

A dashboard can show new source releases, stale inputs, quality failures, and baseline drift. Recalibration creates a new model version and keeps old comparisons reproducible. This document describes the future tracking system. No recurring automation has been scheduled.
