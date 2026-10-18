# Toronto civic-data retrieval

This package provides a first acquisition and retrieval slice for the food-shortage simulation. It uses the City of Toronto ArcGIS feature services directly; it does not scrape rendered HTML pages.

## First datasets

`sources.json` registers four citywide point layers: full-service supermarkets, convenience stores, food-support program sites, and education locations. `dataset_schema.json` defines the canonical location fields and their units. Every normalized record keeps the source ID, source record ID, coordinates, retrieval time, evidence state, and source URL.

The current fields support candidate variables for the count and geographic distribution of these site types, plus school-site counts by reported institution label and service category. These are potential environment inputs after the active simulation area is defined and the source vintage is reviewed. They do not yet provide firm counts, household market demand, grocery operator identity, capacity, inventories, shelf prices, food-bank throughput, or school meal reach. Those values remain `null` with a reason in `dashboard.json`.

## Acquire a candidate snapshot

From the repository root, run:

```powershell
python -m sim.data ingest
```

This creates a new, timestamped folder under `outputs/toronto-data/`. To retrieve a subset or choose a new output location:

```powershell
python -m sim.data ingest --source toronto_supermarkets --source toronto_food_support_sites --out outputs/toronto-data/candidate-review
```

The pipeline pins each raw ArcGIS metadata/query response by SHA-256, pages through up to the layer's advertised record limit, validates the declared field mappings, and writes normalized JSONL, rejected rows, a provenance manifest, `quality_report.json`, `simulation_inputs.json`, and `dashboard.json`. It does not change the frozen illustrative district snapshot.

## Retrieve cited context

```powershell
python -m sim.data retrieve "food assistance program locations" --snapshot outputs/toronto-data/candidate-<UTC timestamp> --top-k 8
```

The retriever ranks source notes and retrieved location records using a dependency-free BM25-style lexical score. It returns the source URL and the record or dataset metadata as context. This is the retrieval half of RAG; no LLM generation provider is configured, and returned context must not directly mutate simulation state.

Retrieval requires a complete snapshot and verifies the `documents.jsonl` hash before ranking. To restrict results to one layer:

```powershell
python -m sim.data retrieve "full-service grocery downtown" --snapshot outputs/toronto-data/candidate-<UTC timestamp> --dataset-id toronto_supermarkets --top-k 8
```

For a known row, add `--record-id <source row id>` to restrict the context to that source record.

## Use listed locations in the pedestrian simulation

The current browser simulation has a downtown Toronto map and walking graph. Prepare a separate, immutable location snapshot from a complete City GIS candidate:

```powershell
python -m sim.data prepare-sites --snapshot outputs/toronto-data/candidate-<UTC timestamp>
```

This clips source-listed supermarket, food-support, and school records to the map bounds, then selects the nearest unique record to each frozen illustrative site anchor. It runs the RAG retriever for each selected record and pins its cited result, source row, retrieval time, source manifest hash, map hash, and coordinate transform. The current derived snapshot is `sim/data/snapshots/toronto-downtown-sites-v3.json`.

`python -m sim.interactables` and the web app's trace generator use this pinned location snapshot by default. The source records provide location and labels only. Current operating status, prices, inventory, hours, capacity, eligibility, and behavior remain illustrative. To create a separate trace set with the original synthetic site anchors, use `python -m sim.interactables --illustrative-sites-only --out outputs/illustrative-only`.

## Scope and evidence limits

- The first extract is citywide; it is not clipped or assigned to the downtown visual area or any chosen neighbourhood.
- Source publication/reference dates remain null unless the source API supplies them. An ArcGIS layer edit date is recorded separately when available.
- Layer license terms are flagged for review before publication; the registry links the City's open-data license for that check.
- City counts describe records in the retrieved layer snapshot, not guaranteed active businesses or delivered service capacity.
- The education layer includes universities, colleges, private schools, and adult learning locations. Filter its type codes before estimating K-12 or meal-program reach.
- A count of mapped retail sites is not a count of unique grocery firms, market share, or stock. Obtain business/operator, price, inventory, and sales records from suitable sources or local audits before making those claims.
