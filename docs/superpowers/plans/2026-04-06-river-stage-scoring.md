# River Stage Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add river stage as a profile-dependent scoring factor using per-station monthly percentile baselines from CDEC historical data.

**Architecture:** New `scoreRiverStage` function uses `linearScore`/`linearScoreInverted` with percentile thresholds from a `cdec_stage_baselines` DB table. A `computeStageBaseline` function in the CDEC service fetches 5 years of daily data and computes monthly percentiles. The conditions service looks up baselines and passes them to `computePaddleScore`, which handles the veto (p95+) and factor scoring.

**Tech Stack:** TypeScript, Vitest, Drizzle ORM, MariaDB, CDEC JSON API

**Spec:** `docs/superpowers/specs/2026-04-06-river-stage-scoring-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `api/src/db/schema.ts` | Modify | Add `cdecStageBaselines` table definition |
| `api/src/db/migrations/0008_*.sql` | Create | DDL for `cdec_stage_baselines` table |
| `api/src/lib/scoring.ts` | Modify | Add `scoreRiverStage`, `StageBaseline` type, extend `ScoreInput` and `ProfileConfig`, add veto + factor in `computePaddleScore` |
| `api/src/lib/profiles.ts` | Modify | Add `river_stage` weight and `riverStageInverted` to all profiles |
| `api/src/services/cdec.ts` | Modify | Add `fetchCdecHistoricalStage` and `computeStageBaseline` functions |
| `api/src/services/conditions.ts` | Modify | Look up stage baseline, pass to scoring |
| `api/tests/lib/scoring-cdec.test.ts` | Modify | Add `scoreRiverStage` unit tests |
| `api/tests/lib/scoring-integration.test.ts` | Modify | Add river stage veto + composite tests |
| `api/tests/services/cdec.test.ts` | Modify | Add `fetchCdecHistoricalStage` and `computeStageBaseline` tests |

---

### Task 1: Database Schema and Migration

**Files:**
- Modify: `api/src/db/schema.ts` (after line 183, after `waterBodyStations` table)
- Create: `api/src/db/migrations/0008_river_stage_baselines.sql`

- [ ] **Step 1: Add table definition to schema.ts**

Add after the `waterBodyStations` table definition (after line 183):

```typescript
export const cdecStageBaselines = mysqlTable(
  'cdec_stage_baselines',
  {
    stationId: varchar('station_id', { length: 3 }).notNull(),
    month: int('month', { unsigned: true }).notNull(),
    p10: double('p10').notNull(),
    p25: double('p25').notNull(),
    p50: double('p50').notNull(),
    p75: double('p75').notNull(),
    p90: double('p90').notNull(),
    p95: double('p95').notNull(),
    sampleCount: int('sample_count', { unsigned: true }).notNull(),
    computedAt: timestamp('computed_at').notNull().defaultNow(),
  },
  (table) => [
    uniqueIndex('uq_station_month').on(table.stationId, table.month),
  ],
);
```

- [ ] **Step 2: Create the SQL migration file**

Create `api/src/db/migrations/0008_river_stage_baselines.sql`:

```sql
CREATE TABLE `cdec_stage_baselines` (
  `station_id` varchar(3) NOT NULL,
  `month` int unsigned NOT NULL,
  `p10` double NOT NULL,
  `p25` double NOT NULL,
  `p50` double NOT NULL,
  `p75` double NOT NULL,
  `p90` double NOT NULL,
  `p95` double NOT NULL,
  `sample_count` int unsigned NOT NULL,
  `computed_at` timestamp NOT NULL DEFAULT (now()),
  UNIQUE INDEX `uq_station_month` (`station_id`, `month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci;
```

- [ ] **Step 3: Update the migration journal**

Read `api/src/db/migrations/meta/_journal.json` and add the new entry for migration 0008. Follow the exact pattern of existing entries (idx, version, when, tag, breakpoints).

- [ ] **Step 4: Verify build**

Run: `cd api && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
cd api && git add src/db/schema.ts src/db/migrations/0008_river_stage_baselines.sql src/db/migrations/meta/_journal.json
git commit -m "feat: add cdec_stage_baselines table schema and migration"
```

---

### Task 2: `scoreRiverStage` Scoring Function (TDD)

**Files:**
- Modify: `api/src/lib/scoring.ts` (add type + function after line 156, extend `ScoreInput` at line 256, extend `ProfileConfig` at line 74)
- Modify: `api/tests/lib/scoring-cdec.test.ts` (add tests)

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/lib/scoring-cdec.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { scoreReservoirLevel, scoreWaterQuality, computePetSafety, scoreRiverStage } from '../../src/lib/scoring.js';

// ... existing tests ...

describe('scoreRiverStage', () => {
  const baseline = { p10: 1.0, p25: 1.5, p50: 2.5, p75: 4.0, p90: 6.0, p95: 8.0, sampleCount: 150 };

  describe('normal direction (lower stage = better)', () => {
    it('returns 100 at median stage', () => {
      expect(scoreRiverStage(2.5, baseline, false)).toBe(100);
    });
    it('returns 100 below median', () => {
      expect(scoreRiverStage(1.0, baseline, false)).toBe(100);
    });
    it('returns 50 at p75', () => {
      expect(scoreRiverStage(4.0, baseline, false)).toBe(50);
    });
    it('returns 0 at p90', () => {
      expect(scoreRiverStage(6.0, baseline, false)).toBe(0);
    });
    it('interpolates between p50 and p75', () => {
      const score = scoreRiverStage(3.25, baseline, false)!;
      expect(score).toBeGreaterThan(50);
      expect(score).toBeLessThan(100);
    });
    it('interpolates between p75 and p90', () => {
      const score = scoreRiverStage(5.0, baseline, false)!;
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThan(50);
    });
    it('returns 0 above p90', () => {
      expect(scoreRiverStage(7.0, baseline, false)).toBe(0);
    });
  });

  describe('inverted direction (higher stage = better)', () => {
    it('returns 100 at median stage', () => {
      expect(scoreRiverStage(2.5, baseline, true)).toBe(100);
    });
    it('returns 100 above median', () => {
      expect(scoreRiverStage(5.0, baseline, true)).toBe(100);
    });
    it('returns 50 at p25', () => {
      expect(scoreRiverStage(1.5, baseline, true)).toBe(50);
    });
    it('returns 0 at p10', () => {
      expect(scoreRiverStage(1.0, baseline, true)).toBe(0);
    });
    it('interpolates between p25 and p50', () => {
      const score = scoreRiverStage(2.0, baseline, true)!;
      expect(score).toBeGreaterThan(50);
      expect(score).toBeLessThan(100);
    });
    it('interpolates between p10 and p25', () => {
      const score = scoreRiverStage(1.25, baseline, true)!;
      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThan(50);
    });
    it('returns 0 below p10', () => {
      expect(scoreRiverStage(0.5, baseline, true)).toBe(0);
    });
  });

  describe('null handling', () => {
    it('returns null for null stage', () => {
      expect(scoreRiverStage(null, baseline, false)).toBeNull();
    });
    it('returns null for null baseline', () => {
      expect(scoreRiverStage(3.0, null, false)).toBeNull();
    });
    it('returns null for low sampleCount', () => {
      const sparse = { ...baseline, sampleCount: 30 };
      expect(scoreRiverStage(3.0, sparse, false)).toBeNull();
    });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/lib/scoring-cdec.test.ts`
Expected: FAIL -- `scoreRiverStage` is not exported from scoring.js

- [ ] **Step 3: Add the StageBaseline type and scoreRiverStage function**

Add to `api/src/lib/scoring.ts` after the `scoreReservoirLevel` function (after line 156):

```typescript
export interface StageBaseline {
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  sampleCount: number;
}

const MIN_STAGE_SAMPLES = 60;

export function scoreRiverStage(
  stageFt: number | null,
  baseline: StageBaseline | null,
  inverted: boolean,
): number | null {
  if (stageFt === null || stageFt === undefined) return null;
  if (baseline === null || baseline.sampleCount < MIN_STAGE_SAMPLES) return null;
  if (inverted) {
    return linearScoreInverted(stageFt, baseline.p50, baseline.p25, baseline.p10);
  }
  return linearScore(stageFt, baseline.p50, baseline.p75, baseline.p90);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/lib/scoring-cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Add `riverStageInverted` to ProfileConfig and extend ScoreInput**

In `api/src/lib/scoring.ts`, update the `ProfileConfig` interface (line 69-74):

```typescript
export interface ProfileConfig {
  curves: Record<string, Curve>;
  tempCurve: TempCurve;
  weights: Record<string, number>;
  vetoes: VetoThresholds;
  riverStageInverted?: boolean;
}
```

Add to the `ScoreInput` interface (after the CDEC additions comment block, before the closing `}`):

```typescript
  riverStageFt?: number | null;
  stageBaseline?: StageBaseline | null;
```

- [ ] **Step 6: Verify build**

Run: `cd api && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 7: Commit**

```bash
cd api && git add src/lib/scoring.ts tests/lib/scoring-cdec.test.ts
git commit -m "feat: add scoreRiverStage function with percentile-based scoring"
```

---

### Task 3: River Stage Veto and Composite Scoring (TDD)

**Files:**
- Modify: `api/src/lib/scoring.ts` (add veto + factor in `computePaddleScore`, lines 327-343)
- Modify: `api/tests/lib/scoring-integration.test.ts` (add integration tests)

- [ ] **Step 1: Write the failing integration tests**

Add to `api/tests/lib/scoring-integration.test.ts`. First, read the file to understand the existing test patterns (base input shape, profile construction, etc.), then add:

```typescript
describe('river stage scoring', () => {
  const stageBaseline = { p10: 1.0, p25: 1.5, p50: 2.5, p75: 4.0, p90: 6.0, p95: 8.0, sampleCount: 150 };

  it('triggers NO_GO veto when stage >= p95', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 8.5,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 } },
    });
    expect(result.rating).toBe('NO_GO');
    expect(result.vetoed).toBe(true);
    expect(result.vetoReason).toBe('Dangerous water level');
  });

  it('triggers NO_GO veto for racing profiles at p95', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 8.0,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 }, riverStageInverted: true },
    });
    expect(result.rating).toBe('NO_GO');
    expect(result.vetoed).toBe(true);
  });

  it('includes river_stage factor for river water bodies', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 2.5,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 } },
    });
    expect(result.factors.river_stage).toBe(100);
  });

  it('scores high stage unfavorably for normal profiles', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 5.0,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 } },
    });
    expect(result.factors.river_stage).toBeGreaterThan(0);
    expect(result.factors.river_stage).toBeLessThan(50);
  });

  it('scores high stage favorably for inverted profiles', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 5.0,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 }, riverStageInverted: true },
    });
    expect(result.factors.river_stage).toBe(100);
  });

  it('excludes river_stage for reservoir water bodies', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'reservoir',
      riverStageFt: 2.5,
      stageBaseline,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 } },
    });
    expect(result.factors.river_stage).toBeUndefined();
  });

  it('excludes river_stage when baseline is null', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterBodyType: 'river',
      riverStageFt: 2.5,
      stageBaseline: null,
      profile: { ...baseInput.profile, weights: { ...baseInput.profile.weights, river_stage: 0.10 } },
    });
    expect(result.factors.river_stage).toBeUndefined();
    expect(result.missingFactors).toContain('river_stage');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/lib/scoring-integration.test.ts`
Expected: FAIL -- river_stage not handled in computePaddleScore

- [ ] **Step 3: Add river stage veto and factor to computePaddleScore**

In `api/src/lib/scoring.ts`, in the `computePaddleScore` function:

**Add river stage veto** after the dam release veto (after line 330). Insert before the reservoir level section:

```typescript
  // River stage veto (universal - all profiles)
  if (input.riverStageFt != null && input.stageBaseline != null &&
      input.stageBaseline.sampleCount >= 60 &&
      input.riverStageFt >= input.stageBaseline.p95) {
    return { value: 0, rating: 'NO_GO', limitingFactor: null, factors: {}, missingFactors: [], vetoed: true, vetoReason: 'Dangerous water level' };
  }
```

**Add river stage factor scoring** after the water quality section (after line 343). Insert before the "if Object.keys" check:

```typescript
  // River stage (rivers only)
  if (input.waterBodyType === 'river' && profile.weights.river_stage) {
    const rs = scoreRiverStage(
      input.riverStageFt ?? null,
      input.stageBaseline ?? null,
      profile.riverStageInverted ?? false,
    );
    if (rs !== null) { factorScores.river_stage = rs; }
    else if (input.riverStageFt != null) { missingFactors.push('river_stage'); }
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/lib/scoring-integration.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Run full scoring test suite**

Run: `cd api && npx vitest run tests/lib/scoring.test.ts tests/lib/scoring-cdec.test.ts tests/lib/scoring-integration.test.ts`
Expected: All tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
cd api && git add src/lib/scoring.ts tests/lib/scoring-integration.test.ts
git commit -m "feat: add river stage veto and factor scoring in computePaddleScore"
```

---

### Task 4: Profile Weights

**Files:**
- Modify: `api/src/lib/profiles.ts` (add `river_stage` weight and `riverStageInverted` to all 6 profiles)

- [ ] **Step 1: Add river_stage to all profiles**

In `api/src/lib/profiles.ts`, update each profile:

**SUP recreational** (line ~26, in weights):
```typescript
    river_stage: 0.10,
```
No `riverStageInverted` needed (defaults to false = normal direction).

**SUP racing** (line ~46, in weights):
```typescript
    river_stage: 0.10,
```
Add after the weights object closing:
```typescript
    riverStageInverted: true,
```

**SUP family** (line ~65, in weights):
```typescript
    river_stage: 0.15,
```
No `riverStageInverted` (defaults to false).

**Kayak flatwater** (line ~86, in weights):
```typescript
    river_stage: 0.10,
```
No `riverStageInverted` (defaults to false).

**Kayak river** (line ~105, in weights):
```typescript
    river_stage: 0.15,
```
Add:
```typescript
    riverStageInverted: true,
```

**Kayak ocean** (line ~124, in weights):
```typescript
    river_stage: 0.0,
```
No `riverStageInverted` needed (weight is 0, never used).

- [ ] **Step 2: Verify build**

Run: `cd api && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Run scoring tests to verify no regressions**

Run: `cd api && npx vitest run tests/lib/`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd api && git add src/lib/profiles.ts
git commit -m "feat: add river_stage weights to all profiles"
```

---

### Task 5: Historical Stage Fetch and Baseline Computation (TDD)

**Files:**
- Modify: `api/src/services/cdec.ts` (add `fetchCdecHistoricalStage` and `computeStageBaseline`)
- Modify: `api/tests/services/cdec.test.ts` (add tests)

- [ ] **Step 1: Write the failing tests for fetchCdecHistoricalStage**

Add to `api/tests/services/cdec.test.ts`:

```typescript
import {
  fetchCdecWaterTemp,
  fetchCdecFlow,
  fetchCdecRiverStage,
  fetchCdecReservoirData,
  fetchCdecWaterQuality,
  fetchCdecWind,
  fetchCdecAirTemp,
  fetchCdecHistoricalStage,
  computeStageBaseline,
} from '../../src/services/cdec.js';

// ... inside the main describe block, after existing tests:

  describe('fetchCdecHistoricalStage', () => {
    it('fetches daily stage data with dur_code D', async () => {
      mockFetchJson([
        record(1, 2.5, '2024-06-15 00:00'),
        record(1, 2.6, '2024-06-16 00:00'),
      ]);
      const data = await fetchCdecHistoricalStage('AFO', 5);
      expect(data).toHaveLength(2);
      expect(data[0]).toEqual({ date: '2024-06-15 00:00', value: 2.5 });
      expect(data[1]).toEqual({ date: '2024-06-16 00:00', value: 2.6 });

      // Verify dur_code=D was used
      const url = (globalThis.fetch as any).mock.calls[0][0] as string;
      expect(url).toContain('dur_code=D');
    });

    it('filters out bad data flags', async () => {
      mockFetchJson([
        record(1, 2.5, '2024-06-15 00:00'),
        record(1, 999.9, '2024-06-16 00:00', 'N'),
        record(1, 2.7, '2024-06-17 00:00'),
      ]);
      const data = await fetchCdecHistoricalStage('AFO', 5);
      expect(data).toHaveLength(2);
    });

    it('returns empty array for no data', async () => {
      mockFetchJson([]);
      const data = await fetchCdecHistoricalStage('AFO', 5);
      expect(data).toEqual([]);
    });
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: FAIL -- `fetchCdecHistoricalStage` is not exported

- [ ] **Step 3: Implement fetchCdecHistoricalStage**

Add to `api/src/services/cdec.ts` after the existing fetch functions (after `fetchCdecAirTemp`):

```typescript
export interface HistoricalStageRecord {
  date: string;
  value: number;
}

/**
 * Fetch historical daily stage data for baseline computation.
 * Uses dur_code=D for daily averages over the specified number of years.
 */
export async function fetchCdecHistoricalStage(
  stationId: string,
  years: number,
): Promise<HistoricalStageRecord[]> {
  const end = new Date();
  const start = new Date(end);
  start.setFullYear(start.getFullYear() - years);

  const fmt = (d: Date) => d.toISOString().split('T')[0];

  const params = new URLSearchParams({
    Stations: stationId,
    SensorNums: String(SENSOR_RIVER_STAGE),
    dur_code: 'D',
    Start: fmt(start),
    End: fmt(end),
  });

  const res = await fetch(`${CDEC_URL}?${params}`);
  if (!res.ok) {
    throw new Error(`CDEC API error: ${res.status}`);
  }

  const records: CdecRecord[] = await res.json();
  return records
    .filter((r) => r.SENSOR_NUM === SENSOR_RIVER_STAGE && !BAD_FLAGS.has(r.dataFlag.trim()))
    .map((r) => ({ date: r.obsDate, value: r.value }));
}
```

Note: `BAD_FLAGS` is the existing Set used by `latestValue`. If it's defined inside `latestValue`, extract it to module scope first:

```typescript
const BAD_FLAGS = new Set(['N', 'v']);
```

Check the existing code -- if `BAD_FLAGS` is already at module scope, reuse it. If the filtering is inline in `latestValue`, extract it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Write the failing tests for computeStageBaseline**

Add to `api/tests/services/cdec.test.ts`:

```typescript
  describe('computeStageBaseline', () => {
    it('computes monthly percentiles from daily data', async () => {
      // Generate 150 records for January (5 years * 31 days = ~155)
      const janRecords: ReturnType<typeof record>[] = [];
      for (let i = 0; i < 150; i++) {
        const day = (i % 31) + 1;
        const year = 2021 + Math.floor(i / 31);
        const dayStr = String(day).padStart(2, '0');
        // Values from 1.0 to 15.0 spread linearly so percentiles are predictable
        janRecords.push(record(1, 1.0 + (i / 149) * 14.0, `${year}-01-${dayStr} 00:00`));
      }
      mockFetchJson(janRecords);

      const baselines = await computeStageBaseline('AFO', 5);
      const jan = baselines.find((b) => b.month === 1)!;

      expect(jan).toBeDefined();
      expect(jan.sampleCount).toBe(150);
      expect(jan.p10).toBeGreaterThan(1.0);
      expect(jan.p50).toBeCloseTo(8.0, 0);
      expect(jan.p90).toBeLessThan(15.0);
      expect(jan.p95).toBeLessThan(15.0);
      expect(jan.p10).toBeLessThan(jan.p25);
      expect(jan.p25).toBeLessThan(jan.p50);
      expect(jan.p50).toBeLessThan(jan.p75);
      expect(jan.p75).toBeLessThan(jan.p90);
      expect(jan.p90).toBeLessThan(jan.p95);
    });

    it('returns entries for each month with data', async () => {
      const records: ReturnType<typeof record>[] = [];
      // 10 records each for Jan, Feb, Mar
      for (let m = 1; m <= 3; m++) {
        for (let i = 0; i < 10; i++) {
          const monthStr = String(m).padStart(2, '0');
          records.push(record(1, 1.0 + i, `2024-${monthStr}-${i + 1} 00:00`));
        }
      }
      mockFetchJson(records);

      const baselines = await computeStageBaseline('AFO', 5);
      expect(baselines).toHaveLength(3);
      expect(baselines.map((b) => b.month).sort()).toEqual([1, 2, 3]);
    });

    it('returns empty array for no data', async () => {
      mockFetchJson([]);
      const baselines = await computeStageBaseline('AFO', 5);
      expect(baselines).toEqual([]);
    });
  });
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: FAIL -- `computeStageBaseline` not exported

- [ ] **Step 7: Implement computeStageBaseline**

Add to `api/src/services/cdec.ts`:

```typescript
export interface StageBaselineRow {
  stationId: string;
  month: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  sampleCount: number;
}

function percentile(sorted: number[], p: number): number {
  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

/**
 * Compute monthly stage percentiles from historical CDEC daily data.
 * Returns one row per month that has data.
 */
export async function computeStageBaseline(
  stationId: string,
  years: number,
): Promise<StageBaselineRow[]> {
  const records = await fetchCdecHistoricalStage(stationId, years);
  if (records.length === 0) return [];

  // Group by month
  const byMonth = new Map<number, number[]>();
  for (const r of records) {
    // Parse month from CDEC date format "YYYY-M-D HH:MM" or "YYYY-MM-DD HH:MM"
    const parts = r.date.split('-');
    const month = parseInt(parts[1], 10);
    if (!byMonth.has(month)) byMonth.set(month, []);
    byMonth.get(month)!.push(r.value);
  }

  const results: StageBaselineRow[] = [];
  for (const [month, values] of byMonth) {
    values.sort((a, b) => a - b);
    results.push({
      stationId,
      month,
      p10: Math.round(percentile(values, 10) * 100) / 100,
      p25: Math.round(percentile(values, 25) * 100) / 100,
      p50: Math.round(percentile(values, 50) * 100) / 100,
      p75: Math.round(percentile(values, 75) * 100) / 100,
      p90: Math.round(percentile(values, 90) * 100) / 100,
      p95: Math.round(percentile(values, 95) * 100) / 100,
      sampleCount: values.length,
    });
  }

  return results.sort((a, b) => a.month - b.month);
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
cd api && git add src/services/cdec.ts tests/services/cdec.test.ts
git commit -m "feat: add fetchCdecHistoricalStage and computeStageBaseline"
```

---

### Task 6: Conditions Service Integration

**Files:**
- Modify: `api/src/services/conditions.ts` (look up baseline, pass to scoring)

- [ ] **Step 1: Add import for schema and StageBaseline type**

At the top of `api/src/services/conditions.ts`, add to the existing imports:

```typescript
import { cdecStageBaselines } from '../db/schema.js';
import type { StageBaseline } from '../lib/scoring.js';
```

- [ ] **Step 2: Add baseline lookup in getWaterData()**

After the river stage fetching section (after the `if (cdecStage != null) riverStageFt = cdecStage;` line around line 804), add baseline lookup:

```typescript
          // Look up stage baseline for scoring
          if (cdecStage != null) {
            const baselineKey = `cdec:${cdecStationId}:stage-baseline`;
            let cachedBaseline = this.cache.get(baselineKey) as StageBaseline | null | undefined;
            if (cachedBaseline === undefined) {
              const currentMonth = new Date().getMonth() + 1;
              const rows = await this.db.select().from(cdecStageBaselines)
                .where(and(
                  eq(cdecStageBaselines.stationId, cdecStationId),
                  eq(cdecStageBaselines.month, currentMonth),
                ))
                .limit(1);
              cachedBaseline = rows.length > 0
                ? { p10: rows[0].p10, p25: rows[0].p25, p50: rows[0].p50, p75: rows[0].p75, p90: rows[0].p90, p95: rows[0].p95, sampleCount: rows[0].sampleCount }
                : null;
              this.cache.set(baselineKey, cachedBaseline, TTL_WATER_TEMP); // 24h TTL
            }
            if (cachedBaseline) stageBaseline = cachedBaseline;
          }
```

Also add the `stageBaseline` variable declaration near where `riverStageFt` is declared in `getWaterData()`:

```typescript
let stageBaseline: StageBaseline | null = null;
```

And include it in the return value of `getWaterData()` alongside `riverStageFt`:

```typescript
stageBaseline,
```

- [ ] **Step 3: Pass stageBaseline to computePaddleScore**

In the `computePaddleScore` call (around line 561-581), add:

```typescript
      riverStageFt: water.riverStageFt ?? null,
      stageBaseline: water.stageBaseline ?? null,
```

- [ ] **Step 4: Add `eq` and `and` to drizzle-orm import if not already there**

Check the imports at top of conditions.ts. `eq` and `and` should already be imported from `drizzle-orm` (line 8). Verify `eq` and `and` are present.

- [ ] **Step 5: Verify build**

Run: `cd api && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Run full test suite**

Run: `cd api && npx vitest run`
Expected: All tests PASS (or only the 3 pre-existing unrelated failures)

- [ ] **Step 7: Commit**

```bash
cd api && git add src/services/conditions.ts
git commit -m "feat: look up stage baselines and pass to scoring engine"
```

---

### Task 7: Apply Migration and Populate Baselines

This task applies the migration to test and production databases and populates initial baselines for AFO and CBR stations.

- [ ] **Step 1: Apply migration to test database**

Run the migration SQL against the test database:

```bash
cd api && mysql -u root paddle_conditions_test < src/db/migrations/0008_river_stage_baselines.sql
```

(Adjust credentials as needed for the test database.)

- [ ] **Step 2: Run full test suite to verify**

Run: `cd api && npx vitest run`
Expected: All tests PASS (or only the 3 pre-existing unrelated failures)

- [ ] **Step 3: Apply migration to production**

SSH to production and run the migration:

```bash
ssh -i ~/.ssh/paddleconditions_prod -p 11208 user@server
mysql -u paddle_user paddle_conditions < 0008_river_stage_baselines.sql
```

- [ ] **Step 4: Write a one-time script to populate baselines**

Create `api/scripts/populate-stage-baselines.ts`:

```typescript
import { computeStageBaseline } from '../src/services/cdec.js';

const STATIONS = ['AFO', 'CBR'];

async function main() {
  for (const stationId of STATIONS) {
    console.log(`Computing baseline for ${stationId}...`);
    const baselines = await computeStageBaseline(stationId, 5);
    console.log(`  Got ${baselines.length} months:`);
    for (const b of baselines) {
      console.log(`  Month ${b.month}: p10=${b.p10} p25=${b.p25} p50=${b.p50} p75=${b.p75} p90=${b.p90} p95=${b.p95} (n=${b.sampleCount})`);
    }
    // Output SQL for insertion
    for (const b of baselines) {
      console.log(`INSERT INTO cdec_stage_baselines (station_id, month, p10, p25, p50, p75, p90, p95, sample_count) VALUES ('${stationId}', ${b.month}, ${b.p10}, ${b.p25}, ${b.p50}, ${b.p75}, ${b.p90}, ${b.p95}, ${b.sampleCount}) ON DUPLICATE KEY UPDATE p10=${b.p10}, p25=${b.p25}, p50=${b.p50}, p75=${b.p75}, p90=${b.p90}, p95=${b.p95}, sample_count=${b.sampleCount}, computed_at=NOW();`);
    }
  }
}

main().catch(console.error);
```

Run: `cd api && npx tsx scripts/populate-stage-baselines.ts`

Review the output. If the percentiles look reasonable (stage values in feet, generally 1-20 range for CA rivers), apply the generated SQL to both test and production databases.

- [ ] **Step 5: Commit the script**

```bash
cd api && git add scripts/populate-stage-baselines.ts
git commit -m "feat: add one-time script to populate stage baselines from CDEC"
```

---

### Task 8: Deploy and Update TPP

- [ ] **Step 1: Build and deploy to production**

```bash
cd api && npm run build
rsync -avz --delete dist/ user@server:~/public_html/api.paddleconditions.com/dist/ -e "ssh -i ~/.ssh/paddleconditions_prod -p 11208"
ssh -i ~/.ssh/paddleconditions_prod -p 11208 user@server "touch ~/public_html/api.paddleconditions.com/tmp/restart.txt"
```

- [ ] **Step 2: Verify production**

Test that the API returns river stage data and scoring for a CA river water body. Check:
- `riverStageFt` is present in the response
- `factors.river_stage` appears in the scoring output
- No errors in production logs

- [ ] **Step 3: Update the TPP**

In `_todo/20260406-cdec-integration.md`:
- Check off `[x] River stage scoring`
- Add session notes about what was done
- Update lore with any new discoveries

- [ ] **Step 4: Update changelog**

Add entry to `website/data/changelog.json` describing the river stage scoring feature.

- [ ] **Step 5: Commit changelog and TPP updates**

```bash
git add _todo/20260406-cdec-integration.md
cd website && git add data/changelog.json && git commit -m "docs: add river stage scoring to changelog"
```
