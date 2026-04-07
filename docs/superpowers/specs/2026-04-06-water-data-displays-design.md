# Water Data Displays Design

## Overview

Add visual displays for water-body-specific data on the location detail page. Reservoir locations show storage level gauges, elevation, dam outflow, and inflow. River locations show stage gauges with monthly percentile context. All locations with flow data get a 24-hour streamflow chart. Water quality metrics and pet safety badges appear when sensor data is available.

## Scope

Two areas of work:

1. **Frontend (app/):** New tile components for the conditions grid and a new streamflow chart.
2. **API (api/):** Extend the conditions response with flow history and ensure all water data fields are surfaced.

## Expanded Conditions Grid

### Layout

Below the existing 6 weather tiles, a new section appears with a descriptive label and water-body-specific tiles. The section only renders when water data is present.

### Reservoir/Lake Tiles

Renders when `waterBodyType` is `reservoir` or `lake` AND `current.reservoir` exists.

Section label: "Reservoir Conditions"

Tiles (3-column grid, same style as existing weather tiles):

| Tile | Value | Subtitle | Color logic |
|------|-------|----------|-------------|
| Reservoir Level | Percentage (storage/capacity * 100) | "{storage} AF of {capacity} AF" | Green >= 60%, Yellow 30-60%, Red < 20% |
| Elevation | `{elevationFt} ft` | "Surface level" | None (informational) |
| Dam Outflow | `{outflowCfs}` | "CFS" | Red if above dam outflow threshold |
| Inflow | `{inflowCfs}` | "CFS" | None (informational) |
| Streamflow | `{streamflowCfs}` | "CFS" | None (informational) |
| Pet Safety | SAFE / CAUTION / UNSAFE | First reason or "No advisories" | Green/Yellow/Red by rating |

The reservoir level tile includes a horizontal progress bar gauge below the percentage, filled proportionally and colored to match the rating.

Tiles only render when their data field is non-null. If a reservoir has no inflow sensor, that tile is omitted. The grid reflows naturally with CSS grid.

`reservoirCapacityAf` comes from the water body record. If capacity is null, the reservoir level tile shows raw storage AF without a percentage or gauge.

### River Tiles

Renders when `waterBodyType` is `river` AND `current.riverStageFt` exists.

Section label: "River Conditions"

Tiles (3-column grid):

| Tile | Value | Subtitle | Visual |
|------|-------|----------|--------|
| River Stage | `{riverStageFt} ft` | "Normal for {month}" / "High for {month}" / "Low for {month}" | Gradient gauge bar with position marker |
| Streamflow | `{streamflowCfs}` | "CFS" | None |
| Pet Safety | SAFE / CAUTION / UNSAFE | First reason or "No advisories" | Color badge |

The river stage tile includes a gradient gauge bar (green to yellow to red) with a small marker showing where the current reading falls relative to the monthly percentile range (p10 to p95). The subtitle text is derived from where the current stage falls:

- Below p25: "Low for {month}"
- p25 to p75: "Normal for {month}"
- Above p75: "High for {month}"

This requires the API to include the stage baseline percentiles and current month context in the response (see API Changes below).

### Water Quality Sub-Row

Renders when `current.waterQuality` exists and has at least one metric.

A 4-column row of smaller tiles below the main water tiles:

| Metric | Unit | Ideal (green) | Marginal (yellow) | Nogo (red) |
|--------|------|---------------|--------------------|----|
| Turbidity | NTU | < 10 | 10-50 | > 100 |
| Dissolved O2 | mg/L | > 6 | 4-6 | < 4 |
| pH | -- | 6.5-8.5 | 6.0-6.5 or 8.5-9.0 | < 6.0 or > 9.0 |
| Conductivity | uS/cm | < 1000 | 1000-2000 | > 2000 |

Each metric tile shows the value colored by its threshold bracket. Tiles only render for metrics with data.

### Tile Rendering Logic

The `WaterConditionsTiles` component receives `current`, `waterBodyType`, and `reservoirCapacityAf`. It renders:

1. Nothing if no water-body-specific data exists.
2. The section label based on water body type.
3. The appropriate tile set based on type + available data.
4. The water quality sub-row if `current.waterQuality` has any metrics.

## Streamflow Chart

A new Recharts chart component in the "Detailed Charts" section, rendered after the existing precipitation chart.

### Chart Type

Area chart with threshold reference bands, consistent with the AQI chart pattern:

- **Background bands:** Three horizontal `ReferenceArea` zones marking ideal (green, low opacity), marginal (yellow), and nogo (red) flow ranges.
- **Data area:** Shaded area fill with line showing flow readings over time.
- **Current value badge:** Top-right corner showing "Current: {value} CFS".
- **Axes:** X-axis shows time labels, Y-axis shows CFS with auto-scaled domain.

### Threshold Bands

The threshold values come from the streamflow scoring curves in the profile. The existing `scoreStreamflow` function uses an optimal CFS and +/- 20% range. The chart bands mirror this:

- Green band: optimal CFS +/- 20%
- Yellow band: extends from green boundary to 2x optimal
- Red band: above 2x optimal

If no optimal CFS is configured for the location, the chart renders without threshold bands (just the flow line and area fill).

### Data Source

The chart uses `flowHistory` -- an array of `{ time: string, cfs: number }` in the conditions response. This is 24 hours of observed flow data sampled at 1-hour intervals.

### Rendering Conditions

The `StreamflowChart` component renders only when `flowHistory` has data. It is lazy-loaded like all other charts.

## API Changes

### Frontend Types (`app/src/lib/types.ts`)

Extend `CurrentConditions`:

```typescript
interface CurrentConditions {
  // ... existing fields ...
  riverStageFt?: number | null;
  stageContext?: {
    label: string;       // "Normal for April", "High for April", etc.
    percentile: number;  // Where current stage falls (0-100)
    p10: number;
    p50: number;
    p90: number;
    p95: number;
  } | null;
  reservoir?: {
    storageAf?: number;
    elevationFt?: number;
    inflowCfs?: number;
    outflowCfs?: number;
    scheduledReleaseCfs?: number;
    regulatingReleaseCfs?: number;
  } | null;
  reservoirCapacityAf?: number | null;
  waterQuality?: {
    turbidityNtu?: number;
    dissolvedOxygenMgL?: number;
    ph?: number;
    conductivityUs?: number;
  } | null;
  petSafety?: {
    rating: 'SAFE' | 'CAUTION' | 'UNSAFE';
    reasons: string[];
  } | null;
}
```

Add to `ForecastResponse`:

```typescript
interface ForecastResponse {
  // ... existing fields ...
  flowHistory?: Array<{ time: string; cfs: number }>;
}
```

### API Response Changes (`api/src/services/conditions.ts`)

**Include existing water data in the response.** The API already computes reservoir, waterQuality, petSafety, and riverStageFt but some fields are not included in the response object sent to clients. Ensure all fields are present:

- `reservoir` object (storage, elevation, inflow, outflow, releases)
- `waterQuality` object (turbidity, DO, pH, conductivity)
- `petSafety` object (rating, reasons)
- `riverStageFt` (already included)
- `reservoirCapacityAf` from the water body record

**Add `stageContext`** to the response when river stage and baseline data are available. Computed from the stage baseline:

```typescript
stageContext: stageBaseline ? {
  label: percentile < 25 ? `Low for ${monthName}` : percentile > 75 ? `High for ${monthName}` : `Normal for ${monthName}`,
  percentile,  // 0-100 position of current stage in the monthly distribution
  p10: stageBaseline.p10,
  p50: stageBaseline.p50,
  p90: stageBaseline.p90,
  p95: stageBaseline.p95,
} : null
```

**Add `flowHistory`** to the forecast/conditions response:

Fetch the last 24 hours of streamflow readings from USGS (or CDEC for CA locations). USGS provides instantaneous values every 15 minutes. Downsample to 1-hour intervals to keep the payload reasonable (~24 data points).

- Use the existing `fetchUsgs` function pattern, querying the USGS instantaneous values endpoint with `period=PT24H`.
- For CDEC stations, use `fetchSensorData` with sensor 20 (flow) and a 1-day lookback.
- Cache with the same TTL as other water data (15 min in-memory).
- Return as `flowHistory: Array<{ time: string, cfs: number }>` sorted chronologically.

If no flow data is available, omit `flowHistory` from the response.

## New Frontend Components

### `WaterConditionsTiles.tsx`

**Props:**
```typescript
interface WaterConditionsTilesProps {
  current: CurrentConditions;
  waterBodyType?: string;
  reservoirCapacityAf?: number | null;
}
```

**Responsibility:** Renders the water-body-specific tile section below the weather grid. Handles all conditional rendering logic internally.

### `WaterQualityRow.tsx`

**Props:**
```typescript
interface WaterQualityRowProps {
  waterQuality: { turbidityNtu?: number; dissolvedOxygenMgL?: number; ph?: number; conductivityUs?: number };
}
```

**Responsibility:** Renders the 4-column water quality metric tiles with color-coded values. Used by `WaterConditionsTiles`.

### `StreamflowChart.tsx`

**Props:**
```typescript
interface StreamflowChartProps {
  flowHistory: Array<{ time: string; cfs: number }>;
  optimalCfs?: number;
}
```

**Responsibility:** Renders the Recharts area chart with threshold bands. Follows the same pattern as `AqiChart.tsx` (ComposedChart with ReferenceArea bands).

## Integration Points

### LocationDetailPage.tsx

1. Import and render `WaterConditionsTiles` after the existing `ConditionsGrid` component.
2. Lazy-import and render `StreamflowChart` in the charts section after `PrecipChart`.
3. Pass `waterBodyType` and `reservoirCapacityAf` from the location config.

### ConditionsGrid.tsx

No changes. The existing grid keeps its 6 tiles. The new water tiles are a separate component rendered below it.

## Testing

### Frontend

- `WaterConditionsTiles` renders reservoir tiles when `waterBodyType === 'reservoir'` and reservoir data exists.
- `WaterConditionsTiles` renders river tiles when `waterBodyType === 'river'` and stage data exists.
- `WaterConditionsTiles` renders nothing when no water data exists.
- `WaterQualityRow` colors values correctly by threshold.
- `StreamflowChart` renders with flow history data.
- `StreamflowChart` renders threshold bands when optimalCfs is provided.
- Pet safety badge shows correct color and reason text.
- Reservoir level gauge shows correct fill percentage and color.

### API

- `flowHistory` included in response when flow data is available.
- `flowHistory` downsampled to hourly from 15-min readings.
- `stageContext` computed correctly from baseline percentiles.
- `reservoirCapacityAf` included from water body record.
- All water data fields present in response (reservoir, waterQuality, petSafety).
