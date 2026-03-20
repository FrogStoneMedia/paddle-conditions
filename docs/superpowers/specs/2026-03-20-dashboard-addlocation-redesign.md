# Dashboard & Add Location Redesign

## Summary

Redesign the dashboard location cards and Add Location configure screen to be visually richer, more informative, and support multiple monitoring stations per water body.

Three connected changes:
1. **Dashboard cards** - gradient cards with score glow, inline conditions, and progressive-loading forecast blocks
2. **Add Location configure screen** - preview card, toggle selectors, data availability list with icons, toggleable monitoring stations
3. **Multi-station backend** - junction table for multiple stations per water body, updated import script, enriched search API response

## 1. Dashboard Location Cards

### Current
Flat card with left border accent, text-only conditions (wind, temp, UV), no forecast data.

### New Design

**Theme:** All colors use CSS variables (`var(--color-card)`, `var(--color-border)`, `var(--color-text)`, etc.) to support both light and dark modes. The mockups below describe the dark-mode appearance; light mode uses the same layout with the corresponding light CSS variable values. No hardcoded colors.

- Card background: `var(--color-card)` with subtle gradient using `var(--color-bg)` as second stop, `1px solid var(--color-border)`, `border-radius: 12px`
- Location name (18px bold, `var(--color-text)`) and subtitle (12px, `var(--color-text-muted)`) top-left
- Score circle (56px) top-right with colored glow shadow (`box-shadow: 0 0 16px` at 40% opacity) using GO/CAUTION/NO_GO colors
- Inline condition stats row below name: Wind, Air, Water Temp, UV - each with uppercase 10px `var(--color-text-muted)` label and 13px bold `var(--color-text)` value
- Mini forecast blocks at bottom, separated by `1px solid var(--color-border)` top border:
  - 5 time slots: 6-9a, 9-12p, 12-3p, 3-6p, 6-9p
  - Each block: `flex: 1`, `border-radius: 6px`, background tinted with rating color at 15% opacity
  - Time label (10px `var(--color-text-muted)`) above score (13px bold, colored by rating)

### Progressive Loading
- Cards render immediately from bulk endpoint data (name, score, conditions)
- After mount, fire individual forecast requests per location in parallel
- Forecast blocks fade in when data arrives (CSS transition)
- Show subtle skeleton/shimmer in forecast area while loading
- **Rate limit note:** Forecast endpoint is rate-limited to 30/min. With N locations, dashboard fires N requests on load. For users with many locations (10+), stagger requests with a small delay (100ms between each) to avoid burst. This is acceptable for v1; a future optimization could add forecast blocks to the bulk endpoint.

### Files Changed
- `app/src/components/LocationCard.tsx` - complete visual overhaul
- `app/src/pages/DashboardPage.tsx` - add per-location forecast fetching using existing `useForecast` hook (already exists at `app/src/hooks/useForecast.ts`)

## 2. Add Location Configure Screen

### Current
Plain form with dropdowns, flat "Available Data" checklist with checkmark/dash icons.

### New Layout (top to bottom)

**Preview Card**
- Gradient card matching dashboard style
- Shows water body name, type, location
- "Verified" pill badge (sky blue) for curated entries

**Activity Selector**
- Toggle buttons instead of dropdown: SUP | Kayaking
- Selected state: `background: rgba(14, 165, 233, 0.15)`, `border: 1px solid var(--color-water)`, `color: var(--color-water)`
- Unselected: `background: var(--color-bg-secondary)`, `border: 1px solid var(--color-border)`, `color: var(--color-text-muted)`

**Profile Selector**
- Same toggle button pattern
- Options change based on activity (SUP: Recreational/Racing/Family, Kayaking: Flatwater/River/Ocean)

**Data Available**
- iOS-style grouped list (`background: var(--color-bg-secondary)`, `border: 1px solid var(--color-border)`, `border-radius: 10px`)
- Each row: icon (28px rounded square) + data type label + source attribution right-aligned
- Available rows: green icon background (`rgba(76, 175, 80, 0.15)`), green stroke, white text, source in muted text
- Unavailable rows: muted icon background (`rgba(100, 116, 139, 0.1)`), gray stroke, gray text, explanation (e.g. "Inland lake")
- Rows separated by `1px solid var(--color-border)` borders

Data type icons (SVG, 14px):
- Water Temperature: thermometer
- Streamflow: flow arrows
- Wind & Weather: wind lines
- UV Index: sun
- Air Quality: air waves
- Tides: ocean waves

This section combines two sources:
- **Station-provided data** (water temp, streamflow, tides) - derived from enabled monitoring stations' `dataTypes`, updates dynamically as users toggle stations on/off
- **Always-available data** (wind, UV, AQI) - always shown as available from Open-Meteo regardless of stations
- **Water body type gating** - Tides row only shown for `bay_ocean` type. Streamflow row only shown for `river` type. If a station provides streamflow data for a lake location, the streamflow row is still hidden (the station icon badge shows it, but it won't appear in the summary since it's irrelevant for the water body type).

**Monitoring Stations**
- Same grouped list style as Data Available
- Each station row contains:
  - Station name (13px bold), e.g. "American River at Fair Oaks"
  - Station ID and distance (11px muted), e.g. "USGS 11446500 . 2.4 mi"
  - Data type icons (24px, smaller versions of the same icons from Data Available) showing what this station provides
  - Toggle switch (44x26px) on the right
- Toggle ON: sky blue background, white knob right-aligned
- Toggle OFF: `var(--color-border)` background, muted knob left-aligned
- Station text and icons dim when toggled off
- Stations sorted by distance, nearest first
- Stations within 20km on by default, others off
- **Geocoding fallback:** When user selects a geocoding result (no curated water body), the Monitoring Stations section is hidden entirely and Data Available shows only the always-available items (wind, UV, AQI). No station toggles appear since there are no linked stations. This matches the current behavior where geocoding locations get weather-only data.

**Save Location Button**
- Full width, sky blue background, white bold text, `border-radius: 10px`

### Data Flow
- When user selects a curated water body, search API returns `stations[]` array
- Data Available section is computed from all enabled stations' `dataTypes`
- Toggling a station on/off updates Data Available in real time
- On save, enabled station IDs are stored in `location.config.dataSources` as an object: `{ usgs: ["11446500", "11447360"], noaa: [] }`

### `dataSources` Type Migration

The `dataSources` type changes from `Record<string, string>` to `{ usgs: string[], noaa: string[] }`.

Both `app/src/lib/types.ts` and `api/src/services/conditions.ts` define `LocationConfig` and `SpotConfig` with `dataSources`. All must be updated:

- **New type:** `DataSources = { usgs: string[]; noaa: string[] }`
- **Normalization:** Add `normalizeDataSources(ds)` helper in `conditions.ts` called at the top of `getWaterData`. If input is old format (`{ usgs: "123", noaa: "456" }`), convert string values to single-element arrays. If already array format, pass through.
- **`SpotConfig.dataSources`** also migrates to the new array type. Existing spots with old-format dataSources are handled by the same normalizer.
- **`getWaterData`** iterates over the station ID arrays, querying each in order, using first valid result per data type.
- **`getWaterTempInfo`** unchanged - it only reads `waterTempF` and `waterTempSource` from `getWaterData`'s return value, not `dataSources` directly.

### Files Changed
- `app/src/pages/AddLocationPage.tsx` - complete rewrite of configure step
- `app/src/lib/types.ts` - update `WaterBodyResult` to include stations array, update `DataSources` type, update `LocationConfig` and `SpotConfig`

## 3. Multi-Station Backend

### New Table: `water_body_stations`

```sql
CREATE TABLE water_body_stations (
  id VARCHAR(36) PRIMARY KEY,
  water_body_id VARCHAR(36) NOT NULL,
  station_type ENUM('usgs', 'noaa') NOT NULL,
  station_id VARCHAR(50) NOT NULL,
  station_name VARCHAR(255) NOT NULL,
  distance_km DECIMAL(10, 2) NOT NULL,
  data_types JSON NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_wb_station (water_body_id, station_type, station_id),
  KEY idx_water_body_id (water_body_id),
  FOREIGN KEY (water_body_id) REFERENCES water_bodies(id) ON DELETE CASCADE
);
```

- `data_types` examples: `["water_temp", "streamflow"]`, `["water_temp", "tides"]`
- Valid data types: `water_temp`, `streamflow`, `gage_height` (USGS); `water_temp`, `tides`, `water_level` (NOAA)

### Import Script Changes

- `findNearestStation` replaced with `findStationsWithinRadius(lat, lng, stations, radiusKm)` returning all matches sorted by distance
- After inserting water body row, insert all matching stations into `water_body_stations`
- Keep existing `usgs_station_id` / `noaa_station_id` columns on `water_bodies` populated with nearest station for backward compatibility
- USGS station data enrichment: query USGS API for station name and available parameters per site

### USGS Station Data Types Discovery

The USGS Water Services API provides parameter information per station. During import, query available parameters:
- Parameter 00010 = Water Temperature
- Parameter 00060 = Discharge (Streamflow)
- Parameter 00065 = Gage Height

Store discovered parameters as `data_types` in junction table.

### Search Endpoint Changes

`GET /water-bodies/search?q=natoma` response adds `stations` array:

```json
{
  "id": "...",
  "name": "Lake Natoma",
  "type": "lake",
  "state": "CA",
  "lat": 38.63,
  "lng": -121.18,
  "usgsStationId": "11446500",
  "noaaStationId": null,
  "stations": [
    {
      "stationType": "usgs",
      "stationId": "11446500",
      "stationName": "American River at Fair Oaks",
      "distanceKm": 3.8,
      "dataTypes": ["water_temp", "streamflow"]
    },
    {
      "stationType": "usgs",
      "stationId": "11447360",
      "stationName": "Sacramento River at Freeport",
      "distanceKm": 13.0,
      "dataTypes": ["water_temp", "streamflow", "gage_height"]
    }
  ]
}
```

### Conditions Service Changes

- Accept `dataSources` as `{ usgs: string[], noaa: string[] }` (arrays instead of single values)
- For each data type, query enabled stations in distance order
- Use first station that returns valid data for each data type (closest valid wins)
- Maintains backward compatibility: if `dataSources` has string values (old format), treat as single-element array

### Files Changed
- `api/src/db/schema.ts` - add `waterBodyStations` table
- `api/src/db/migrations/0002_*.sql` - migration for new table
- `api/scripts/import-water-bodies.ts` - store multiple stations per water body
- `api/scripts/lib/haversine.ts` - add `findStationsWithinRadius`
- `api/scripts/lib/usgs-stations.ts` - fetch available parameters per station
- `api/src/routes/water-bodies/search.ts` - join stations in response. The route uses raw SQL (`dbPool.execute`), not Drizzle ORM. Add a second query to fetch stations for matched water body IDs, then merge in application code. Avoids JSON aggregation complexity in MySQL.
- `api/src/services/conditions.ts` - query multiple stations, closest valid wins

## 4. What Doesn't Change

- Geocoding fallback path (no curated data, no stations, weather-only)
- Scoring engine (`computePaddleScore`)
- Forecast endpoint response shape
- Bulk endpoint response shape
- Location detail page (`LocationDetailPage.tsx`)
- `ScoreHero`, `ConditionsGrid`, `ScoreCircle` components (internal use unchanged)
- NOAA/USGS API client functions (just called multiple times)

## 5. Verification

- Dashboard shows gradient cards with score glow and inline conditions for all locations
- Forecast blocks appear progressively after initial card render
- Add Location shows preview card, toggle selectors, data available with icons, monitoring stations with toggles
- Toggling a station off updates Data Available section in real time
- Multiple USGS stations stored per water body in junction table
- Search endpoint returns stations array with distance and data types
- Conditions service queries multiple enabled stations, closest valid data wins
- Backward compatibility: old locations with single-string dataSources still work
