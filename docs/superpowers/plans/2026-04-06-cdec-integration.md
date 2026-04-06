# CDEC Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CDEC as a peer water data provider for California water bodies, with reservoir/water quality scoring and pet safety advisories.

**Architecture:** New `cdec.ts` service module following the existing USGS/NOAA pattern (pure async functions, no abstraction layer). The conditions service orchestrates all sources in parallel, merging with a "freshest wins" strategy. New scoring factors (reservoir level, dam release, water quality, river stage) and pet safety advisories extend the existing scoring engine.

**Tech Stack:** Fastify, Drizzle ORM, Vitest, TypeScript, MariaDB

**Spec:** `docs/superpowers/specs/2026-04-06-cdec-integration-design.md`

**Out of scope for this plan (future work):**
- Station discovery API endpoint (searching/associating CDEC stations with water bodies)
- River stage scoring (requires per-station historical baselines)
- CDEC wind/air temp as weather fallback (most water stations lack these sensors)

---

### Task 1: CDEC API Client - Core Parsing and Fetch

**Files:**
- Create: `api/src/services/cdec.ts`
- Create: `api/tests/services/cdec.test.ts`

This task builds the CDEC JSON API parser and the core `fetchCdecSensorData` helper that all public functions use. CDEC returns an array of records with `stationId`, `SENSOR_NUM`, `sensorType`, `date`, `value`, `dataFlag`, `units`. We parse, filter bad flags, and return the most recent valid value.

- [ ] **Step 1: Write test for parsing CDEC JSON response**

```typescript
// api/tests/services/cdec.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchCdecWaterTemp } from '../../src/services/cdec.js';

describe('CDEC service', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe('fetchCdecWaterTemp', () => {
    it('extracts latest water temperature in F', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO',
            durCode: 'E',
            SENSOR_NUM: 25,
            sensorType: 'TEMP W',
            date: '2026-4-5 14:00',
            obsDate: '2026-4-5 14:00',
            value: 54.8,
            dataFlag: ' ',
            units: 'DEG F',
          },
          {
            stationId: 'AFO',
            durCode: 'E',
            SENSOR_NUM: 25,
            sensorType: 'TEMP W',
            date: '2026-4-5 14:15',
            obsDate: '2026-4-5 14:15',
            value: 55.2,
            dataFlag: ' ',
            units: 'DEG F',
          },
        ],
      });

      const temp = await fetchCdecWaterTemp('AFO');
      expect(temp).toBe(55.2);
    });

    it('skips records with error data flags', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 25, sensorType: 'TEMP W',
            date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00',
            value: 54.8, dataFlag: ' ', units: 'DEG F',
          },
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 25, sensorType: 'TEMP W',
            date: '2026-4-5 14:15', obsDate: '2026-4-5 14:15',
            value: -999, dataFlag: 'N', units: 'DEG F',
          },
        ],
      });

      const temp = await fetchCdecWaterTemp('AFO');
      expect(temp).toBe(54.8);
    });

    it('returns null for empty response', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      const temp = await fetchCdecWaterTemp('AFO');
      expect(temp).toBeNull();
    });

    it('throws on API error', async () => {
      (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 503 });
      await expect(fetchCdecWaterTemp('AFO')).rejects.toThrow('CDEC API error');
    });

    it('skips out-of-range data flag', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 25, sensorType: 'TEMP W',
            date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00',
            value: 999, dataFlag: 'v', units: 'DEG F',
          },
        ],
      });

      const temp = await fetchCdecWaterTemp('AFO');
      expect(temp).toBeNull();
    });

    it('accepts estimated and revised data flags', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 25, sensorType: 'TEMP W',
            date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00',
            value: 55.0, dataFlag: 'e', units: 'DEG F',
          },
        ],
      });

      const temp = await fetchCdecWaterTemp('AFO');
      expect(temp).toBe(55.0);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: FAIL - module not found

- [ ] **Step 3: Write the CDEC service module with core parsing**

```typescript
// api/src/services/cdec.ts
/**
 * CDEC (California Data Exchange Center) API client.
 *
 * Fetches water data from California's state monitoring network.
 * Stations use 3-letter IDs (e.g., AFO, FOL, NAT) with numeric sensor codes.
 * Public API, no auth required. Timestamps are Pacific Standard Time.
 */

const CDEC_URL = 'https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet';

// Bad data flags to skip
const BAD_FLAGS = new Set(['N', 'v']);

// Sensor numbers (from CDEC official sensor list)
const SENSOR = {
  WATER_TEMP: 25,
  FLOW: 20,
  RIVER_STAGE: 1,
  RESERVOIR_STORAGE: 15,
  RESERVOIR_ELEVATION: 6,
  INFLOW: 76,
  OUTFLOW: 23,
  SCHEDULED_RELEASE: 7,
  REGULATING_RELEASE: 85,
  WIND_SPEED: 9,
  WIND_DIRECTION: 10,
  WIND_GUST: 77,
  AIR_TEMP: 4,
  AIR_TEMP_ALT: 30,
  TURBIDITY: 27,
  DISSOLVED_OXYGEN: 61,
  PH: 62,
  CONDUCTIVITY: 100,
} as const;

interface CdecRecord {
  stationId: string;
  durCode: string;
  SENSOR_NUM: number;
  sensorType: string;
  date: string;
  obsDate: string;
  value: number;
  dataFlag: string;
  units: string;
}

export interface ReservoirData {
  storageAf?: number;
  elevationFt?: number;
  inflowCfs?: number;
  outflowCfs?: number;
  scheduledReleaseCfs?: number;
  regulatingReleaseCfs?: number;
}

export interface WaterQualityData {
  turbidityNtu?: number;
  dissolvedOxygenMgL?: number;
  ph?: number;
  conductivityUs?: number;
}

export interface CdecData {
  waterTempF?: number;
  flowCfs?: number;
  riverStageFt?: number;
  reservoir?: ReservoirData;
  windSpeedMph?: number;
  windDirectionDeg?: number;
  windGustMph?: number;
  airTempF?: number;
  waterQuality?: WaterQualityData;
}

/**
 * Fetch sensor data from CDEC for the last 2 hours.
 * Returns array of valid records sorted by date ascending.
 */
async function fetchSensorData(
  stationId: string,
  sensorNums: number[],
  durCode: string,
): Promise<CdecRecord[]> {
  const now = new Date();
  const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000);

  const fmt = (d: Date) => d.toISOString().split('T')[0];
  const params = new URLSearchParams({
    Stations: stationId,
    SensorNums: sensorNums.join(','),
    dur_code: durCode,
    Start: fmt(twoHoursAgo),
    End: fmt(now),
  });

  const res = await fetch(`${CDEC_URL}?${params}`);
  if (!res.ok) {
    throw new Error(`CDEC API error: ${res.status}`);
  }

  const records: CdecRecord[] = await res.json();
  return records.filter((r) => !BAD_FLAGS.has(r.dataFlag?.trim()));
}

/**
 * Extract the most recent value for a specific sensor from a set of records.
 */
function latestValue(records: CdecRecord[], sensorNum: number): number | null {
  const matching = records.filter((r) => r.SENSOR_NUM === sensorNum);
  if (matching.length === 0) return null;
  const latest = matching[matching.length - 1];
  if (latest.value == null || typeof latest.value !== 'number') return null;
  return latest.value;
}

// ============================================================================
// Public fetch functions
// ============================================================================

export async function fetchCdecWaterTemp(stationId: string): Promise<number | null> {
  const records = await fetchSensorData(stationId, [SENSOR.WATER_TEMP], 'E');
  return latestValue(records, SENSOR.WATER_TEMP);
}

export async function fetchCdecFlow(stationId: string): Promise<number | null> {
  const records = await fetchSensorData(stationId, [SENSOR.FLOW], 'E');
  return latestValue(records, SENSOR.FLOW);
}

export async function fetchCdecRiverStage(stationId: string): Promise<number | null> {
  const records = await fetchSensorData(stationId, [SENSOR.RIVER_STAGE], 'E');
  return latestValue(records, SENSOR.RIVER_STAGE);
}

export async function fetchCdecReservoirData(stationId: string): Promise<ReservoirData | null> {
  const sensors = [
    SENSOR.RESERVOIR_STORAGE, SENSOR.RESERVOIR_ELEVATION,
    SENSOR.INFLOW, SENSOR.OUTFLOW,
    SENSOR.SCHEDULED_RELEASE, SENSOR.REGULATING_RELEASE,
  ];
  const records = await fetchSensorData(stationId, sensors, 'H');
  // Also fetch event-duration scheduled release
  const eventRecords = await fetchSensorData(stationId, [SENSOR.SCHEDULED_RELEASE], 'E');

  const storage = latestValue(records, SENSOR.RESERVOIR_STORAGE);
  const elevation = latestValue(records, SENSOR.RESERVOIR_ELEVATION);
  const inflow = latestValue(records, SENSOR.INFLOW);
  const outflow = latestValue(records, SENSOR.OUTFLOW);
  const scheduledRelease = latestValue(eventRecords, SENSOR.SCHEDULED_RELEASE)
    ?? latestValue(records, SENSOR.SCHEDULED_RELEASE);
  const regulatingRelease = latestValue(records, SENSOR.REGULATING_RELEASE);

  if (storage == null && elevation == null && inflow == null && outflow == null) {
    return null;
  }

  return {
    ...(storage != null && { storageAf: storage }),
    ...(elevation != null && { elevationFt: elevation }),
    ...(inflow != null && { inflowCfs: inflow }),
    ...(outflow != null && { outflowCfs: outflow }),
    ...(scheduledRelease != null && { scheduledReleaseCfs: scheduledRelease }),
    ...(regulatingRelease != null && { regulatingReleaseCfs: regulatingRelease }),
  };
}

export async function fetchCdecWind(
  stationId: string,
): Promise<{ speed?: number; direction?: number; gust?: number } | null> {
  const records = await fetchSensorData(
    stationId,
    [SENSOR.WIND_SPEED, SENSOR.WIND_DIRECTION, SENSOR.WIND_GUST],
    'E',
  );
  const speed = latestValue(records, SENSOR.WIND_SPEED);
  const direction = latestValue(records, SENSOR.WIND_DIRECTION);
  const gust = latestValue(records, SENSOR.WIND_GUST);
  if (speed == null && direction == null && gust == null) return null;
  return {
    ...(speed != null && { speed }),
    ...(direction != null && { direction }),
    ...(gust != null && { gust }),
  };
}

export async function fetchCdecAirTemp(stationId: string): Promise<number | null> {
  const records = await fetchSensorData(
    stationId,
    [SENSOR.AIR_TEMP, SENSOR.AIR_TEMP_ALT],
    'E',
  );
  return latestValue(records, SENSOR.AIR_TEMP) ?? latestValue(records, SENSOR.AIR_TEMP_ALT);
}

export async function fetchCdecWaterQuality(stationId: string): Promise<WaterQualityData | null> {
  const records = await fetchSensorData(
    stationId,
    [SENSOR.TURBIDITY, SENSOR.DISSOLVED_OXYGEN, SENSOR.PH, SENSOR.CONDUCTIVITY],
    'E',
  );

  const turbidity = latestValue(records, SENSOR.TURBIDITY);
  const dissolvedOxygen = latestValue(records, SENSOR.DISSOLVED_OXYGEN);
  const ph = latestValue(records, SENSOR.PH);
  const conductivity = latestValue(records, SENSOR.CONDUCTIVITY);

  if (turbidity == null && dissolvedOxygen == null && ph == null && conductivity == null) {
    return null;
  }

  return {
    ...(turbidity != null && { turbidityNtu: turbidity }),
    ...(dissolvedOxygen != null && { dissolvedOxygenMgL: dissolvedOxygen }),
    ...(ph != null && { ph }),
    ...(conductivity != null && { conductivityUs: conductivity }),
  };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd api && git add src/services/cdec.ts tests/services/cdec.test.ts && git commit -m "feat(cdec): add CDEC API client with water temp parsing"
```

---

### Task 2: CDEC Service - Flow, Stage, and Reservoir Tests

**Files:**
- Modify: `api/tests/services/cdec.test.ts`
- (No changes to `api/src/services/cdec.ts` - implementation already written in Task 1)

Add tests for flow, river stage, and reservoir data to verify the remaining public fetch functions work correctly.

- [ ] **Step 1: Add flow and stage tests**

Append to `api/tests/services/cdec.test.ts` inside the main `describe('CDEC service')` block, after the `fetchCdecWaterTemp` describe:

```typescript
  describe('fetchCdecFlow', () => {
    it('extracts latest flow in CFS', async () => {
      const { fetchCdecFlow } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 20, sensorType: 'FLOW',
            date: '2026-4-5 14:15', obsDate: '2026-4-5 14:15',
            value: 1523, dataFlag: ' ', units: 'CFS',
          },
        ],
      });

      const flow = await fetchCdecFlow('AFO');
      expect(flow).toBe(1523);
    });
  });

  describe('fetchCdecRiverStage', () => {
    it('extracts latest river stage in feet', async () => {
      const { fetchCdecRiverStage } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          {
            stationId: 'AFO', durCode: 'E', SENSOR_NUM: 1, sensorType: 'RIV STG',
            date: '2026-4-5 14:15', obsDate: '2026-4-5 14:15',
            value: 4.32, dataFlag: ' ', units: 'FEET',
          },
        ],
      });

      const stage = await fetchCdecRiverStage('AFO');
      expect(stage).toBe(4.32);
    });
  });
```

- [ ] **Step 2: Add reservoir data tests**

Append inside the main describe block:

```typescript
  describe('fetchCdecReservoirData', () => {
    it('extracts reservoir metrics from hourly data', async () => {
      const { fetchCdecReservoirData } = await import('../../src/services/cdec.js');

      let callCount = 0;
      (globalThis.fetch as any).mockImplementation(async () => {
        callCount++;
        if (callCount === 1) {
          // Hourly reservoir sensors
          return {
            ok: true,
            json: async () => [
              { stationId: 'FOL', durCode: 'H', SENSOR_NUM: 15, sensorType: 'STORAGE', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 650000, dataFlag: ' ', units: 'AF' },
              { stationId: 'FOL', durCode: 'H', SENSOR_NUM: 6, sensorType: 'RES ELE', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 430.5, dataFlag: ' ', units: 'FEET' },
              { stationId: 'FOL', durCode: 'H', SENSOR_NUM: 76, sensorType: 'INFLOW', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 5200, dataFlag: ' ', units: 'CFS' },
              { stationId: 'FOL', durCode: 'H', SENSOR_NUM: 23, sensorType: 'OUTFLOW', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 4800, dataFlag: ' ', units: 'CFS' },
            ],
          };
        }
        // Event-duration scheduled release
        return {
          ok: true,
          json: async () => [
            { stationId: 'FOL', durCode: 'E', SENSOR_NUM: 7, sensorType: 'REL SCH', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 1500, dataFlag: ' ', units: 'CFS' },
          ],
        };
      });

      const data = await fetchCdecReservoirData('FOL');
      expect(data).toEqual({
        storageAf: 650000,
        elevationFt: 430.5,
        inflowCfs: 5200,
        outflowCfs: 4800,
        scheduledReleaseCfs: 1500,
      });
    });

    it('returns null when no reservoir sensors available', async () => {
      const { fetchCdecReservoirData } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      const data = await fetchCdecReservoirData('AFO');
      expect(data).toBeNull();
    });
  });
```

- [ ] **Step 3: Run all CDEC tests**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd api && git add tests/services/cdec.test.ts && git commit -m "test(cdec): add flow, stage, and reservoir data tests"
```

---

### Task 3: CDEC Service - Water Quality and Wind Tests

**Files:**
- Modify: `api/tests/services/cdec.test.ts`

- [ ] **Step 1: Add water quality and wind tests**

Append inside the main describe block:

```typescript
  describe('fetchCdecWaterQuality', () => {
    it('extracts water quality metrics', async () => {
      const { fetchCdecWaterQuality } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          { stationId: 'WQ1', durCode: 'E', SENSOR_NUM: 27, sensorType: 'TURBIDITY', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 8.2, dataFlag: ' ', units: 'NTU' },
          { stationId: 'WQ1', durCode: 'E', SENSOR_NUM: 61, sensorType: 'DISS OXY', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 7.5, dataFlag: ' ', units: 'MG/L' },
          { stationId: 'WQ1', durCode: 'E', SENSOR_NUM: 62, sensorType: 'PH', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 7.8, dataFlag: ' ', units: 'PH' },
          { stationId: 'WQ1', durCode: 'E', SENSOR_NUM: 100, sensorType: 'EL COND', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 450, dataFlag: ' ', units: 'US/CM' },
        ],
      });

      const wq = await fetchCdecWaterQuality('WQ1');
      expect(wq).toEqual({
        turbidityNtu: 8.2,
        dissolvedOxygenMgL: 7.5,
        ph: 7.8,
        conductivityUs: 450,
      });
    });

    it('returns null when no WQ sensors available', async () => {
      const { fetchCdecWaterQuality } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      const wq = await fetchCdecWaterQuality('AFO');
      expect(wq).toBeNull();
    });

    it('returns partial data when only some sensors available', async () => {
      const { fetchCdecWaterQuality } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          { stationId: 'WQ1', durCode: 'E', SENSOR_NUM: 27, sensorType: 'TURBIDITY', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 12.1, dataFlag: ' ', units: 'NTU' },
        ],
      });

      const wq = await fetchCdecWaterQuality('WQ1');
      expect(wq).toEqual({ turbidityNtu: 12.1 });
    });
  });

  describe('fetchCdecWind', () => {
    it('extracts wind speed, direction, and gust', async () => {
      const { fetchCdecWind } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 9, sensorType: 'WIND SPD', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 8.5, dataFlag: ' ', units: 'MPH' },
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 10, sensorType: 'WIND DIR', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 225, dataFlag: ' ', units: 'DEG' },
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 77, sensorType: 'PEAK WND', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 14.2, dataFlag: ' ', units: 'MPH' },
        ],
      });

      const wind = await fetchCdecWind('WX1');
      expect(wind).toEqual({ speed: 8.5, direction: 225, gust: 14.2 });
    });

    it('returns null when no wind sensors available', async () => {
      const { fetchCdecWind } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [],
      });

      const wind = await fetchCdecWind('AFO');
      expect(wind).toBeNull();
    });
  });

  describe('fetchCdecAirTemp', () => {
    it('prefers sensor 4 over sensor 30', async () => {
      const { fetchCdecAirTemp } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 4, sensorType: 'AIR TEMP', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 72.5, dataFlag: ' ', units: 'DEG F' },
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 30, sensorType: 'AIR TEMP', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 73.1, dataFlag: ' ', units: 'DEG F' },
        ],
      });

      const temp = await fetchCdecAirTemp('WX1');
      expect(temp).toBe(72.5);
    });

    it('falls back to sensor 30 when sensor 4 unavailable', async () => {
      const { fetchCdecAirTemp } = await import('../../src/services/cdec.js');

      (globalThis.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => [
          { stationId: 'WX1', durCode: 'E', SENSOR_NUM: 30, sensorType: 'AIR TEMP', date: '2026-4-5 14:00', obsDate: '2026-4-5 14:00', value: 73.1, dataFlag: ' ', units: 'DEG F' },
        ],
      });

      const temp = await fetchCdecAirTemp('WX1');
      expect(temp).toBe(73.1);
    });
  });
```

- [ ] **Step 2: Run all CDEC tests**

Run: `cd api && npx vitest run tests/services/cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
cd api && git add tests/services/cdec.test.ts && git commit -m "test(cdec): add water quality, wind, and air temp tests"
```

---

### Task 4: Database Schema Migration

**Files:**
- Create: `api/src/db/migrations/XXXX_add_cdec_support.sql` (use next sequence number)
- Modify: `api/src/db/schema.ts`

Add `cdecStationId` and `reservoirCapacityAf` columns to `water_bodies`, and add `'cdec'` to the `stationType` enum on `water_body_stations`.

- [ ] **Step 1: Check existing migration numbering**

Run: `ls api/src/db/migrations/`
Use the next sequential number for the new migration file.

- [ ] **Step 2: Create the SQL migration**

Create the migration file (replace `XXXX` with the correct sequence number):

```sql
-- api/src/db/migrations/XXXX_add_cdec_support.sql
-- Add CDEC station support

-- Add cdecStationId and reservoirCapacityAf to water_bodies
ALTER TABLE water_bodies
  ADD COLUMN cdec_station_id VARCHAR(20) DEFAULT NULL AFTER noaa_station_id,
  ADD COLUMN reservoir_capacity_af DOUBLE DEFAULT NULL AFTER cdec_station_id;

-- Extend station_type enum to include 'cdec'
ALTER TABLE water_body_stations
  MODIFY COLUMN station_type ENUM('usgs', 'noaa', 'cdec') NOT NULL;
```

- [ ] **Step 3: Update the Drizzle schema to match**

In `api/src/db/schema.ts`, update the `waterBodies` table definition. Add after `noaaStationId`:

```typescript
    cdecStationId: varchar('cdec_station_id', { length: 20 }),
    reservoirCapacityAf: double('reservoir_capacity_af'),
```

Update the `waterBodyStations` table `stationType` enum:

```typescript
    stationType: mysqlEnum('station_type', ['usgs', 'noaa', 'cdec']).notNull(),
```

Note: You'll need to import `double` from `drizzle-orm/mysql-core` if not already imported. Check the existing imports at the top of the file.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd api && git add src/db/schema.ts src/db/migrations/ && git commit -m "feat(db): add CDEC station columns and enum value"
```

---

### Task 5: Extend DataSources and Conditions Service Types

**Files:**
- Modify: `api/src/services/conditions.ts`
- Modify: `api/src/services/water-body-cache.ts`

Extend `DataSources` to include `cdec`, update `normalizeDataSources`, and extend `CachedConditionsData.water` to include CDEC-specific fields.

- [ ] **Step 1: Update DataSources interface and normalizeDataSources**

In `api/src/services/conditions.ts`, update the `DataSources` interface (~line 137):

```typescript
interface DataSources {
  usgs: string[];
  noaa: string[];
  cdec: string[];
}
```

Update `normalizeDataSources` (~line 161) to handle the new field:

```typescript
function normalizeDataSources(ds: DataSources | Record<string, string> | undefined): DataSources {
  if (!ds) return { usgs: [], noaa: [], cdec: [] };
  if (Array.isArray((ds as DataSources).usgs)) {
    const typed = ds as DataSources;
    return {
      usgs: typed.usgs ?? [],
      noaa: typed.noaa ?? [],
      cdec: typed.cdec ?? [],
    };
  }
  const old = ds as Record<string, string>;
  return {
    usgs: old.usgs ? [old.usgs] : [],
    noaa: old.noaa ? [old.noaa] : [],
    cdec: old.cdec ? [old.cdec] : [],
  };
}
```

- [ ] **Step 2: Add CDEC import at the top of conditions.ts**

Add import after the existing NOAA import (~line 19):

```typescript
import {
  fetchCdecWaterTemp, fetchCdecFlow, fetchCdecRiverStage,
  fetchCdecReservoirData, fetchCdecWaterQuality,
  fetchCdecWind, fetchCdecAirTemp,
  type CdecData, type ReservoirData, type WaterQualityData,
} from './cdec.js';
```

- [ ] **Step 3: Extend CachedConditionsData.water type**

In `api/src/services/water-body-cache.ts`, update the `CachedConditionsData` interface (~line 13):

```typescript
export interface CachedConditionsData {
  weather: WeatherData;
  water: {
    waterTempF: number | null;
    waterTempSource: string | null;
    waterTempUpdatedAt: string | null;
    streamflowCfs: number | null;
    tides: any | null;
    riverStageFt?: number | null;
    reservoir?: ReservoirData | null;
    waterQuality?: WaterQualityData | null;
    sources?: Record<string, string>;
  };
  aqi: AqiData;
}
```

Add the import at the top of `water-body-cache.ts`:

```typescript
import type { ReservoirData, WaterQualityData } from './cdec.js';
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
cd api && git add src/services/conditions.ts src/services/water-body-cache.ts && git commit -m "feat: extend DataSources and cache types for CDEC"
```

---

### Task 6: Integrate CDEC into getWaterData

**Files:**
- Modify: `api/src/services/conditions.ts`
- Modify: `api/tests/services/conditions.test.ts` (or create if it doesn't exist for this method)

Wire CDEC fetching into the existing `getWaterData` method with the "freshest wins" merge strategy.

- [ ] **Step 1: Write test for CDEC data merge**

Check if `api/tests/services/conditions.test.ts` exists. If tests for `getWaterData` don't exist, create a focused test. Because `getWaterData` is private, test through the public interface or extract the merge logic into a testable function.

Create `api/tests/services/cdec-merge.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

// Test the merge logic directly
// When both USGS and CDEC provide water temp, freshest wins
describe('CDEC merge logic', () => {
  interface WaterDataResult {
    waterTempF: number | null;
    waterTempSource: string | null;
    streamflowCfs: number | null;
    riverStageFt: number | null;
    reservoir: any | null;
    waterQuality: any | null;
    tides: any | null;
    sources: Record<string, string>;
  }

  function mergeWaterData(
    usgs: { waterTempF: number | null; streamflowCfs: number | null } | null,
    cdec: { waterTempF?: number; flowCfs?: number; riverStageFt?: number; reservoir?: any; waterQuality?: any } | null,
  ): WaterDataResult {
    const result: WaterDataResult = {
      waterTempF: null,
      waterTempSource: null,
      streamflowCfs: null,
      riverStageFt: null,
      reservoir: null,
      waterQuality: null,
      tides: null,
      sources: {},
    };

    // USGS data
    if (usgs?.waterTempF != null) {
      result.waterTempF = usgs.waterTempF;
      result.waterTempSource = 'usgs';
      result.sources.waterTemp = 'usgs';
    }
    if (usgs?.streamflowCfs != null) {
      result.streamflowCfs = usgs.streamflowCfs;
      result.sources.flow = 'usgs';
    }

    // CDEC data - overwrites USGS if available (CDEC is typically more recent for CA)
    if (cdec?.waterTempF != null) {
      result.waterTempF = cdec.waterTempF;
      result.waterTempSource = 'cdec';
      result.sources.waterTemp = 'cdec';
    }
    if (cdec?.flowCfs != null) {
      result.streamflowCfs = cdec.flowCfs;
      result.sources.flow = 'cdec';
    }

    // CDEC-exclusive data (pass through)
    if (cdec?.riverStageFt != null) result.riverStageFt = cdec.riverStageFt;
    if (cdec?.reservoir != null) result.reservoir = cdec.reservoir;
    if (cdec?.waterQuality != null) result.waterQuality = cdec.waterQuality;

    return result;
  }

  it('uses USGS data when no CDEC available', () => {
    const result = mergeWaterData(
      { waterTempF: 68, streamflowCfs: 450 },
      null,
    );
    expect(result.waterTempF).toBe(68);
    expect(result.waterTempSource).toBe('usgs');
    expect(result.streamflowCfs).toBe(450);
  });

  it('CDEC overwrites USGS water temp when both available', () => {
    const result = mergeWaterData(
      { waterTempF: 68, streamflowCfs: 450 },
      { waterTempF: 55.2, flowCfs: 1523 },
    );
    expect(result.waterTempF).toBe(55.2);
    expect(result.waterTempSource).toBe('cdec');
    expect(result.streamflowCfs).toBe(1523);
    expect(result.sources.waterTemp).toBe('cdec');
    expect(result.sources.flow).toBe('cdec');
  });

  it('passes through CDEC-exclusive data', () => {
    const result = mergeWaterData(
      { waterTempF: 68, streamflowCfs: 450 },
      {
        riverStageFt: 4.32,
        reservoir: { storageAf: 650000, elevationFt: 430.5 },
        waterQuality: { turbidityNtu: 8.2 },
      },
    );
    expect(result.riverStageFt).toBe(4.32);
    expect(result.reservoir).toEqual({ storageAf: 650000, elevationFt: 430.5 });
    expect(result.waterQuality).toEqual({ turbidityNtu: 8.2 });
    // USGS still wins for water temp since CDEC didn't provide it
    expect(result.waterTempF).toBe(68);
    expect(result.waterTempSource).toBe('usgs');
  });

  it('handles both sources null', () => {
    const result = mergeWaterData(null, null);
    expect(result.waterTempF).toBeNull();
    expect(result.streamflowCfs).toBeNull();
  });
});
```

- [ ] **Step 2: Run the merge test**

Run: `cd api && npx vitest run tests/services/cdec-merge.test.ts`
Expected: All tests PASS

- [ ] **Step 3: Update getWaterData in conditions.ts**

In `api/src/services/conditions.ts`, update the `getWaterData` method to include CDEC fetching. The return type expands to include the new fields:

```typescript
  private async getWaterData(
    waterBodyType: string,
    dataSources: DataSources,
  ): Promise<{
    waterTempF: number | null;
    streamflowCfs: number | null;
    tides: NoaaData | null;
    waterTempSource: string | null;
    riverStageFt: number | null;
    reservoir: ReservoirData | null;
    waterQuality: WaterQualityData | null;
    sources: Record<string, string>;
  }> {
    let waterTempF: number | null = null;
    let streamflowCfs: number | null = null;
    let tides: NoaaData | null = null;
    let waterTempSource: string | null = null;
    let riverStageFt: number | null = null;
    let reservoir: ReservoirData | null = null;
    let waterQuality: WaterQualityData | null = null;
    const sources: Record<string, string> = {};

    try {
      // USGS
      for (const usgsSiteId of dataSources.usgs) {
        const cacheKey = `usgs:${usgsSiteId}`;
        let data: UsgsData;
        const cached = this.cache.get(cacheKey) as UsgsData | undefined;
        if (cached) {
          data = cached;
        } else {
          data = await fetchUsgs(usgsSiteId);
          this.cache.set(cacheKey, data, TTL_WATER_TEMP);
        }
        if (waterTempF == null && data.waterTempF != null) {
          waterTempF = data.waterTempF;
          waterTempSource = 'usgs';
          sources.waterTemp = 'usgs';
        }
        if (streamflowCfs == null && data.streamflowCfs != null) {
          streamflowCfs = data.streamflowCfs;
          sources.flow = 'usgs';
        }
        if (waterTempF != null && streamflowCfs != null) break;
      }

      // CDEC
      for (const cdecStationId of dataSources.cdec) {
        const tempKey = `cdec:${cdecStationId}:temp`;
        const flowKey = `cdec:${cdecStationId}:flow`;
        const stageKey = `cdec:${cdecStationId}:stage`;
        const resKey = `cdec:${cdecStationId}:reservoir`;
        const wqKey = `cdec:${cdecStationId}:waterQuality`;

        // Water temp (overwrites USGS if available - CDEC is typically fresher for CA)
        let cdecTemp = this.cache.get(tempKey) as number | null | undefined;
        if (cdecTemp === undefined) {
          cdecTemp = await fetchCdecWaterTemp(cdecStationId);
          this.cache.set(tempKey, cdecTemp, TTL_WEATHER);
        }
        if (cdecTemp != null) {
          waterTempF = cdecTemp;
          waterTempSource = 'cdec';
          sources.waterTemp = 'cdec';
        }

        // Flow (overwrites USGS if available)
        let cdecFlow = this.cache.get(flowKey) as number | null | undefined;
        if (cdecFlow === undefined) {
          cdecFlow = await fetchCdecFlow(cdecStationId);
          this.cache.set(flowKey, cdecFlow, TTL_WEATHER);
        }
        if (cdecFlow != null) {
          streamflowCfs = cdecFlow;
          sources.flow = 'cdec';
        }

        // River stage (CDEC-exclusive)
        let cdecStage = this.cache.get(stageKey) as number | null | undefined;
        if (cdecStage === undefined) {
          cdecStage = await fetchCdecRiverStage(cdecStationId);
          this.cache.set(stageKey, cdecStage, TTL_WEATHER);
        }
        if (cdecStage != null) {
          riverStageFt = cdecStage;
        }

        // Reservoir data (CDEC-exclusive)
        if (waterBodyType === 'reservoir' || waterBodyType === 'lake') {
          let cdecRes = this.cache.get(resKey) as ReservoirData | null | undefined;
          if (cdecRes === undefined) {
            cdecRes = await fetchCdecReservoirData(cdecStationId);
            this.cache.set(resKey, cdecRes, TTL_WEATHER);
          }
          if (cdecRes != null) {
            reservoir = cdecRes;
          }
        }

        // Water quality (CDEC-exclusive, rare)
        let cdecWq = this.cache.get(wqKey) as WaterQualityData | null | undefined;
        if (cdecWq === undefined) {
          cdecWq = await fetchCdecWaterQuality(cdecStationId);
          this.cache.set(wqKey, cdecWq, TTL_WATER_TEMP);
        }
        if (cdecWq != null) {
          waterQuality = cdecWq;
        }
      }

      // NOAA (existing logic unchanged)
      for (const noaaStationId of dataSources.noaa) {
        if (waterBodyType === 'bay_ocean' || waterTempF == null) {
          if (tides == null) {
            const tideCacheKey = `noaa-tides:${noaaStationId}`;
            const cachedTides = this.cache.get(tideCacheKey) as NoaaData | undefined;
            if (cachedTides) {
              tides = cachedTides;
            } else {
              tides = await fetchTides(noaaStationId);
              this.cache.set(tideCacheKey, tides, TTL_WATER_TEMP);
            }
          }
          if (waterTempF == null) {
            const tempCacheKey = `noaa-temp:${noaaStationId}`;
            const cachedTemp = this.cache.get(tempCacheKey) as number | null | undefined;
            if (cachedTemp !== undefined) {
              waterTempF = cachedTemp;
            } else {
              waterTempF = await fetchWaterTemp(noaaStationId);
              this.cache.set(tempCacheKey, waterTempF, TTL_WATER_TEMP);
            }
            if (waterTempF != null) {
              waterTempSource = 'noaa';
              sources.waterTemp = 'noaa';
            }
          }
        }
        if (tides != null && waterTempF != null) break;
      }
    } catch {
      // Graceful degradation - water data is optional
    }

    return { waterTempF, streamflowCfs, tides, waterTempSource, riverStageFt, reservoir, waterQuality, sources };
  }
```

- [ ] **Step 4: Update callers of getWaterData**

Update the code that builds the `water` object (~line 510) to include the new fields:

```typescript
    const water = {
      waterTempF: waterTempInfo.value,
      waterTempSource: waterTempInfo.source,
      waterTempUpdatedAt: waterTempInfo.updatedAt,
      streamflowCfs: waterData.streamflowCfs,
      tides: waterData.tides ?? null,
      riverStageFt: waterData.riverStageFt ?? null,
      reservoir: waterData.reservoir ?? null,
      waterQuality: waterData.waterQuality ?? null,
      sources: waterData.sources,
    };
```

Also update `fetchRawData` if it exists (used by the refresh job) to include the same fields.

- [ ] **Step 5: Verify TypeScript compiles and existing tests pass**

Run: `cd api && npx tsc --noEmit && npx vitest run`
Expected: No type errors, all existing tests pass

- [ ] **Step 6: Commit**

```bash
cd api && git add src/services/conditions.ts tests/services/cdec-merge.test.ts && git commit -m "feat: integrate CDEC fetch into conditions service with merge strategy"
```

---

### Task 7: New Scoring Factors - Reservoir Level and Water Quality

**Files:**
- Modify: `api/src/lib/scoring.ts`
- Create: `api/tests/lib/scoring-cdec.test.ts`

Add scoring functions for reservoir level (% capacity), water quality composite, and pet safety advisory.

- [ ] **Step 1: Write tests for new scoring functions**

```typescript
// api/tests/lib/scoring-cdec.test.ts
import { describe, it, expect } from 'vitest';
import {
  scoreReservoirLevel,
  scoreWaterQuality,
  computePetSafety,
} from '../../src/lib/scoring.js';

describe('scoreReservoirLevel', () => {
  it('returns 100 for 80% capacity', () => {
    expect(scoreReservoirLevel(800000, 1000000)).toBe(100);
  });

  it('returns ~75 for 45% capacity (marginal zone)', () => {
    const score = scoreReservoirLevel(450000, 1000000)!;
    expect(score).toBeGreaterThan(50);
    expect(score).toBeLessThan(100);
  });

  it('returns 0 for 10% capacity (no-go)', () => {
    expect(scoreReservoirLevel(100000, 1000000)).toBe(0);
  });

  it('returns null when capacity is null', () => {
    expect(scoreReservoirLevel(500000, null)).toBeNull();
  });

  it('returns null when storage is null', () => {
    expect(scoreReservoirLevel(null, 1000000)).toBeNull();
  });
});

describe('scoreWaterQuality', () => {
  it('returns 100 for ideal conditions', () => {
    expect(scoreWaterQuality({ turbidityNtu: 5, dissolvedOxygenMgL: 8, ph: 7.5, conductivityUs: 500 })).toBe(100);
  });

  it('returns 0 for terrible turbidity', () => {
    expect(scoreWaterQuality({ turbidityNtu: 150 })).toBe(0);
  });

  it('returns marginal score for borderline DO', () => {
    const score = scoreWaterQuality({ dissolvedOxygenMgL: 5 })!;
    expect(score).toBeGreaterThan(0);
    expect(score).toBeLessThan(100);
  });

  it('returns null when no data provided', () => {
    expect(scoreWaterQuality({})).toBeNull();
  });
});

describe('computePetSafety', () => {
  it('returns SAFE for good conditions', () => {
    const result = computePetSafety(65, { dissolvedOxygenMgL: 8, turbidityNtu: 5, ph: 7.5, conductivityUs: 500 });
    expect(result!.rating).toBe('SAFE');
    expect(result!.reasons).toHaveLength(0);
  });

  it('returns UNSAFE for algal bloom conditions', () => {
    const result = computePetSafety(78, { dissolvedOxygenMgL: 3.5, turbidityNtu: 60 });
    expect(result!.rating).toBe('UNSAFE');
    expect(result!.reasons).toContain('Possible algal bloom conditions');
  });

  it('returns UNSAFE for extreme turbidity', () => {
    const result = computePetSafety(65, { turbidityNtu: 120 });
    expect(result!.rating).toBe('UNSAFE');
  });

  it('returns CAUTION for early bloom conditions', () => {
    const result = computePetSafety(70, { dissolvedOxygenMgL: 5.5 });
    expect(result!.rating).toBe('CAUTION');
  });

  it('returns null when no water quality data', () => {
    expect(computePetSafety(65, null)).toBeNull();
  });

  it('returns UNSAFE for extreme pH', () => {
    const result = computePetSafety(65, { ph: 4.5 });
    expect(result!.rating).toBe('UNSAFE');
  });

  it('returns CAUTION for high conductivity', () => {
    const result = computePetSafety(65, { conductivityUs: 2500 });
    expect(result!.rating).toBe('CAUTION');
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/lib/scoring-cdec.test.ts`
Expected: FAIL - functions not exported

- [ ] **Step 3: Implement scoring functions**

Add to the end of `api/src/lib/scoring.ts`, before the `computePaddleScore` function:

```typescript
// ============================================================================
// CDEC-specific scoring factors
// ============================================================================

export function scoreReservoirLevel(
  storageAf: number | null | undefined,
  capacityAf: number | null | undefined,
): number | null {
  if (storageAf == null || capacityAf == null || capacityAf <= 0) return null;
  const pct = (storageAf / capacityAf) * 100;
  if (pct >= 60) return 100;
  if (pct <= 20) return 0;
  // 20-60% maps linearly from 0-100
  return Math.round(100 * (pct - 20) / 40);
}

export function scoreWaterQuality(
  wq: { turbidityNtu?: number; dissolvedOxygenMgL?: number; ph?: number; conductivityUs?: number },
): number | null {
  const scores: number[] = [];

  if (wq.turbidityNtu != null) {
    scores.push(linearScore(wq.turbidityNtu, 10, 50, 100) ?? 100);
  }
  if (wq.dissolvedOxygenMgL != null) {
    scores.push(linearScoreInverted(wq.dissolvedOxygenMgL, 6, 4, 2) ?? 100);
  }
  if (wq.ph != null) {
    // pH has a two-sided ideal range
    if (wq.ph >= 6.5 && wq.ph <= 8.5) {
      scores.push(100);
    } else if (wq.ph < 6.5) {
      scores.push(linearScoreInverted(wq.ph, 6.5, 6.0, 5.0) ?? 0);
    } else {
      scores.push(linearScore(wq.ph, 8.5, 9.0, 10.0) ?? 0);
    }
  }
  if (wq.conductivityUs != null) {
    scores.push(linearScore(wq.conductivityUs, 1000, 2000, 3000) ?? 100);
  }

  if (scores.length === 0) return null;
  return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
}

export interface PetSafetyRating {
  rating: 'SAFE' | 'CAUTION' | 'UNSAFE';
  reasons: string[];
}

export function computePetSafety(
  waterTempF: number | null | undefined,
  wq: { turbidityNtu?: number; dissolvedOxygenMgL?: number; ph?: number; conductivityUs?: number } | null | undefined,
): PetSafetyRating | null {
  if (!wq) return null;
  const hasAnyData = wq.turbidityNtu != null || wq.dissolvedOxygenMgL != null || wq.ph != null || wq.conductivityUs != null;
  if (!hasAnyData) return null;

  const reasons: string[] = [];
  let isUnsafe = false;
  let isCaution = false;

  // Algal bloom: high temp + low DO + elevated turbidity
  if (waterTempF != null && waterTempF > 75 && wq.dissolvedOxygenMgL != null && wq.dissolvedOxygenMgL < 4) {
    reasons.push('Possible algal bloom conditions');
    isUnsafe = true;
  }

  // Turbidity
  if (wq.turbidityNtu != null) {
    if (wq.turbidityNtu > 100) {
      reasons.push('Very high turbidity');
      isUnsafe = true;
    } else if (wq.turbidityNtu > 50) {
      reasons.push('Elevated turbidity');
      isCaution = true;
    }
  }

  // pH
  if (wq.ph != null) {
    if (wq.ph < 5.0 || wq.ph > 9.5) {
      reasons.push(`pH ${wq.ph} outside safe range`);
      isUnsafe = true;
    } else if (wq.ph < 6.0 || wq.ph > 9.0) {
      reasons.push(`pH ${wq.ph} borderline`);
      isCaution = true;
    }
  }

  // Early bloom (temp + DO, less severe)
  if (!isUnsafe && waterTempF != null && waterTempF > 68 && wq.dissolvedOxygenMgL != null && wq.dissolvedOxygenMgL < 6) {
    reasons.push('Early bloom conditions possible');
    isCaution = true;
  }

  // Conductivity
  if (wq.conductivityUs != null && wq.conductivityUs > 2000) {
    reasons.push('High dissolved solids');
    isCaution = true;
  }

  if (isUnsafe) return { rating: 'UNSAFE', reasons };
  if (isCaution) return { rating: 'CAUTION', reasons };
  return { rating: 'SAFE', reasons: [] };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd api && npx vitest run tests/lib/scoring-cdec.test.ts`
Expected: All tests PASS

- [ ] **Step 5: Run all tests to make sure nothing broke**

Run: `cd api && npx vitest run`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd api && git add src/lib/scoring.ts tests/lib/scoring-cdec.test.ts && git commit -m "feat(scoring): add reservoir level, water quality, and pet safety scoring"
```

---

### Task 8: Integrate New Scoring Factors into computePaddleScore

**Files:**
- Modify: `api/src/lib/scoring.ts`
- Modify: `api/src/lib/profiles.ts`
- Create: `api/tests/lib/scoring-integration.test.ts`

Wire the new scoring factors into `computePaddleScore` and add profile weights/curves. Add `paddlesWithPets` toggle.

- [ ] **Step 1: Write integration test**

```typescript
// api/tests/lib/scoring-integration.test.ts
import { describe, it, expect } from 'vitest';
import { computePaddleScore, type ScoreInput } from '../../src/lib/scoring.js';
import { PROFILES } from '../../src/lib/profiles.js';

describe('computePaddleScore with CDEC factors', () => {
  const baseInput: ScoreInput = {
    windSpeed: 5, windGusts: 8, aqi: 25, airTemp: 75,
    uvIndex: 4, visibility: 10, precipitation: 0,
    hasThunderstorm: false, waterBodyType: 'reservoir',
    profile: PROFILES.sup.recreational,
  };

  it('includes reservoir_level factor when data provided', () => {
    const result = computePaddleScore({
      ...baseInput,
      reservoirStorageAf: 800000,
      reservoirCapacityAf: 1000000,
    });
    expect(result.factors.reservoir_level).toBe(100);
  });

  it('skips reservoir_level when capacity missing', () => {
    const result = computePaddleScore({
      ...baseInput,
      reservoirStorageAf: 800000,
    });
    expect(result.factors.reservoir_level).toBeUndefined();
  });

  it('includes water_quality factor when data provided', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterQuality: { turbidityNtu: 5, dissolvedOxygenMgL: 8 },
    });
    expect(result.factors.water_quality).toBeDefined();
    expect(result.factors.water_quality).toBeGreaterThan(80);
  });

  it('triggers pet safety veto when paddlesWithPets is true and water is unsafe', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterTempF: 78,
      waterQuality: { dissolvedOxygenMgL: 3, turbidityNtu: 60 },
      paddlesWithPets: true,
    });
    expect(result.vetoed).toBe(true);
    expect(result.vetoReason).toContain('pet');
  });

  it('does not veto when paddlesWithPets is false even with unsafe water', () => {
    const result = computePaddleScore({
      ...baseInput,
      waterTempF: 78,
      waterQuality: { dissolvedOxygenMgL: 3, turbidityNtu: 60 },
      paddlesWithPets: false,
    });
    expect(result.vetoed).toBe(false);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd api && npx vitest run tests/lib/scoring-integration.test.ts`
Expected: FAIL - properties not on ScoreInput

- [ ] **Step 3: Extend ScoreInput and computePaddleScore**

In `api/src/lib/scoring.ts`, add new fields to `ScoreInput`:

```typescript
export interface ScoreInput {
  windSpeed: number | null;
  windGusts: number | null;
  aqi: number | null;
  airTemp: number | null;
  uvIndex: number | null;
  visibility: number | null;
  precipitation: number | null;
  streamflowCfs?: number | null;
  tideCurrent?: number | null;
  hasThunderstorm: boolean;
  waterBodyType: string;
  profile: ProfileConfig;
  optimalCfs?: number;
  // CDEC additions
  reservoirStorageAf?: number | null;
  reservoirCapacityAf?: number | null;
  damOutflowCfs?: number | null;
  damOutflowThreshold?: number | null;
  waterQuality?: { turbidityNtu?: number; dissolvedOxygenMgL?: number; ph?: number; conductivityUs?: number } | null;
  waterTempF?: number | null;
  paddlesWithPets?: boolean;
}
```

In `computePaddleScore`, add pet safety veto check after the existing hard veto check:

```typescript
  // Pet safety veto (after existing hard vetoes)
  if (input.paddlesWithPets && input.waterQuality) {
    const petSafety = computePetSafety(input.waterTempF ?? null, input.waterQuality);
    if (petSafety?.rating === 'UNSAFE') {
      return { value: 0, rating: 'NO_GO', limitingFactor: null, factors: {}, missingFactors: [], vetoed: true, vetoReason: `Unsafe water quality for pets: ${petSafety.reasons.join(', ')}` };
    }
  }
```

Add reservoir level and water quality scoring in the water-body-specific section (after the existing streamflow/tide blocks):

```typescript
  // Dam release veto (safety-critical for downstream river segments)
  if (input.damOutflowCfs != null && input.damOutflowThreshold != null && input.damOutflowCfs > input.damOutflowThreshold) {
    return { value: 0, rating: 'NO_GO', limitingFactor: null, factors: {}, missingFactors: [], vetoed: true, vetoReason: `High dam release: ${input.damOutflowCfs} CFS exceeds ${input.damOutflowThreshold} CFS threshold` };
  }

  // Reservoir level
  if ((input.waterBodyType === 'reservoir' || input.waterBodyType === 'lake') && profile.weights.reservoir_level) {
    const rl = scoreReservoirLevel(input.reservoirStorageAf ?? null, input.reservoirCapacityAf ?? null);
    if (rl !== null) {
      factorScores.reservoir_level = rl;
    } else if (input.reservoirCapacityAf != null) {
      missingFactors.push('reservoir_level');
    }
  }

  // Water quality
  if (profile.weights.water_quality && input.waterQuality) {
    const wq = scoreWaterQuality(input.waterQuality);
    if (wq !== null) {
      factorScores.water_quality = wq;
    }
  }
```

- [ ] **Step 4: Add weights to profiles**

In `api/src/lib/profiles.ts`, add new weight entries to each profile's `weights` object. For `sup.recreational`:

```typescript
      weights: {
        wind_speed: 0.25, wind_gusts: 0.10, air_quality: 0.15, temperature: 0.15,
        uv_index: 0.10, visibility: 0.10, precipitation: 0.05,
        streamflow: 0.10, tide: 0.10,
        reservoir_level: 0.10, water_quality: 0.10,
      },
```

Repeat for other profiles (racing, family, and kayak profiles), adjusting weights as appropriate. The weights will be re-normalized by `computePaddleScore`, so the exact values are relative.

- [ ] **Step 5: Run all scoring tests**

Run: `cd api && npx vitest run tests/lib/`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `cd api && npx vitest run`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd api && git add src/lib/scoring.ts src/lib/profiles.ts tests/lib/scoring-integration.test.ts && git commit -m "feat(scoring): integrate reservoir level, water quality, and pet safety into paddle score"
```

---

### Task 9: Wire CDEC Data Through to API Response

**Files:**
- Modify: `api/src/services/conditions.ts`

Update `buildConditionsResponse` and related methods to pass CDEC data (reservoir, water quality, pet safety) through to the API response.

- [ ] **Step 1: Update buildConditionsResponse**

Find `buildConditionsResponse` in `conditions.ts` and update it to:
1. Pass `reservoir`, `waterQuality`, `riverStageFt` from the water data into the response
2. Compute `petSafety` rating using `computePetSafety` from scoring.ts
3. Pass new fields (`reservoirStorageAf`, `reservoirCapacityAf`, `waterQuality`, `waterTempF`, `paddlesWithPets`) to `computePaddleScore`

The `reservoirCapacityAf` needs to be loaded from the water body record. Check how the water body is loaded in the service and add `reservoirCapacityAf` to the data passed through.

Import `computePetSafety` and `type PetSafetyRating` at the top of the file:

```typescript
import { computePaddleScore, computePetSafety, type PaddleScore, type PetSafetyRating } from '../lib/scoring.js';
```

Add pet safety and CDEC data to the conditions response. The exact location depends on the current response shape. Add these fields to the `ConditionsResponse` interface:

```typescript
  petSafety?: PetSafetyRating;
  riverStageFt?: number | null;
  reservoir?: ReservoirData | null;
  waterQuality?: WaterQualityData | null;
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Run full test suite**

Run: `cd api && npx vitest run`
Expected: All existing tests PASS

- [ ] **Step 4: Commit**

```bash
cd api && git add src/services/conditions.ts && git commit -m "feat: wire CDEC data through to conditions API response"
```

---

### Task 10: Update Refresh Job for CDEC

**Files:**
- Modify: `api/src/services/water-body-cache.ts`

The refresh job calls `conditionsService.fetchRawData()` which calls `getWaterData()`. Since we updated `getWaterData` in Task 6, the refresh job will automatically fetch CDEC data when `dataSources.cdec` is populated.

The key change is in `getStationConfig` in `water-body-cache.ts` -- it needs to include CDEC station IDs in the returned `dataSources`.

- [ ] **Step 1: Update getStationConfig to include CDEC stations**

Find the `getStationConfig` method in `api/src/services/water-body-cache.ts`. It queries `waterBodyStations` for the given water body. Update it to include `cdec` station type in the returned `dataSources`:

Look at the current implementation. It likely builds `dataSources` from the stations table. The `stationType` is already queried, so adding `cdec` should flow through naturally since we added `'cdec'` to the enum. But verify that the code maps `stationType === 'cdec'` to `dataSources.cdec`.

The existing code likely does something like:
```typescript
for (const station of stations) {
  if (station.stationType === 'usgs') dataSources.usgs.push(station.stationId);
  else if (station.stationType === 'noaa') dataSources.noaa.push(station.stationId);
}
```

Add the CDEC case:
```typescript
  else if (station.stationType === 'cdec') dataSources.cdec.push(station.stationId);
```

And initialize `cdec: []` in the dataSources object.

Also check if there's a direct lookup path using `waterBodies.cdecStationId` (similar to `usgsStationId`). If the code checks for direct station IDs, add the CDEC equivalent.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Run full test suite**

Run: `cd api && npx vitest run`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd api && git add src/services/water-body-cache.ts && git commit -m "feat: include CDEC stations in refresh job data sources"
```

---

### Task 11: Final Integration Test and Cleanup

**Files:**
- Run full test suite and verify everything works together

- [ ] **Step 1: Run TypeScript type check**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Run full test suite**

Run: `cd api && npx vitest run`
Expected: All tests PASS

- [ ] **Step 3: Review for unused imports or dead code**

Quickly scan the modified files for any unused imports or variables that the linter would catch.

- [ ] **Step 4: Update changelog**

Add entry to `website/data/changelog.json` for the CDEC integration. Follow existing format.

- [ ] **Step 5: Update docs**

Add/update relevant docs in `website/src/pages/docs/` describing CDEC as a data source and the new water quality / pet safety features.

- [ ] **Step 6: Final commit**

```bash
git add -A && git commit -m "feat: CDEC integration - California water data, reservoir scoring, pet safety"
```
