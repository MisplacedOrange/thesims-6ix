# Data plan

## Existing spatial baseline

The browser already uses a frozen, attributed OpenStreetMap snapshot of downtown Toronto with a walking graph for the bounded food-access scenario. Retain that context for the active pilot. A geometry layer alone does not establish occupancy, rent, ownership, service capacity, or economic activity. Broader map coverage is deferred unless the selected proposal requires it.

## Active evidence priorities

The next data work should support the selected proposal and actor map: dated operating status, authority or agreement, service hours and capacity, supplier availability and delivery constraints, prices and inventory, and costs only where needed for the proposal's outcomes. Add actual stakeholder and partner input as a separately governed, source-linked evidence stream with date, geography, method, reach, consent limits, disagreements, and representation gaps. Do not infer these fields from a mapped site or synthetic household.

Keep source publication, observation, retrieval, and refresh-check dates distinct. Preserve raw inputs, hashes, transformations, rejected-row reports, and evidence states. Do not begin broader acquisition for transit, drones, additional geography, or other features until the selected proposal establishes a need. The [active roadmap](../NEXT_STEPS.md) controls current acquisition priorities; the register below remains a source inventory.

## Evidence states

Current spatial inputs: the browser and bounded food-access traces use a frozen, attributed OpenStreetMap snapshot of downtown Toronto and its walking graph. This is a limited scene and route input, not the complete versioned Toronto GIS world package described above. The connected district also uses the content-hashed illustrative snapshot under `sim/district/data`. Separately, `sim/data` supports a City GIS acquisition and retrieval flow that can create hashed candidate snapshots for supermarket, convenience-store, food-support-program, and education locations, plus a retrieval index and dashboard-ready source metrics. The first City GIS acquisition attempt could not establish outbound connections from this workspace, so a complete City GIS candidate snapshot is not available. These candidate locations do not replace or calibrate the illustrative district.

Each parameter carries one of four states: observed, announced, estimated, or illustrative. Unknown is a missing value with a reason, not a zero. A source can be verified while its input remains unsuitable for calibration because geography, timing, or definition does not match.

Public sources have been located and selected claims checked. This source review, current to 2026-10-17, adds newer releases below; it did not download or integrate economic source files into a candidate snapshot. Partner-held prices, costs, utilization, and behavior still require access. The initial runnable dataset must identify every illustrative substitute.

The initial `sim/data` schema and extraction path cover citywide locations only. Its canonical field map distinguishes named sites, service categories, school institution labels, coordinates, source IDs, and source dates. Source dates remain unknown when the API does not expose them; missing operator identities, prices, inventories, daily capacity, demand served, and school-meal reach remain null. See [`sim/data/README.md`](../sim/data/README.md) for the acquisition and retrieval commands.

## Priority data register

| Priority | Primary source | Required fields | Use and known gap |
| --- | --- | --- | --- |
| P0 | [Toronto 3D massing](https://open.toronto.ca/dataset/3d-massing/) | Building or tile IDs, geometry, height, coordinate system, licence, vintage | Primary 3D context. The portal currently offers 2025 WGS84 shapefile and multipatch resources; pin the selected resource and its content hash. Inspect actual formats and coverage before choosing a renderer or converter. Massing does not establish occupancy or household attributes. |
| P0 | [Toronto Centreline](https://ckan0.cf.opendata.inter.prod-toronto.ca/en/dataset/toronto-centreline-tcl) | Segment IDs, geometry, feature codes, mode eligibility, source vintage | Street foundation. Filter non-traversable features; it is not by itself a sidewalk or pedestrian graph. |
| P0 | Pedestrian links, crossings, barriers, and access | Stable link IDs, geometry, permitted modes, accessibility tags, source and quality flag | Build and validate the walkable graph for the active area. Identify gaps and synthetic links instead of silently routing across them. |
| P0 | [Toronto supermarket layer](https://gis.toronto.ca/arcgis/rest/services/cot_geospatial26/MapServer/4), [TDSB school directory](https://www.tdsb.on.ca/find-your/school) | Place IDs, names, coordinates, type, source date if exposed, retrieval date, status | Anchor the first active area and test feature-to-scene alignment. The live supermarket layer exposes location fields but its service metadata does not establish an observation date; record retrieval time separately and verify current status. Add non-supermarket food services separately. |
| P0 | Coordinate reference and map attribution | CRS, transform, local origin, licence, attribution, feature-ID mapping | Keep scene, route graph, services, and rollout sites spatially aligned and traceable to source records. |
| P1 | [TTC schedules](https://open.toronto.ca/dataset/ttc-routes-and-schedules/) | Stops, trips, stop times, service dates, accessibility | Add transit access where supported. Schedules do not establish observed reliability. Freeze feed validity. |
| P1 | [Census household total-income groups, Table 98-10-0055-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810005501), [after-tax groups, Table 98-10-0056-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810005601), [Toronto Neighbourhood Profiles](https://open.toronto.ca/dataset/neighbourhood-profiles/), [Toronto 2021 Census backgrounder](https://www.toronto.ca/wp-content/uploads/2022/07/9877-City-Planning-2021-Census-Backgrounder-Families-Hhlds-Marital-Status-Income.pdf) | Annual household income groups, household type, size, number of earners, age composition, geography, reference year | Best available detailed City/neighbourhood household baseline found; income generally refers to 2020. Table 98-10-0056's household-characteristic cross-tabs are at Toronto CMA/CMA-part geographies, not neighbourhoods. Use City and neighbourhood controls only at the geography and detail actually published. |
| P1 | [Canadian Income Survey 2024, Table 11-10-0237-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110023701) | 2024-reference-year market, total, and after-tax income statistics by economic-family type and selected CMA; release date | Newest annual Toronto-CMA income comparison found, released 2026-04-29. Use as a freshness/trend check only: its units are economic families and persons not in economic families, and its geography is Toronto CMA, not Toronto City. Do not substitute it for private-household controls. |
| P1 | [T1 Family File 2023, Table 11-10-0013-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110001301) | 2023 census-family total-income groups, family type, number of children, CMA | Additional family-level comparison; not a distribution of all private households. The 2024 reference-year T1FF release is delayed to Winter 2026/27; small-area 2024 and 2025 T1FF+ geography is expected early 2027. |
| P1 | [Household Economic Accounts, Table 36-10-0663-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066301) | Quarterly household income, consumption, saving and quintile distributions; Canada/province/territory; latest reference period | Newest household-level macro trend found is Q4 2025. Use for broad trend context only; geography and broad quintile measures are insufficient for Toronto City population weights. |
| P1 | [Toronto Public Health food security and Ontario Nutritious Food Basket (ONFB)](https://www.toronto.ca/city-government/accountability-operations-customer-service/long-term-vision-plans-and-strategies/poverty-reduction-strategy/food-security-in-toronto-poverty-reduction-strategy/), [Cost of Living in Toronto dataset](https://open.toronto.ca/dataset/cost-of-living-in-toronto-for-low-income-households/) | Annual local food-basket costs; household scenario, basket definition, income and expense components, reference year | The City reports 2026 ONFB cost of $1,242/month for two adults and children aged 8 and 14, and links the full set of household scenarios. Use as a Toronto food-affordability benchmark, not average household spending or a grocery-store price list. Cost-of-living workbooks are constructed scenarios, not population distributions. |
| P1 | [CPI table 18-10-0004-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401), [retail prices 18-10-0245-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810024501) | Geography, product, package size, month, price, currency basis, vintage | As of 2026-10-17, latest available CPI and selected retail-price reference month is August 2026. Use matched geography and product definitions for price trends or dollar adjustments. Retail-price series are not store-level Toronto observations; supplement with dated local store audits. CPI rebasing changes dollar units, not the underlying income distribution or its economic context. |
| P1 | [Second Harvest reports](https://www.secondharvest.ca/about/reports) and school or food-hub operators | Sites, eligible input, rescued versus purchased mass, shifts, yields, menus, uptake, costs | Model service and rollout constraints. Request local operating records; national reports do not establish local daily capacity. |
| P1 | [Who's Hungry 2025](https://www.dailybread.ca/wp-content/uploads/2025/12/DB-WHR-2025-Final_Nov-3_reader.pdf) | Food-bank visits, survey methods, program geography, reporting period | Latest Toronto report found: 4,124,313 visits from 2024-04-01 to 2025-03-31. Use for citywide hardship and demand context. Visit counts are repeated service events, not unique households or site/day-level demand; survey findings describe food-bank clients, not a population-representative sample. Daily unmet requests and supply need partner records. |
| P2 | Consented local behavior or sentiment study | Sampling, question wording, geography, date, consent, response rate | Optional validation stream. Keep observations separate from synthetic agent state and generated dialogue. |
| P2 | [Transport Canada site guidance](https://tc.canada.ca/en/aviation/drone-safety/learn-rules-you-fly-your-drone/where-fly-your-drone) | Constraints, route-assessment references, date | Only needed for a drone delivery scenario. Eligibility checks are not route approvals or an operational airspace feed. |

Weather, energy, vehicle specifications, and emission factors are additional datasets for a drone or environmental study, not prerequisites for the first Toronto pedestrian scene. Use dated authoritative measurements and vehicle-specific tests when available. Otherwise expose downtime and energy as illustrative ranges and suppress unsupported emissions claims.

## Snapshot contract

Each raw or derived dataset records:

```text
dataset_id, publisher, source_url, resource_url
retrieved_at, published_at, reference_period_start, reference_period_end
geography_id, boundary_vintage, statistical_unit, population_universe
income_concept, units, price_base_month
licence_url, attribution, raw_sha256, transform_revision
row_count, missingness, quality_flags, evidence_state
```

Unknown publication dates remain null. Do not use retrieval time as publication time or imply that a live layer's retrieval date is its observation date. Record statistical unit and population universe explicitly (for example, private household, economic family, census family, person, or client visit). Current pages with unverified vintages stay outside a strict historical baseline until an archived or dated resource confirms availability.

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

## Household income evidence and model contract

The first income target is a household's **annual after-tax income group**, with its income reference year and dollar basis attached. This is a general household characteristic. It is not the household's cash balance at a point in the simulation. If a later model needs a numeric annual amount, generate a synthetic amount from the published group using a documented method and mark it as synthetic; do not represent it as observed household microdata.

Statistics Canada's 2021 Census Table 98-10-0056-01 reports household after-tax income groups for private households and supports breakdowns by household type, household size, age composition, and number of earners. Table 98-10-0055-01 provides household total-income groups. The Census income reference period is generally calendar year 2020, with income categories expressed in 2020 constant dollars. These tables provide aggregate counts, not records for individual Toronto households. This remains the best direct household baseline found for Toronto; newer sources do not provide a comparable current-year City household distribution.

The 2021 Census Profile and Toronto Neighbourhood Profiles provide City/neighbourhood income and demographic controls. The City's 2021 backgrounder reports 1,160,890 households and a median total household income of $84,000 in 2020 dollars, as well as differences in household composition across Toronto. It also documents substantial pandemic benefit receipt in 2020. Treat the Census distribution as a dated baseline and label the pandemic-period reference year; CPI adjustment alone does not make it a measured current-year distribution. The City's profiles cover 158 neighbourhood geographies, but only publish certain measures at that level.

Table 98-10-0056-01's joint household-characteristic distributions use Toronto CMA and CMA-part geographies. They must not be described as Toronto City or neighbourhood cross-tabs. For City-level synthesis, use City-level household income groups and compatible City-level household composition margins. For neighbourhood analysis, add neighbourhood controls only where published. If margins do not identify the income-by-household-type relationship at the target geography, mark it as an assumption and evaluate plausible alternatives instead of implying the joint distribution is observed.

Statistics Canada's [2024 Canadian Income Survey Table 11-10-0237-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110023701), released 2026-04-29, is the newest annual Toronto-CMA income comparison found (reference year 2024). Its statistical units are economic families and persons not in economic families, not private households, and its geography is the CMA, not the City. Use it as a freshness or trend check; do not substitute it directly for private-household income records. With the 2024 CIS release, Statistics Canada also revised 2018-2023 estimates using 2021 Census population counts; pin the specific table release and revision in each snapshot.

The [2023 T1 Family File Table 11-10-0013-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110001301) adds annual total-income groups by census-family type and number of children for selected CMAs. It can inform family-specific sensitivity scenarios, but it excludes households not represented by a census family and must retain that unit label. Statistics Canada reports that the T1FF 2024 release is delayed to Winter 2026/27 and that small-area T1FF+ geography for 2024 and 2025 is expected early 2027; treat those as expected releases, not available data.

Statistics Canada's [Household Economic Accounts, Table 36-10-0663-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610066301) provides newer household-level macroeconomic distributions through 2025 Q4, at Canada and provincial/territorial geographies. Use it only as a broad trend comparator: it does not provide Toronto-specific weights or the detailed income groups and household cross-tabs needed for the synthetic population.

Keep income fields and time-varying cash-ledger fields separate in the simulation schema. Do not convert annual income to trip-time cash without a separate, explicit model of income timing, taxes, housing costs, and other commitments. Any support-program eligibility rule must also be explicit; a published income bracket does not automatically define eligibility.

For food affordability, Toronto Public Health reports a [2026 Ontario Nutritious Food Basket cost](https://www.toronto.ca/city-government/accountability-operations-customer-service/long-term-vision-plans-and-strategies/poverty-reduction-strategy/food-security-in-toronto-poverty-reduction-strategy/) of $1,242 per month for two adults and two children aged 8 and 14, with data for additional household scenarios. Treat this as a local healthy-food-basket benchmark, not general household spending, full cost of living, or itemized store prices. The City's cost-of-living scenarios are constructed examples; they are not a sample from which to estimate household income frequencies.

The latest Toronto-specific food-bank context found is [Who's Hungry 2025](https://www.dailybread.ca/wp-content/uploads/2025/12/DB-WHR-2025-Final_Nov-3_reader.pdf), which reports 4,124,313 visits during 2024-04-01 to 2025-03-31. Preserve visits as a service-use measure and its reporting period. Visit counts are repeated service events, not unique households or daily site-level demand; the report's survey findings describe food-bank clients, not a population-representative sample. Use it for citywide context and scenario stress tests, while seeking partner-level aggregate data for capacity and unmet demand.

## RAG-to-simulation pipeline

### Current implementation boundary

`sim/data` currently acquires civic location layers and builds a BM25-style lexical retrieval index over source notes and location records. It has no household-income dataset or configured LLM generation provider. Income retrieval and the income-to-simulation transformation below are planned additions, not implemented behavior. See [`sim/data/README.md`](../sim/data/README.md).

### Target flow

```mermaid
flowchart LR
  A[Official tables and source documentation] --> B[Acquire raw files and metadata]
  B --> C[Immutable, hashed source snapshot]
  C --> D[Normalize into typed statistical records]
  D --> E[Quality checks and source totals]
  D --> F[Structured numeric retrieval]
  D --> G[Search index for definitions and source notes]
  F --> H[Retrieved evidence with source and geography]
  G --> H
  H --> I[Agent response with citations]
  E --> J[Deterministic population-input builder]
  J --> K[Candidate simulation snapshot]
  K --> L[Review and validation]
  L --> M[Versioned snapshot selected by simulation run]
```

Use structured, dimension-filtered queries for numeric statistics (for example: geography, income concept, household type, household size, income group, and reference year). Use lexical or semantic retrieval for definitions, methodology, limitations, and source context. The agent can explain retrieved evidence and cite it; it must not invent aggregate values or silently write generated answers into the active simulation.

The deterministic population-input builder converts validated aggregate records into a candidate distribution or synthetic population. Its output retains the source dataset ID, extraction time, income concept, income reference year, currency base year, geography, household universe, income-group labels/counts, transformation revision, random seed, weights, and fitting diagnostics. Preserve source counts and the normalized table separately from derived household records.

Each candidate must pass checks before selection: source totals reconcile under the source's documented rounding rules; group labels, units, geography, and reference years are consistent; rounding, suppression, and missing cells are surfaced; derived proportions reproduce the selected controls within a documented tolerance; and seeded generation is reproducible. Publishing a new snapshot creates a new dataset/version and new simulation runs. Existing runs keep their original snapshot and provenance.

This pipeline can be developed alongside the agent layer. Define the snapshot and retrieval contract first so the agent can query a stable candidate dataset while the deterministic population builder is implemented and validated.

## Synthetic population

Create synthetic households and resident pedestrians that match available aggregate controls across household size, age bands, annual household income groups, tenure, and area. Attach homes and initial positions to eligible residential areas or clearly synthetic buildings. Give each simulated person a synthetic ID and only the schedule and attributes needed for the modeled activity. Use a documented fitting method such as iterative proportional fitting once compatible controls and seed distributions are obtained. Retain the source snapshot ID, seed, weights, convergence diagnostics, and residuals.

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

For an operational research workflow, refresh CPI and selected retail-price series monthly, Toronto ONFB and food-insecurity reports when their annual releases appear, household income sources when their stated annual releases appear, TTC schedules by service period if transit is in scope, school provision by term and delivery day, and City location layers when refreshed. The 2025 Toronto 3D massing resources should be treated as a fixed source vintage until a newer resource is verified. Keep the source reference period, publication date, actual retrieval date, and—where available—observation date distinct. Keep both planned and actual dates for partner data.

A dashboard can show new source releases, stale inputs, quality failures, and baseline drift. Recalibration creates a new model version and keeps old comparisons reproducible. This document describes the future tracking system. No recurring automation has been scheduled.
