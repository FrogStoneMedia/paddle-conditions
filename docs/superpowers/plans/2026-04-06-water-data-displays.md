# Water Data Displays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add water-body-specific condition tiles (reservoir gauges, river stage, water quality, pet safety) and a 24-hour streamflow chart to the location detail page.

**Architecture:** API changes first (load reservoirCapacityAf, add stageContext and flowHistory), then frontend types, then new components (WaterQualityRow, WaterConditionsTiles, StreamflowChart), then wire into LocationDetailPage.

**Tech Stack:** TypeScript, React, Recharts, Vitest (API), Vite (app)

**Spec:** `docs/superpowers/specs/2026-04-06-water-data-displays-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `api/src/services/conditions.ts` | Modify | Load reservoirCapacityAf from DB, add stageContext and flowHistory to response |
| `api/src/services/usgs.ts` | Modify | Add `fetchUsgsFlowHistory` for 24h historical flow |
| `api/src/services/water-body-cache.ts` | Modify | Add flowHistory to cached data interface |
| `api/tests/services/usgs.test.ts` | Modify | Add flowHistory tests |
| `app/src/lib/types.ts` | Modify | Add water data fields to ConditionsResponse and ForecastResponse |
| `app/src/components/WaterQualityRow.tsx` | Create | 4-column water quality metrics with threshold colors |
| `app/src/components/WaterConditionsTiles.tsx` | Create | Water-body-specific tile section (reservoir/river/pet safety) |
| `app/src/components/StreamflowChart.tsx` | Create | Recharts area chart with threshold bands |
| `app/src/pages/LocationDetailPage.tsx` | Modify | Render new components |

---

### Task 1: Load reservoirCapacityAf and Add stageContext to API Response

**Files:**
- Modify: `api/src/services/conditions.ts`

- [ ] **Step 1: Read the current code**

Read `api/src/services/conditions.ts` to find:
- Line 577: `reservoirCapacityAf: null, // TODO: load from water body record`
- The `buildConditionsResponse` function (around line 553)
- How the water body record is accessed (check if `waterBodies` table is already queried in the flow)
- Where `stageBaseline` is available in the response construction

- [ ] **Step 2: Load reservoirCapacityAf from the water body record**

The `buildConditionsResponse` function receives water data but not the water body record directly. You need to:

1. Find where the water body is queried in the conditions service (look for where `waterBodyType` is determined -- it's loaded from the `locations` or `waterBodies` table).
2. Add `reservoirCapacityAf` to the data that flows into `buildConditionsResponse`.
3. Replace the TODO null with the actual value.
4. Include `reservoirCapacityAf` in the response object (add as a top-level field alongside `reservoir`):

```typescript
...(reservoirCapacityAf != null && { reservoirCapacityAf }),
```

- [ ] **Step 3: Add stageContext to the response**

In `buildConditionsResponse`, after where `riverStageFt` is spread into the response (around line 629), add `stageContext`:

```typescript
...(water.riverStageFt != null && water.stageBaseline && {
  stageContext: (() => {
    const baseline = water.stageBaseline;
    const stage = water.riverStageFt!;
    const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const monthName = months[new Date().getMonth()];
    // Compute approximate percentile position (0-100) using linear interpolation
    let percentile: number;
    if (stage <= baseline.p10) percentile = 0;
    else if (stage <= baseline.p25) percentile = 10 + 15 * (stage - baseline.p10) / (baseline.p25 - baseline.p10);
    else if (stage <= baseline.p50) percentile = 25 + 25 * (stage - baseline.p25) / (baseline.p50 - baseline.p25);
    else if (stage <= baseline.p75) percentile = 50 + 25 * (stage - baseline.p50) / (baseline.p75 - baseline.p50);
    else if (stage <= baseline.p90) percentile = 75 + 15 * (stage - baseline.p75) / (baseline.p90 - baseline.p75);
    else percentile = 90 + 10 * Math.min(1, (stage - baseline.p90) / (baseline.p95 - baseline.p90));
    percentile = Math.round(Math.max(0, Math.min(100, percentile)));
    const label = percentile < 25 ? `Low for ${monthName}` : percentile > 75 ? `High for ${monthName}` : `Normal for ${monthName}`;
    return { label, percentile, p10: baseline.p10, p50: baseline.p50, p90: baseline.p90, p95: baseline.p95 };
  })(),
}),
```

- [ ] **Step 4: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Run tests**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && npx vitest run`
Expected: All 481 tests pass

- [ ] **Step 6: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api
git add src/services/conditions.ts
git commit -m "feat: load reservoirCapacityAf from DB, add stageContext to response"
```

---

### Task 2: Add Flow History to API (TDD)

**Files:**
- Modify: `api/src/services/usgs.ts` (add `fetchUsgsFlowHistory`)
- Modify: `api/src/services/conditions.ts` (fetch and include flowHistory)
- Modify: `api/src/services/water-body-cache.ts` (add flowHistory to cached interface)
- Modify: `api/tests/services/usgs.test.ts` (add tests)

- [ ] **Step 1: Write failing tests for fetchUsgsFlowHistory**

Read `api/tests/services/usgs.test.ts` to understand the mock pattern, then add:

```typescript
describe('fetchUsgsFlowHistory', () => {
  it('returns 24h of hourly flow readings', async () => {
    // Mock USGS response with multiple time series values
    // The USGS API returns timeSeries[].values[].value[] arrays
    // Each value has { value: string, dateTime: string }
    // Create mock with ~24 hourly readings for param 00060 (streamflow)
    const mockValues = Array.from({ length: 24 }, (_, i) => ({
      value: String(1000 + i * 10),
      dateTime: new Date(Date.now() - (23 - i) * 60 * 60 * 1000).toISOString(),
    }));
    // Mock the USGS response structure (check parseUsgs for exact shape)
    // ...adapt to match the actual mock pattern in the test file

    const history = await fetchUsgsFlowHistory('12345678');
    expect(history).toHaveLength(24);
    expect(history[0]).toHaveProperty('time');
    expect(history[0]).toHaveProperty('cfs');
    expect(history[0].cfs).toBe(1000);
  });

  it('returns empty array when no flow data', async () => {
    // Mock empty timeSeries response
    const history = await fetchUsgsFlowHistory('12345678');
    expect(history).toEqual([]);
  });
});
```

Adapt the mock structure to match the existing test patterns in `usgs.test.ts`. The key is understanding the USGS JSON response shape used in existing mocks.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && npx vitest run tests/services/usgs.test.ts`
Expected: FAIL -- `fetchUsgsFlowHistory` not exported

- [ ] **Step 3: Implement fetchUsgsFlowHistory**

Add to `api/src/services/usgs.ts`:

```typescript
export interface FlowHistoryPoint {
  time: string;
  cfs: number;
}

/**
 * Fetch 24 hours of historical streamflow readings from USGS.
 * Returns hourly data points (downsampled from 15-min intervals).
 */
export async function fetchUsgsFlowHistory(siteId: string): Promise<FlowHistoryPoint[]> {
  const params = new URLSearchParams({
    format: 'json',
    sites: siteId,
    parameterCd: PARAM_STREAMFLOW,
    period: 'PT24H',
  });

  const res = await fetch(`${USGS_URL}?${params}`);
  if (!res.ok) return [];

  const data = await res.json();
  const timeSeries = data?.value?.timeSeries;
  if (!Array.isArray(timeSeries)) return [];

  const flowSeries = timeSeries.find(
    (ts: any) => ts.variable?.variableCode?.[0]?.value === PARAM_STREAMFLOW,
  );
  if (!flowSeries) return [];

  const values = flowSeries.values?.[0]?.value;
  if (!Array.isArray(values) || values.length === 0) return [];

  // Downsample to hourly: take one reading per hour
  const hourly = new Map<string, FlowHistoryPoint>();
  for (const v of values) {
    const cfs = parseFloat(v.value);
    if (isNaN(cfs) || cfs < 0) continue;
    const dt = new Date(v.dateTime);
    const hourKey = dt.toISOString().slice(0, 13); // "YYYY-MM-DDTHH"
    hourly.set(hourKey, { time: dt.toISOString(), cfs });
  }

  return Array.from(hourly.values()).sort((a, b) => a.time.localeCompare(b.time));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && npx vitest run tests/services/usgs.test.ts`
Expected: PASS

- [ ] **Step 5: Add flowHistory to CachedConditionsData**

In `api/src/services/water-body-cache.ts`, add to the `water` interface inside `CachedConditionsData`:

```typescript
flowHistory?: Array<{ time: string; cfs: number }>;
```

Import `FlowHistoryPoint` from usgs.ts if using the type, or just use the inline shape.

- [ ] **Step 6: Fetch and include flowHistory in conditions service**

In `api/src/services/conditions.ts`:

1. Import `fetchUsgsFlowHistory` from usgs.ts:
```typescript
import { fetchUsgs, fetchUsgsFlowHistory, type UsgsData, type FlowHistoryPoint } from './usgs.js';
```

2. In `getWaterData()`, after USGS data is fetched (around line 764), add flow history fetch:
```typescript
// Fetch 24h flow history for chart
let flowHistory: FlowHistoryPoint[] = [];
if (usgsStationId && streamflowCfs != null) {
  const flowHistKey = `usgs:${usgsStationId}:flowHistory`;
  const cachedHistory = this.cache.get(flowHistKey) as FlowHistoryPoint[] | undefined;
  if (cachedHistory !== undefined) {
    flowHistory = cachedHistory;
  } else {
    flowHistory = await fetchUsgsFlowHistory(usgsStationId);
    this.cache.set(flowHistKey, flowHistory, TTL_WEATHER);
  }
}
```

3. Add `flowHistory` to the return value of `getWaterData()`.

4. In `fetchRawData()`, add `flowHistory` to the cached water object:
```typescript
flowHistory: waterData.flowHistory ?? [],
```

5. In `buildConditionsResponse()`, add `flowHistory` to the response:
```typescript
...(water.flowHistory && water.flowHistory.length > 0 && { flowHistory: water.flowHistory }),
```

- [ ] **Step 7: Verify build and tests**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && npx tsc --noEmit && npx vitest run`
Expected: No type errors, all tests pass

- [ ] **Step 8: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api
git add src/services/usgs.ts src/services/conditions.ts src/services/water-body-cache.ts tests/services/usgs.test.ts
git commit -m "feat: add 24h flow history to conditions API response"
```

---

### Task 3: Update Frontend Types

**Files:**
- Modify: `app/src/lib/types.ts`

- [ ] **Step 1: Add water data fields to ConditionsResponse**

In `app/src/lib/types.ts`, add these fields to the `ConditionsResponse` interface (after `refreshInterval`):

```typescript
  riverStageFt?: number | null;
  stageContext?: {
    label: string;
    percentile: number;
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
```

- [ ] **Step 2: Add flowHistory to ForecastResponse**

In the `ForecastResponse` interface, add:

```typescript
  flowHistory?: Array<{ time: string; cfs: number }>;
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app
git add src/lib/types.ts
git commit -m "feat: add water data types to ConditionsResponse and ForecastResponse"
```

---

### Task 4: WaterQualityRow Component

**Files:**
- Create: `app/src/components/WaterQualityRow.tsx`

- [ ] **Step 1: Create the component**

Create `app/src/components/WaterQualityRow.tsx`:

```tsx
interface WaterQualityRowProps {
  waterQuality: {
    turbidityNtu?: number;
    dissolvedOxygenMgL?: number;
    ph?: number;
    conductivityUs?: number;
  };
}

function wqColor(metric: string, value: number): string {
  switch (metric) {
    case 'turbidity':
      if (value < 10) return 'var(--color-go)';
      if (value <= 50) return 'var(--color-caution)';
      return 'var(--color-nogo)';
    case 'do':
      if (value > 6) return 'var(--color-go)';
      if (value >= 4) return 'var(--color-caution)';
      return 'var(--color-nogo)';
    case 'ph':
      if (value >= 6.5 && value <= 8.5) return 'var(--color-go)';
      if (value >= 6.0 && value <= 9.0) return 'var(--color-caution)';
      return 'var(--color-nogo)';
    case 'conductivity':
      if (value < 1000) return 'var(--color-go)';
      if (value <= 2000) return 'var(--color-caution)';
      return 'var(--color-nogo)';
    default:
      return 'var(--color-text)';
  }
}

export default function WaterQualityRow({ waterQuality }: WaterQualityRowProps) {
  const metrics: Array<{ label: string; value: number | undefined; unit: string; key: string }> = [
    { label: 'Turbidity', value: waterQuality.turbidityNtu, unit: 'NTU', key: 'turbidity' },
    { label: 'Dissolved O\u2082', value: waterQuality.dissolvedOxygenMgL, unit: 'mg/L', key: 'do' },
    { label: 'pH', value: waterQuality.ph, unit: '', key: 'ph' },
    { label: 'Conductivity', value: waterQuality.conductivityUs, unit: '\u00B5S/cm', key: 'conductivity' },
  ];

  const available = metrics.filter((m) => m.value != null);
  if (available.length === 0) return null;

  return (
    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${available.length}, 1fr)` }}>
      {available.map((m) => (
        <div
          key={m.key}
          className="rounded-lg p-2 text-center border"
          style={{ backgroundColor: 'var(--color-card)', borderColor: 'var(--color-border)' }}
        >
          <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{m.label}</div>
          <div className="text-base font-bold" style={{ color: wqColor(m.key, m.value!) }}>
            {m.key === 'ph' ? m.value!.toFixed(1) : Math.round(m.value!)}
          </div>
          {m.unit && (
            <div className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>{m.unit}</div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app
git add src/components/WaterQualityRow.tsx
git commit -m "feat: add WaterQualityRow component with threshold colors"
```

---

### Task 5: WaterConditionsTiles Component

**Files:**
- Create: `app/src/components/WaterConditionsTiles.tsx`

- [ ] **Step 1: Create the component**

Create `app/src/components/WaterConditionsTiles.tsx`:

```tsx
import type { ConditionsResponse } from '../lib/types.js';
import WaterQualityRow from './WaterQualityRow.js';

interface Props {
  conditions: ConditionsResponse;
  waterBodyType?: string;
}

function petSafetyColor(rating: string): string {
  if (rating === 'SAFE') return 'var(--color-go)';
  if (rating === 'CAUTION') return 'var(--color-caution)';
  return 'var(--color-nogo)';
}

function reservoirLevelColor(pct: number): string {
  if (pct >= 60) return 'var(--color-go)';
  if (pct >= 30) return 'var(--color-caution)';
  return 'var(--color-nogo)';
}

function Tile({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div
      className="rounded-xl p-3 text-center border"
      style={{ backgroundColor: 'var(--color-card)', borderColor: 'var(--color-border)' }}
    >
      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{label}</div>
      <div className="text-lg font-bold" style={{ color: color ?? 'var(--color-text)' }}>{value}</div>
      {sub && <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>{sub}</div>}
    </div>
  );
}

function ReservoirLevelTile({ storageAf, capacityAf }: { storageAf: number; capacityAf: number | null }) {
  if (capacityAf == null || capacityAf <= 0) {
    return <Tile label="Reservoir Storage" value={`${storageAf.toLocaleString()} AF`} />;
  }
  const pct = Math.round((storageAf / capacityAf) * 100);
  const color = reservoirLevelColor(pct);
  return (
    <div
      className="rounded-xl p-3 text-center border"
      style={{ backgroundColor: 'var(--color-card)', borderColor: 'var(--color-border)' }}
    >
      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Reservoir Level</div>
      <div className="text-xl font-bold" style={{ color }}>{pct}%</div>
      <div
        className="rounded h-1.5 mt-1 overflow-hidden"
        style={{ backgroundColor: 'var(--color-border)' }}
      >
        <div className="h-full rounded" style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color }} />
      </div>
      <div className="text-[10px] mt-1" style={{ color: 'var(--color-text-muted)' }}>
        {storageAf.toLocaleString()} of {capacityAf.toLocaleString()} AF
      </div>
    </div>
  );
}

function RiverStageTile({ stageFt, stageContext }: { stageFt: number; stageContext: NonNullable<ConditionsResponse['stageContext']> }) {
  const { label, percentile, p10, p95 } = stageContext;
  const color = percentile > 75 ? 'var(--color-caution)' : percentile < 25 ? 'var(--color-text-muted)' : 'var(--color-go)';
  // Position marker as percentage of the gauge (p10=0%, p95=100%)
  const range = p95 - p10;
  const markerPct = range > 0 ? Math.max(0, Math.min(100, ((stageFt - p10) / range) * 100)) : 50;

  return (
    <div
      className="rounded-xl p-3 text-center border"
      style={{ backgroundColor: 'var(--color-card)', borderColor: 'var(--color-border)' }}
    >
      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>River Stage</div>
      <div className="text-xl font-bold" style={{ color }}>{stageFt.toFixed(1)} ft</div>
      <div className="relative rounded h-1.5 mt-1 overflow-visible" style={{ background: 'linear-gradient(to right, var(--color-go), var(--color-caution), var(--color-nogo))' }}>
        <div
          className="absolute top-[-2px] w-[3px] h-[10px] rounded"
          style={{ left: `${markerPct}%`, backgroundColor: 'var(--color-text)', transform: 'translateX(-50%)' }}
        />
      </div>
      <div className="text-[10px] mt-1" style={{ color: 'var(--color-text-muted)' }}>{label}</div>
    </div>
  );
}

export default function WaterConditionsTiles({ conditions, waterBodyType }: Props) {
  const { reservoir, waterQuality, petSafety, riverStageFt, stageContext, reservoirCapacityAf } = conditions;
  const streamflowCfs = conditions.current.streamflowCfs;

  const isReservoir = (waterBodyType === 'reservoir' || waterBodyType === 'lake') && reservoir;
  const isRiver = waterBodyType === 'river' && riverStageFt != null;

  if (!isReservoir && !isRiver && !petSafety && !waterQuality) return null;

  return (
    <div className="mt-4">
      {/* Section label */}
      {(isReservoir || isRiver) && (
        <div className="text-xs uppercase tracking-wider mb-2" style={{ color: 'var(--color-text-muted)' }}>
          {isReservoir ? 'Reservoir Conditions' : 'River Conditions'}
        </div>
      )}

      {/* Main tiles */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        {/* Reservoir tiles */}
        {isReservoir && reservoir.storageAf != null && (
          <ReservoirLevelTile storageAf={reservoir.storageAf} capacityAf={reservoirCapacityAf ?? null} />
        )}
        {isReservoir && reservoir.elevationFt != null && (
          <Tile label="Elevation" value={`${Math.round(reservoir.elevationFt)} ft`} sub="Surface level" />
        )}
        {isReservoir && reservoir.outflowCfs != null && (
          <Tile label="Dam Outflow" value={reservoir.outflowCfs.toLocaleString()} sub="CFS" />
        )}
        {isReservoir && reservoir.inflowCfs != null && (
          <Tile label="Inflow" value={reservoir.inflowCfs.toLocaleString()} sub="CFS" />
        )}

        {/* River tiles */}
        {isRiver && stageContext && (
          <RiverStageTile stageFt={riverStageFt!} stageContext={stageContext} />
        )}
        {isRiver && !stageContext && riverStageFt != null && (
          <Tile label="River Stage" value={`${riverStageFt.toFixed(1)} ft`} />
        )}

        {/* Shared tiles */}
        {streamflowCfs != null && (
          <Tile label="Streamflow" value={streamflowCfs.toLocaleString()} sub="CFS" />
        )}

        {/* Pet safety */}
        {petSafety && (
          <Tile
            label="Pet Safety"
            value={petSafety.rating}
            sub={petSafety.reasons.length > 0 ? petSafety.reasons[0] : 'No advisories'}
            color={petSafetyColor(petSafety.rating)}
          />
        )}
      </div>

      {/* Water quality sub-row */}
      {waterQuality && <WaterQualityRow waterQuality={waterQuality} />}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app
git add src/components/WaterConditionsTiles.tsx
git commit -m "feat: add WaterConditionsTiles with reservoir/river/pet safety tiles"
```

---

### Task 6: StreamflowChart Component

**Files:**
- Create: `app/src/components/StreamflowChart.tsx`

- [ ] **Step 1: Create the component**

Create `app/src/components/StreamflowChart.tsx`. Follow the exact pattern from `AqiChart.tsx`:

```tsx
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceArea,
} from 'recharts';
import { formatTime } from '../lib/utils.js';

interface StreamflowChartProps {
  flowHistory: Array<{ time: string; cfs: number }>;
  optimalCfs?: number;
}

export default function StreamflowChart({ flowHistory, optimalCfs }: StreamflowChartProps) {
  if (flowHistory.length === 0) return null;

  const data = flowHistory.map((p) => ({
    time: formatTime(p.time),
    cfs: Math.round(p.cfs),
  }));

  const maxCfs = Math.max(...data.map((d) => d.cfs), optimalCfs ? optimalCfs * 2.5 : 0);
  const currentCfs = data[data.length - 1]?.cfs;

  // Threshold bands based on optimal CFS
  const idealLow = optimalCfs ? Math.round(optimalCfs * 0.8) : null;
  const idealHigh = optimalCfs ? Math.round(optimalCfs * 1.2) : null;
  const marginalHigh = optimalCfs ? Math.round(optimalCfs * 2) : null;

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <div className="text-sm font-semibold" style={{ color: 'var(--color-text)' }}>
          Streamflow (CFS)
        </div>
        {currentCfs != null && (
          <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Current: <span className="font-semibold" style={{ color: 'var(--color-water, #0ea5e9)' }}>{currentCfs.toLocaleString()} CFS</span>
          </div>
        )}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="time" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
          <YAxis domain={[0, Math.ceil(maxCfs * 1.1)]} tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-card)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number) => [`${value.toLocaleString()} CFS`, 'Flow']}
          />
          {/* Threshold bands (only when optimalCfs is configured) */}
          {idealLow != null && idealHigh != null && (
            <ReferenceArea y1={idealLow} y2={idealHigh} fill="#22c55e" fillOpacity={0.06} />
          )}
          {idealHigh != null && marginalHigh != null && (
            <ReferenceArea y1={idealHigh} y2={marginalHigh} fill="#eab308" fillOpacity={0.05} />
          )}
          {marginalHigh != null && (
            <ReferenceArea y1={marginalHigh} y2={Math.ceil(maxCfs * 1.1)} fill="#ef4444" fillOpacity={0.05} />
          )}
          <Area
            type="monotone"
            dataKey="cfs"
            stroke="#0ea5e9"
            fill="#0ea5e9"
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app
git add src/components/StreamflowChart.tsx
git commit -m "feat: add StreamflowChart with threshold bands"
```

---

### Task 7: Integrate Into LocationDetailPage

**Files:**
- Modify: `app/src/pages/LocationDetailPage.tsx`

- [ ] **Step 1: Add WaterConditionsTiles import and render**

At the top of `LocationDetailPage.tsx`, add the import alongside the existing component imports (not lazy -- it's small and part of the initial view):

```typescript
import WaterConditionsTiles from '../components/WaterConditionsTiles.js';
```

After the `ConditionsGrid` render (line 103), add:

```tsx
<WaterConditionsTiles conditions={conditions} waterBodyType={location?.waterBodyType} />
```

- [ ] **Step 2: Add StreamflowChart lazy import and render**

Add to the lazy imports (after line 20):

```typescript
const StreamflowChart = lazy(() => import('../components/StreamflowChart.js'));
```

In the charts section (after the PrecipChart card, around line 162), add:

```tsx
{forecast.flowHistory && forecast.flowHistory.length > 0 && (
  <div className="rounded-xl border p-4" style={{ backgroundColor: 'var(--color-card)', borderColor: 'var(--color-border)' }}>
    <StreamflowChart flowHistory={forecast.flowHistory} />
  </div>
)}
```

- [ ] **Step 3: Verify build**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Dev server visual check**

Run: `cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && npx vite dev`

Open the app, navigate to a California reservoir location (Folsom Lake or Lake Natoma) and verify:
- Reservoir condition tiles appear below the weather grid
- River locations show stage tiles
- Streamflow chart appears in the charts section (if flow data available)

- [ ] **Step 5: Commit**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app
git add src/pages/LocationDetailPage.tsx
git commit -m "feat: integrate water condition tiles and streamflow chart into detail page"
```

---

### Task 8: Build, Deploy, and Update Docs

- [ ] **Step 1: Build and deploy API**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api
npm run build
rsync -avz --delete dist/ devsac@104.255.174.113:~/public_html/api.paddleconditions.com/dist/ -e "ssh -i ~/.ssh/paddleconditions_prod -p 11208"
ssh -i ~/.ssh/paddleconditions_prod -p 11208 devsac@104.255.174.113 "touch ~/public_html/api.paddleconditions.com/tmp/restart.txt"
```

- [ ] **Step 2: Build and deploy app**

Build and deploy the app following the same pattern used for the app repo. Check `app/CLAUDE.md` or `app/package.json` for deploy scripts.

- [ ] **Step 3: Update changelog**

Add entry to `website/data/changelog.json`:

```json
{
  "date": "2026-04-06",
  "headline": "Water Data Displays",
  "entries": [
    {
      "type": "new-feature",
      "title": "Water Condition Tiles",
      "text": "Reservoir locations now show storage level gauges, elevation, dam outflow, and inflow. River locations display current stage with a gauge showing where the level falls relative to monthly normals. Water quality metrics and pet safety ratings appear when sensor data is available."
    },
    {
      "type": "new-feature",
      "title": "Streamflow Chart",
      "text": "A new 24-hour streamflow chart shows how flow has changed over the past day with threshold bands marking ideal, marginal, and high-flow zones."
    }
  ]
}
```

- [ ] **Step 4: Push all repos**

```bash
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/api && git push
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/app && git push
cd /Users/michaelkahn/Documents/ClaudeCode/PaddleConditions/website && git push
```
