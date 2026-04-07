# CDEC Integration - Future Work

## Current State

CDEC integration is live and deployed as of 2026-04-06. The core data pipeline, scoring, and pet safety advisory are complete.

**Spec:** `docs/superpowers/specs/2026-04-06-cdec-integration-design.md`
**Plan:** `docs/superpowers/plans/2026-04-06-cdec-integration.md`

### What's Deployed
- CDEC service module (`api/src/services/cdec.ts`) - 7 fetch functions + historical stage + baseline computation
- Scoring: reservoir level, water quality composite, pet safety, dam release veto, river stage (percentile-based)
- Conditions service merges USGS + CDEC + NOAA with source tracking
- River stage baselines for AFO and CBR (migration 0008, 24 rows)
- Water data displays: reservoir gauges, river stage gauge, pet safety badges, water quality tiles, streamflow chart
- 24h flow history from USGS instantaneous values endpoint
- `reservoirCapacityAf` loaded from DB, `stageContext` in API response
- Three CA water bodies configured: Folsom Lake (FOL), Lake Natoma (NAT+AFO), South Fork American River (CBR+AFO)
- Website docs updated for all CDEC features

## Phases

- [x] Core CDEC service module + tests
- [x] Schema migration + deploy
- [x] Scoring factors (reservoir level, water quality, pet safety, dam release)
- [x] Conditions service integration + API response
- [x] Production deploy + station association
- [x] Station discovery API
- [x] River stage scoring
- [ ] DWR water quality station mapping
- [x] Website docs for CDEC features

## Tasks

### Station Discovery API
- [x] Build service to search CDEC stations by lat/lng, river basin, county
- [x] Return candidate stations with available sensors and distance
- [x] Auto-populate `dataTypes` based on sensor availability probing (description-first matching)
- Note: No user-facing endpoint. Claude Code uses service functions directly when associating stations.

### River Stage Scoring
- [x] Fetch historical stage data from CDEC (event data, aggregated to daily averages)
- [x] Compute per-station monthly percentile baselines (p10/p25/p50/p75/p90/p95)
- [x] Add `scoreRiverStage` function using `linearScore`/`linearScoreInverted` with percentile thresholds
- [x] Profile-dependent: recreational uses normal direction (low=good), racing uses inverted (high=good)
- [x] Universal flood veto at p95 for all profiles
- [x] Baselines populated for AFO and CBR (24 rows)

### DWR Water Quality Station Mapping
- [ ] Identify DWR continuous monitoring stations near target water bodies
- [ ] Most WQ stations are in Sacramento-San Joaquin Delta
- [ ] Target stations (FOL, NAT, AFO) lack WQ sensors - need separate nearby WQ stations
- [ ] Associate WQ stations as additional `water_body_stations` entries

### Additional Water Bodies
- [ ] Add Lake Oroville (ORO) to catalog with capacity 3,537,577 AF
- [ ] Add reservoirCapacityAf for other CA reservoirs as they're cataloged
- [ ] Set damOutflowThreshold per water body for dam release veto scoring

### User Data Source Submissions
- [ ] Design a way for users to suggest data sources or corrections (e.g., "this lake has a water quality station you're not using")
- [ ] Could be a simple form on the website footer or a feedback link on the location detail page
- [ ] Consider: email form, GitHub issue template, or in-app feedback button
- [ ] Document the process in the website footer or docs

### Website Docs
- [x] Add CDEC data source to location-detail, caching, adding-locations pages
- [x] Document all scoring factors (river stage, reservoir level, water quality) on scores-and-ratings page
- [x] Document pet safety advisory and expanded veto list
- [x] Document activity profile differences for river stage direction

## Lore

- CDEC sensor numbers are NOT globally consistent. Sensor 71 means "dissolved oxygen" in the official list but "discharge, spillway" at dam stations (NAT, FOL). Always verify per-station.
- Correct sensor numbers: DO=61, pH=62, Conductivity=100 (the spec initially had these wrong)
- Water quality sensors (turbidity, DO, pH, conductivity) are rare at river/reservoir stations. They're primarily at specialized DWR monitoring stations in the Delta.
- Wind/air temp sensors are at CDEC weather stations, not most water stations. AFO and FOL don't have them.
- CDEC staMeta endpoint returns HTML, not JSON. Sensor availability must be probed by scraping `staMeta?station_id=X`.
- CDEC staSearch also returns HTML. The station table is a DataTable with `id="station_table"`, rendered client-side.
- CDEC timestamps are Pacific Standard Time, non-ISO format like `"2026-4-5 14:15"` (no zero-padding). Must parse carefully.
- CDEC staSearch requires `_chk=on` activator params for each filter. Without it, the filter is ignored.
- Station ID cells in staSearch contain `<a>` links. HTML parsing must strip nested tags.
- staMeta sensor table must be found by "Sensor Description" header text, not positional index.
- FLOW regex needs word boundaries (`\bFLOW\b`) to avoid matching "FLOW" within "INFLOW".
- Reservoir INFLOW/OUTFLOW/RELEASE descriptions must not map to `flow` dataType.
- Production SSH uses key `~/.ssh/paddleconditions_prod` (not password), port 11208.
- Deploy is rsync of built `dist/` to `~/public_html/api.paddleconditions.com/dist/` + touch `tmp/restart.txt`.
- 3 pre-existing test failures in jobs-integration and purge-soft-deletes tests (not related to CDEC work). UPDATE: these may be resolved now (488 tests all passing as of 2026-04-07).
- App deploy is rsync of built `dist/` to `~/public_html/app.paddleconditions.com/` (no restart needed, static files).
- Water body conditions cache must be flushed after API changes that add new fields to the response. Set `next_fetch_at` to past date for affected rows.
- `reservoirCapacityAf` was a TODO null in conditions.ts line 577 until this session. Now loaded from `waterBodies` table via `WaterBodyCacheService.getReservoirCapacity()`.
- USGS instantaneous values endpoint supports `period=PT24H` for historical data. Returns 15-min readings, downsample to hourly for charts.
- CDEC `dur_code=D` (daily) returns empty for river stage at AFO and CBR. Must use `dur_code=E` (event/15min) and aggregate to daily averages.
- CDEC uses `-9999` as a sentinel value for missing data that is NOT always flagged with bad data flags (N, v). Filter by `value > -100`.
- CBR station has periods of sentinel values mixed with valid data, especially in 2021-2022. The p10 percentile was corrupted before adding the sentinel filter.

## Session Notes -- 2026-04-07

### Completed This Session
- **River stage scoring**: spec, plan, 8-task implementation, code review, deploy. 30 new tests (488 total). Specs at `docs/superpowers/specs/2026-04-06-river-stage-scoring-design.md`
- **Water data displays**: spec, plan, 7-task implementation, deploy. New frontend components: WaterConditionsTiles (reservoir gauges, river stage gauge, pet safety badges), WaterQualityRow (threshold-colored metrics), StreamflowChart (24h Recharts area chart with bands)
- **API enhancements**: `reservoirCapacityAf` loaded from DB, `stageContext` with percentile context, `flowHistory` from USGS 24h instantaneous values
- **Website docs**: 4 pages updated with CDEC features (scores-and-ratings, location-detail, caching, adding-locations)
- **N/A tiles**: Pet safety and water quality show "No data source" when sensors unavailable

### All Specs/Plans Created
- `docs/superpowers/specs/2026-04-06-river-stage-scoring-design.md`
- `docs/superpowers/plans/2026-04-06-river-stage-scoring.md`
- `docs/superpowers/specs/2026-04-06-water-data-displays-design.md`
- `docs/superpowers/plans/2026-04-06-water-data-displays.md`

### Next Steps
- **DWR water quality station mapping**: find WQ monitoring stations near FOL/NAT/AFO (mostly in Delta)
- **Additional water bodies**: use `findNearbyStations()` + `getStationSensors()` to set up Oroville and other CA lakes
- **User data source submissions**: design a feedback mechanism for users to suggest stations/corrections
- Delete the `cdec-integration` branch (already merged)
