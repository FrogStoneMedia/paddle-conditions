# River Stage Scoring Design

## Overview

Add river stage as a scoring factor for California river water bodies using CDEC data. Unlike universal metrics (wind, AQI), river stage has no absolute "good" values. A 3-foot stage might be ideal on one river and dangerous on another. This design uses per-station monthly percentile baselines to normalize stage readings into the existing scoring framework.

## Data Flow

```
CDEC historical data (5 years daily)
  --> computeStageBaseline() --> cdec_stage_baselines table (monthly percentiles)

CDEC real-time stage (sensor 1, event data)
  --> fetchCdecRiverStage() --> conditions service
  --> scoreRiverStage(current, baseline, profileDirection) --> composite score
```

## Baseline Data

### New Table: `cdec_stage_baselines`

| Column | Type | Description |
|--------|------|-------------|
| stationId | varchar(3) | CDEC station ID (PK) |
| month | tinyint | 1-12 (PK) |
| p10 | float | 10th percentile stage (feet) |
| p25 | float | 25th percentile, low-normal |
| p50 | float | Median stage |
| p75 | float | 75th percentile, high-normal |
| p90 | float | 90th percentile, elevated |
| p95 | float | 95th percentile, flood veto threshold |
| sampleCount | int | Number of daily observations used |
| computedAt | datetime | When baseline was last computed |

Composite primary key: (stationId, month).

### Population

A service function `computeStageBaseline(stationId: string)` handles baseline computation:

1. Fetch 5 years of daily stage data from CDEC (sensor 1, dur_code D)
2. Group observations by month
3. Compute percentiles (p10, p25, p50, p75, p90, p95) per month
4. Upsert all 12 months into `cdec_stage_baselines`
5. Record `computedAt` timestamp and `sampleCount`

Run once per station during station setup. Re-run annually or on demand to incorporate new data.

### CDEC Historical Data API

Same endpoint as real-time, with different parameters:
- `dur_code=D` (daily averages instead of event data)
- `Start=2021-01-01&End=2026-04-06` (5-year window)
- Returns one value per day per station

Expected volume: ~1,825 daily records per station (5 years). Small enough to process in-memory.

## Scoring Function

### `scoreRiverStage(currentStageFt, baseline, inverted)`

The function maps the current stage against the station's monthly percentile baseline. The `inverted` flag controls whether lower or higher stage is preferred.

**Normal direction (recreational/family -- lower stage is better):**

| Current Stage | Score | Rationale |
|---------------|-------|-----------|
| <= p50 | 100 | Calm, manageable water |
| p50 to p75 | 100 to 50 | Increasing current, getting challenging |
| p75 to p90 | 50 to 0 | High water, dangerous for casual paddlers |
| >= p90 | 0 | Nogo range |

**Inverted direction (racing/river -- higher stage is better):**

| Current Stage | Score | Rationale |
|---------------|-------|-----------|
| >= p50 | 100 | Good current, exciting water |
| p25 to p50 | 50 to 100 | Moderate flow, acceptable |
| p10 to p25 | 0 to 50 | Getting low, shallow spots |
| <= p10 | 0 | Too low, scraping bottom |

Linear interpolation between threshold points, consistent with existing scoring functions.

**Returns null when:**
- `currentStageFt` is null
- No baseline data exists for the station/month combination

### Hard Veto

Stage >= p95 (for the current month) triggers NO_GO for ALL profiles, including racing. Flood conditions are universally dangerous: debris, fast currents, submerged hazards.

Veto reason: `"Dangerous water level"`

This is checked in `computePaddleScore` alongside existing vetoes (wind, AQI, visibility, etc.).

## Profile Integration

### Weights

| Profile | Weight | Direction | Rationale |
|---------|--------|-----------|-----------|
| SUP recreational | 0.10 | Normal | Cautious of high water |
| SUP racing | 0.10 | Inverted | Prefers current for speed |
| SUP family | 0.15 | Normal | Extra cautious, kids on board |
| Kayak flatwater | 0.10 | Normal | Similar to SUP recreational |
| Kayak river | 0.15 | Inverted | Wants current, experienced |
| Kayak ocean | 0 | N/A | River stage not applicable |

### Profile Config Changes

Add to `ProfileConfig.weights`:
```typescript
river_stage?: number
```

Add to `ProfileConfig`:
```typescript
riverStageInverted?: boolean  // true = higher stage scores better (racing/river)
```

Unlike other factors, river stage does not use `curves` for thresholds. The percentile values from `cdec_stage_baselines` serve as the thresholds. The `riverStageInverted` flag controls scoring direction: `false` (default) means lower stage scores better (recreational), `true` means higher stage scores better (racing).

## Conditions Service Integration

### Data Flow in `getWaterData()`

1. Fetch `riverStageFt` from CDEC (already exists)
2. Look up baseline: query `cdec_stage_baselines` for the station's current month
3. Cache baseline in memory (24h TTL, station baselines are static)
4. Pass `riverStageFt` and baseline to `computePaddleScore`

### ScoreInput Changes

Add to `ScoreInput`:
```typescript
riverStageFt?: number | null
stageBaseline?: {
  p10: number; p25: number; p50: number
  p75: number; p90: number; p95: number
} | null
```

### Activation Conditions

River stage scoring activates when ALL of:
1. Water body has a CDEC station with `"stage"` in `dataTypes`
2. That station has baseline data in `cdec_stage_baselines` for the current month
3. Active profile has `river_stage` weight > 0

If any condition is not met, river_stage is excluded from the composite score via existing weight renormalization.

## Applicable Stations

Currently configured stations with stage data:
- **AFO** (American River at Fair Oaks) - river gauge, sensor 1 available
- **CBR** (American River at Chili Bar) - river gauge, sensor 1 available

Not applicable:
- FOL, NAT - reservoir stations (use reservoir level scoring instead)

Future stations added via station discovery will automatically get river stage scoring if they have sensor 1 and baselines are computed.

## Testing

### Unit Tests

**`scoreRiverStage` function:**
- Normal direction: score 100 at p50, 50 at p75, 0 at p90
- Inverted direction: score 100 at p50, 50 at p25, 0 at p10
- Returns null for null input
- Returns null for null baseline
- Linear interpolation between thresholds
- Edge cases: stage exactly at percentile boundaries

**`computeStageBaseline` function:**
- Correctly computes percentiles from daily data
- Groups by month correctly
- Handles months with sparse data (few observations)
- Handles empty response from CDEC

### Integration Tests

**Veto logic:**
- Stage >= p95 triggers NO_GO for recreational profiles
- Stage >= p95 triggers NO_GO for racing profiles (universal veto)
- Veto reason is "Dangerous water level"

**Composite scoring:**
- River stage factor included for river water bodies with baselines
- River stage factor excluded for reservoir water bodies
- Weight renormalization works correctly with river_stage present/absent
- Racing profile scores high stage favorably
- Recreational profile scores high stage unfavorably

### Test Fixtures

Capture real CDEC daily stage data for AFO station to use as test fixture. Compute known percentiles from the fixture data for deterministic tests.

## Migration

**Migration 0008:** Create `cdec_stage_baselines` table.

After migration, run `computeStageBaseline` for AFO and CBR stations to populate initial baselines.
