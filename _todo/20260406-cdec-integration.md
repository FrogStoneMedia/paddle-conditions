# CDEC Integration - Future Work

## Current State

CDEC integration is live and deployed as of 2026-04-06. The core data pipeline, scoring, and pet safety advisory are complete.

**Spec:** `docs/superpowers/specs/2026-04-06-cdec-integration-design.md`
**Plan:** `docs/superpowers/plans/2026-04-06-cdec-integration.md`

### What's Deployed
- CDEC service module (`api/src/services/cdec.ts`) - 7 fetch functions, 17 tests
- Scoring: reservoir level, water quality composite, pet safety, dam release veto
- Conditions service merges USGS + CDEC + NOAA with source tracking
- DB migration applied to test and production
- Three CA water bodies configured: Folsom Lake (FOL), Lake Natoma (NAT+AFO), South Fork American River (CBR+AFO)
- Changelog updated in website repo

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
- 3 pre-existing test failures in jobs-integration and purge-soft-deletes tests (not related to CDEC work).
- CDEC `dur_code=D` (daily) returns empty for river stage at AFO and CBR. Must use `dur_code=E` (event/15min) and aggregate to daily averages.
- CDEC uses `-9999` as a sentinel value for missing data that is NOT always flagged with bad data flags (N, v). Filter by `value > -100`.
- CBR station has periods of sentinel values mixed with valid data, especially in 2021-2022. The p10 percentile was corrupted before adding the sentinel filter.

## Session Notes -- 2026-04-06

### Completed
- Full CDEC integration: spec, plan, implementation (11 tasks), review, deploy
- Station Discovery Service: 4 functions, 28 tests, 817 lines across 2 files
- Spec: `docs/superpowers/specs/2026-04-06-cdec-station-discovery-design.md`
- Plan: `docs/superpowers/plans/2026-04-06-cdec-station-discovery.md`

### Session 2 - River Stage Scoring
- Design spec: `docs/superpowers/specs/2026-04-06-river-stage-scoring-design.md`
- Plan: `docs/superpowers/plans/2026-04-06-river-stage-scoring.md`
- `scoreRiverStage` function with percentile-based scoring (17 unit tests)
- Veto at p95 + factor in `computePaddleScore` (7 integration tests)
- `fetchCdecHistoricalStage` with event-to-daily aggregation + `computeStageBaseline` (6 service tests)
- Baselines populated for AFO (6.0-13.9 ft range) and CBR (1.2-8.6 ft range)
- Migration 0008 applied, deployed to production
- Fixed: cached path missing stageBaseline, varchar(3) too short, sentinel values, month cache key

### Next Steps
- **Website docs**: document CDEC data source, water quality scoring, pet safety advisory, river stage scoring
- **Additional water bodies**: use `findNearbyStations()` + `getStationSensors()` to set up new CA lakes
- Delete the `cdec-integration` branch (already merged)
