# CDEC (California Data Exchange Center) Integration

## Overview

Add CDEC as a new water data provider for California water bodies, running alongside existing USGS and NOAA sources. CDEC provides richer California-specific data including reservoir metrics, water quality, river stage, dam releases, and wind/air temp from ~1,500+ stations across the state. This integration also introduces water quality scoring, pet safety advisories, and new scoring factors for reservoir conditions and dam releases.

## CDEC API

- **Base URL:** `https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet`
- **Auth:** None required (public API)
- **Format:** JSON, CSV, or Excel
- **Parameters:**
  - `Stations`: Comma-delimited 3-letter station IDs (e.g., `FOL,NAT,AFO`)
  - `SensorNums`: Comma-delimited sensor numbers
  - `dur_code`: `E` (event/15min), `H` (hourly), `D` (daily), `M` (monthly)
  - `Start`, `End`: Date range (format: `YYYY-MM-DD`)
- **Response structure:**
  ```json
  [
    {
      "stationId": "AFO",
      "durCode": "E",
      "SENSOR_NUM": 25,
      "sensorType": "TEMP W",
      "date": "2026-4-5 14:15",
      "obsDate": "2026-4-5 14:15",
      "value": 55.2,
      "dataFlag": " ",
      "units": "DEG F"
    }
  ]
  ```
- **Data flags to skip:** `N` (error in data), `v` (out of valid range)
- **Rate limiting:** No documented limits, but stagger calls (existing 6s delay in refresh job applies)

## Sensors

| Sensor | Number | Duration | Units | Purpose |
|--------|--------|----------|-------|---------|
| Water Temp | 25 | E (15min) | DEG F | Core paddling metric |
| Flow | 20 | E | CFS | Streamflow |
| River Stage | 1 | E | FEET | Water level at gauge |
| Reservoir Storage | 15 | H (hourly) | AF | Reservoir volume |
| Reservoir Elevation | 6 | H | FEET | Water surface elevation |
| Inflow | 76 | H | CFS | Reservoir inflow |
| Outflow | 23 | H | CFS | Reservoir outflow |
| Scheduled Release | 7 | E (event) | CFS | Planned dam releases |
| Discharge/Regulating | 85 | H | CFS | Controlled release |
| Wind Speed | 9 | E | MPH | Supplements weather |
| Wind Direction | 10 | E | DEG | Supplements weather |
| Air Temp | 4 or 30 | E | DEG F | Supplements weather |
| Turbidity | 27 | E | NTU | Water clarity |
| Dissolved Oxygen | 61 | E | MG/L | Water quality |
| pH | 62 | E | PH | Water chemistry |
| Electrical Conductivity | 100 | E | US/CM | Salinity proxy |
| Wind, Peak Gust | 77 | E | MPH | Supplements weather |

## Architecture: Peer Provider Pattern

CDEC joins as a peer data source alongside USGS and NOAA, following the existing service module pattern. No abstraction layer. Each source is a standalone module; the conditions service orchestrates.

This pattern scales to future state water data sources (e.g., Oregon OWRD, Colorado DWR, Texas TWDB) by adding new modules and `stationType` values in `water_body_stations`.

```
Conditions Service (orchestrator)
  |-- NWS + Open-Meteo  --> weather
  |-- USGS              --> water temp, streamflow
  |-- NOAA CO-OPS       --> tides, coastal temp
  |-- CDEC (NEW)        --> water temp, flow, stage, reservoir, water quality, wind, air temp
  |-- Open-Meteo AQI    --> air quality
```

## New Service Module: `api/src/services/cdec.ts`

Follows the same pattern as `usgs.ts` and `noaa.ts`. Exports pure functions, handles its own HTTP requests, error handling, unit conversions, and parsing.

### Functions

- `fetchCdecWaterTemp(stationId: string): Promise<number | null>` - Sensor 25, duration E. Latest water temp in F.
- `fetchCdecFlow(stationId: string): Promise<number | null>` - Sensor 20. Latest flow in CFS.
- `fetchCdecRiverStage(stationId: string): Promise<number | null>` - Sensor 1. Latest stage in feet.
- `fetchCdecReservoirData(stationId: string): Promise<ReservoirData | null>` - Sensors 15, 6, 76, 23, 7, 85. Combined reservoir metrics.
- `fetchCdecWind(stationId: string): Promise<{speed?: number, direction?: number} | null>` - Sensors 9, 10.
- `fetchCdecAirTemp(stationId: string): Promise<number | null>` - Sensor 4 or 30.
- `fetchCdecWaterQuality(stationId: string): Promise<WaterQualityData | null>` - Sensors 27, 61, 62, 100.
- `fetchCdecStationMeta(stationId: string): Promise<StationMeta | null>` - Station metadata. The `staMeta` endpoint returns HTML (not JSON), so sensor availability is determined by probing the JSON data endpoint for each sensor group and checking for non-empty responses. Results cached indefinitely (station sensor inventory is static).

### Implementation Details

- Query last 2 hours of event data, take most recent non-null value with valid data flag
- Batch sensor requests where possible (multiple SensorNums in one call)
- In-memory TTL cache: 15 min for water/weather, 24 hours for station metadata
- Cache key format: `cdec:{stationId}:{sensorGroup}` (e.g., `cdec:FOL:reservoir`)
- Graceful degradation: return null for any sensor that fails or has no data
- **Timestamp handling:** CDEC returns timestamps in Pacific Standard Time with format `"YYYY-M-D H:MM"` (no timezone, no ISO format, no zero-padding). Parse and normalize to UTC before comparing with USGS timestamps (which are UTC).
- **Sensor availability detection:** Not all stations have all sensors. On first fetch for a station, probe each sensor group and cache which ones return data. Skip unavailable sensors on subsequent fetches.

### Return Types

```typescript
type CdecData = {
  waterTempF?: number
  flowCfs?: number
  riverStageFt?: number
  reservoir?: ReservoirData
  windSpeedMph?: number
  windDirectionDeg?: number
  airTempF?: number
  waterQuality?: WaterQualityData
}

type ReservoirData = {
  storageAf?: number
  elevationFt?: number
  inflowCfs?: number
  outflowCfs?: number
  scheduledReleaseCfs?: number
  regulatingReleaseCfs?: number
}

type WaterQualityData = {
  turbidityNtu?: number
  dissolvedOxygenMgL?: number
  ph?: number
  conductivityUs?: number
}
```

## Schema Changes

### `water_bodies` table

Add columns:
- `cdecStationId` (varchar, nullable) - Direct CDEC station ID lookup, alongside existing `usgsStationId` and `noaaStationId`
- `reservoirCapacityAf` (float, nullable) - Maximum reservoir capacity in acre-feet. Required for reservoir level scoring. Populated from CDEC reservoir info or manually.

### `water_body_stations` table

Add `'cdec'` to the `stationType` enum (currently `['usgs', 'noaa']`). This requires a Drizzle migration to alter the enum. The existing `dataTypes` JSON column stores available sensor groups (e.g., `["waterTemp", "flow", "reservoir", "waterQuality"]`). The `dataTypes` array is populated during station setup based on sensor availability detection.

### `locations` config

Extend `dataSources` in `SpotConfig`:
```typescript
dataSources?: {
  usgs: string[]    // existing
  noaa: string[]    // existing
  cdec: string[]    // NEW - CDEC station IDs per spot
}
```

### `water_body_conditions.water` JSON

Extend cached water data:
```typescript
water: {
  // existing
  waterTempF?: number
  streamflowCfs?: number
  // new from CDEC
  riverStageFt?: number
  reservoir?: ReservoirData
  waterQuality?: WaterQualityData
  // source tracking
  sources?: Record<string, 'usgs' | 'cdec' | 'noaa'>
}
```

## Station Discovery

Semi-automatic approach for associating CDEC stations with water bodies:

1. When adding a CA water body, query CDEC station search by lat/lng proximity and river basin
2. Return candidate stations with their available sensors and distance
3. Admin or user picks which station(s) to associate
4. For large water bodies (e.g., Folsom Lake), different spots can reference different CDEC stations via `dataSources` config in `SpotConfig`

Station search uses the CDEC station search endpoint, filterable by sensor type, river basin, hydrologic area, county, and geographic coordinates.

## Data Merging Strategy

When a CA water body has both USGS and CDEC stations:

1. **Parallel fetch** - USGS, NOAA, and CDEC requests fire concurrently
2. **Freshest wins** - For overlapping metrics (water temp, flow), use whichever source returned a more recent observation. Track source in the response.
3. **CDEC-exclusive pass-through** - Reservoir data, water quality, river stage, scheduled releases are CDEC-only. No merge needed.
4. **Wind/air temp as fallback** - CDEC wind and air temp used only if NWS/Open-Meteo didn't return data (true fallback, not merge). Note: wind/air temp sensors are only available at CDEC weather stations, not at most water monitoring stations. This fallback only activates if the water body has an associated CDEC station with these sensors.

## Sensor Availability Note

Not all CDEC stations have all sensors. In particular:

- **Water quality sensors** (turbidity, DO, pH, conductivity) are rare at river gauge and reservoir stations. They are primarily available at specialized DWR water quality monitoring stations, mostly in the Sacramento-San Joaquin Delta. The six target stations (FOL, NAT, AFO, CBR, HST, ORO) do not have water quality sensors.
- **Wind sensors** (speed, direction, gusts) are not available at most water monitoring stations. They are available at weather stations, which are separate from river/reservoir gauges.
- **Air temp** is available at some but not all water stations.

The CDEC service must detect sensor availability per station (see Implementation Details) and only fetch sensors that are known to return data. Water quality and pet safety features are "when available" -- they activate when a water body is associated with a CDEC station that has WQ sensors, but most initial water bodies will not have this data.

To surface water quality data for target water bodies, the station discovery process should also search for nearby DWR water quality monitoring stations in addition to the primary flow/level gauge station.

## New Scoring Factors

### 1. Reservoir Level

For reservoir water bodies, score based on current storage relative to capacity.

**Capacity data source:** Add `reservoirCapacityAf` column (float, nullable) to the `water_bodies` table. Populate from CDEC's reservoir info endpoint (`reportapp/javareports?name=ResInfo`) or manually for key reservoirs:
- Folsom Lake: 977,000 AF
- Lake Natoma: 8,760 AF
- Lake Oroville: 3,537,577 AF

| Range | Rating | Rationale |
|-------|--------|-----------|
| 60-100% capacity | Ideal | Good launch access, normal conditions |
| 30-60% capacity | Marginal | Some ramps may be unusable, exposed hazards |
| <20% capacity | No-go | Launch ramps unusable, navigation hazards |

Profile-dependent: kayakers tolerate lower levels better than SUP. Requires `reservoirCapacityAf` to be set on the water body; if null, this factor is skipped.

### 2. Dam Release / Outflow

High dam releases create dangerous conditions downstream. Safety-critical factor.

- **Hard veto potential:** If outflow exceeds safe threshold for the downstream river segment, trigger NO_GO with reason "High dam release"
- **Per-water-body thresholds:** Every dam/river is different. Store safe thresholds in water body metadata. Start with conservative defaults.
- **Scheduled release awareness:** If a scheduled release is planned during the paddle window, factor it into the forecast blocks

### 3. Water Quality Composite

Combine turbidity, DO, pH, and conductivity into a water quality score.

| Metric | Ideal | Marginal | No-go |
|--------|-------|----------|-------|
| Turbidity | <10 NTU | 10-50 NTU | >100 NTU |
| Dissolved Oxygen | >6 mg/L | 4-6 mg/L | <4 mg/L |
| pH | 6.5-8.5 | 6.0-6.5 or 8.5-9.0 | <6.0 or >9.0 |
| Conductivity | <1000 uS/cm | 1000-2000 uS/cm | >2000 uS/cm |

Hard veto: Algal bloom conditions (water temp >75F + DO <4 mg/L + turbidity >50 NTU).

### 4. River Stage

Alternative to streamflow for rivers where stage is measured but flow isn't rated.

- Requires per-station calibration: "normal" stage varies by river
- Use station's historical range to normalize
- High stage = fast water = caution for recreational, preferred for racing

All new factors use the existing scoring framework: linear interpolation curves with ideal/marginal/no-go thresholds, per-profile weights, and hard vetoes.

## Pet Safety Advisory

Explicit pet safety rating when water quality data is available. Shows prominently in the app.

### Data Structure

```typescript
petSafety?: {
  rating: 'SAFE' | 'CAUTION' | 'UNSAFE'
  reasons: string[]
}
```

### Rating Criteria

**UNSAFE:**
- Water temp >75F + DO <4 mg/L (strong algal bloom indicator)
- Turbidity >100 NTU
- pH outside 5.0-9.5

**CAUTION:**
- Water temp >68F + DO <6 mg/L (early bloom conditions)
- Turbidity 50-100 NTU
- pH outside 6.0-9.0
- Conductivity >2000 uS/cm

**SAFE:** All metrics within normal ranges

When insufficient data is available, the rating is omitted (not shown) rather than defaulting to SAFE. Since water quality sensors are only available at specialized DWR monitoring stations (not at most river/reservoir gauges), pet safety will initially be unavailable for most water bodies until nearby WQ stations are identified and associated.

### Profile Integration

New profile toggle: `paddlesWithPets: boolean`

When enabled:
- `UNSAFE` pet safety triggers a hard veto (NO_GO with reason "Unsafe water quality for pets")
- `CAUTION` pet safety adds negative weight to composite score (similar to high AQI)
- Pet safety data is always included in the response when available, but only affects scoring when the profile toggle is on

## Caching

Uses the existing two-tier cache unchanged:

- **In-memory TTL cache:** 15 min for water/weather data, 24 hours for station metadata
- **Database cache (`water_body_conditions`):** CDEC data stored in the `water` JSON column alongside USGS/NOAA data
- **Background refresh job:** Fetches CDEC data as part of the regular refresh cycle. No extra API calls on user requests.
- **Refresh strategy:** Same tiered frequency based on user count (6h/12h/24h)

## Testing

### Unit Tests (`api/tests/services/cdec.test.ts`)

- Parse CDEC JSON responses for each sensor type
- Handle data flags (skip `N`, `v`; accept blank, `e`, `r`)
- Handle empty arrays (no data available)
- Handle malformed responses and timeouts
- Unit conversion verification
- Cache key generation and TTL behavior

### Merge Logic Tests

- USGS + CDEC overlap: verify freshest-wins for water temp and flow
- CDEC-only data: verify reservoir, water quality, stage pass through
- Wind/air temp fallback: verify only used when weather sources fail
- Source tracking: verify correct source attribution

### Scoring Tests

- Reservoir level scoring with profile variation
- Dam release veto at threshold
- Water quality composite calculation
- Pet safety rating derivation from water quality metrics
- Profile toggle: `paddlesWithPets` affects scoring

### Integration Tests

- End-to-end conditions fetch for CA water body with CDEC station
- Verify cached data includes CDEC metrics
- Verify bulk endpoint includes CDEC data

### Test Fixtures

Capture real CDEC API responses for test fixtures:
- AFO (American River at Fair Oaks) - river station with water temp, flow
- FOL (Folsom Lake) - reservoir with full sensor suite
- NAT (Lake Natoma / Nimbus Dam) - reservoir + downstream river data

## Key Stations for Initial Rollout

| Station ID | Name | Type | Key Sensors |
|-----------|------|------|-------------|
| FOL | Folsom Lake | Reservoir | Storage, elevation, inflow, outflow, water temp |
| NAT | Lake Natoma / Nimbus Dam | Reservoir | Storage, elevation, release, water temp |
| AFO | American River at Fair Oaks | River | Water temp, flow, stage |
| CBR | American River at Chili Bar | River | Water temp, flow, stage |
| HST | American River at H Street | River | Stage (not rated for flow) |
| ORO | Oroville Dam | Reservoir | Full reservoir suite |

## Future Considerations

- **Other state water data sources:** Oregon OWRD, Colorado DWR, Texas TWDB can follow the same peer provider pattern. Add a new service module + `stationType` per source.
- **Algal bloom advisories:** Integrate state/county algal bloom advisory feeds for authoritative warnings beyond sensor-derived estimates.
- **Historical baselines:** Use CDEC's daily/monthly data to establish seasonal baselines for river stage normalization.
- **DWR water quality station mapping:** Systematically identify DWR continuous monitoring stations near popular paddle water bodies to enable water quality scoring and pet safety for more locations.
