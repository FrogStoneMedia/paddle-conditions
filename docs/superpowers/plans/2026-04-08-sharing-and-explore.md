# Sharing & Explore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add public spot pages, an explore-nearby page on the website, and a share button in the app.

**Architecture:** Two new public API endpoints read from existing cached data. The Astro website switches to hybrid SSR (Node adapter + Passenger) for dynamic spot pages. A Leaflet map island powers the explore page. The app gets a share button that generates water-body-based URLs.

**Tech Stack:** Fastify (API), Astro 6 + @astrojs/node (website SSR), Leaflet (map), Tailwind 4 (styling), Vitest (API tests)

**Spec:** `docs/superpowers/specs/2026-04-08-sharing-and-explore-design.md`

---

## File Structure

### API (`api/`)
- **Create:** `src/routes/public/spot.ts` -- GET /public/spot/:slug endpoint
- **Create:** `src/routes/public/nearby.ts` -- GET /public/spots/nearby endpoint
- **Create:** `src/services/public-conditions.ts` -- shared logic for public scoring
- **Create:** `src/db/migrations/0010_water_body_slugs.sql` -- add slug column + backfill
- **Modify:** `src/db/schema.ts` -- add slug to waterBodies definition
- **Modify:** `src/index.ts` -- register public routes
- **Modify:** `src/services/sync.ts` -- include waterBodySlug in pull response
- **Create:** `tests/routes/public-spot.test.ts` -- spot endpoint tests
- **Create:** `tests/routes/public-nearby.test.ts` -- nearby endpoint tests

### Website (`website/`)
- **Modify:** `astro.config.mjs` -- switch to hybrid output + Node adapter
- **Modify:** `package.json` -- add @astrojs/node, leaflet deps, start script
- **Create:** `src/pages/spot/[slug].astro` -- SSR spot page
- **Create:** `src/pages/explore.astro` -- explore page shell
- **Create:** `src/components/ExploreMap.tsx` -- Leaflet map React island
- **Create:** `src/components/SpotCard.astro` -- card for explore grid
- **Create:** `src/components/ConditionsGrid.astro` -- conditions metric tiles
- **Create:** `src/components/ScoreCircle.astro` -- score display
- **Create:** `src/components/PremiumCTA.astro` -- already exists, may reuse
- **Modify:** `src/components/Header.astro` -- add Explore nav link
- **Modify:** `.github/workflows/deploy.yml` -- add Passenger restart

### App (`app/`)
- **Modify:** `src/lib/types.ts` -- add waterBodySlug to Location type
- **Modify:** `src/pages/LocationDetailPage.tsx` -- add share button
- **Create:** `src/components/ShareButton.tsx` -- share/copy component

---

## Task 1: Database Migration -- Add slug to water_bodies

**Files:**
- Create: `api/src/db/migrations/0010_water_body_slugs.sql`
- Modify: `api/src/db/schema.ts:137-165`

- [ ] **Step 1: Write the migration SQL**

Create `api/src/db/migrations/0010_water_body_slugs.sql`:

```sql
ALTER TABLE `water_bodies` ADD COLUMN `slug` varchar(255);--> statement-breakpoint
CREATE UNIQUE INDEX `water_bodies_slug_idx` ON `water_bodies` (`slug`);
```

Note: Slug backfill will be done via a separate script after the column exists, since generating slugs with dedup logic requires application code.

- [ ] **Step 2: Update the Drizzle schema**

In `api/src/db/schema.ts`, add `slug` to the `waterBodies` table definition. Find the `metadata` line and add `slug` before it:

```typescript
// Inside waterBodies table definition, after cdecStationId:
slug: varchar('slug', { length: 255 }),
```

And add the index in the table's index array:

```typescript
uniqueIndex('water_bodies_slug_idx').on(table.slug),
```

- [ ] **Step 3: Create the backfill script**

Create `api/scripts/backfill-water-body-slugs.ts`:

```typescript
import 'dotenv/config';
import { createPool } from 'mysql2/promise';

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/['']/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

async function main() {
  const pool = createPool({
    host: process.env.DB_HOST ?? 'localhost',
    port: parseInt(process.env.DB_PORT ?? '3306', 10),
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_DATABASE,
  });

  const [rows] = await pool.execute('SELECT id, name FROM water_bodies WHERE slug IS NULL');
  const slugCounts = new Map<string, number>();

  for (const row of rows as Array<{ id: string; name: string }>) {
    let base = slugify(row.name);
    if (!base) base = 'water-body';

    const count = slugCounts.get(base) ?? 0;
    const slug = count === 0 ? base : `${base}-${count + 1}`;
    slugCounts.set(base, count + 1);

    await pool.execute('UPDATE water_bodies SET slug = ? WHERE id = ?', [slug, row.id]);
  }

  console.log(`Backfilled ${(rows as any[]).length} slugs`);
  await pool.end();
}

main().catch(console.error);
```

- [ ] **Step 4: Run migration locally and verify**

Run: `cd api && npx tsx src/db/run-migration.ts` (or apply via tunnel)

Then run backfill: `cd api && npx tsx scripts/backfill-water-body-slugs.ts`

Verify: `mysql -e "SELECT name, slug FROM water_bodies LIMIT 10;"`

Expected: Each water body has a slug like `lake-tahoe`, `folsom-lake`, etc.

- [ ] **Step 5: Commit**

```bash
cd api && git add src/db/migrations/0010_water_body_slugs.sql src/db/schema.ts scripts/backfill-water-body-slugs.ts
git commit -m "feat: add slug column to water_bodies with backfill script"
```

---

## Task 2: Public Conditions Service

**Files:**
- Create: `api/src/services/public-conditions.ts`

This service computes conditions from cached data using the default SUP recreational profile.

- [ ] **Step 1: Write the failing test**

Create `api/tests/services/public-conditions.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { computePublicConditions } from '../../src/services/public-conditions.js';

const mockWeather = {
  windSpeed: 5,
  windGusts: 8,
  windDirection: 'SW',
  airTemp: 68,
  feelsLike: 66,
  humidity: 45,
  uvIndex: 6,
  visibility: 10,
  precipProbability: 0,
  conditionText: 'Sunny',
  hasThunderstorm: false,
  hourly: [],
};

const mockWater = {
  waterTempF: 52,
  waterTempSource: 'usgs',
  waterTempUpdatedAt: '2026-04-08T12:00:00Z',
  streamflowCfs: 500,
  tides: null,
};

const mockAqi = { aqi: 32, pm25: 8, pm10: 12, ozone: 25 };

describe('computePublicConditions', () => {
  it('computes score and current conditions from cached data', () => {
    const result = computePublicConditions(mockWeather, mockWater, mockAqi, 'lake');

    expect(result.score).toBeGreaterThan(0);
    expect(result.score).toBeLessThanOrEqual(100);
    expect(['GO', 'CAUTION', 'NO_GO']).toContain(result.rating);
    expect(result.current.windSpeed).toBe(5);
    expect(result.current.windDirection).toBe('SW');
    expect(result.current.airTemp).toBe(68);
    expect(result.current.waterTemp).toBe(52);
    expect(result.current.uvIndex).toBe(6);
    expect(result.current.aqi).toBe(32);
    expect(result.current.precipProbability).toBe(0);
    expect(result.current.conditionText).toBe('Sunny');
  });

  it('returns null values for missing water data', () => {
    const emptyWater = { waterTempF: null, waterTempSource: null, waterTempUpdatedAt: null, streamflowCfs: null, tides: null };
    const result = computePublicConditions(mockWeather, emptyWater, mockAqi, 'lake');

    expect(result.current.waterTemp).toBeNull();
    expect(result.score).toBeGreaterThan(0);
  });

  it('uses SUP recreational profile for scoring', () => {
    // High wind should reduce score significantly for SUP recreational
    const windyWeather = { ...mockWeather, windSpeed: 18, windGusts: 25 };
    const result = computePublicConditions(windyWeather, mockWater, mockAqi, 'lake');

    expect(result.rating).toBe('CAUTION');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && npx vitest run tests/services/public-conditions.test.ts`

Expected: FAIL -- module not found

- [ ] **Step 3: Implement the service**

Create `api/src/services/public-conditions.ts`:

```typescript
import { computePaddleScore } from '../lib/scoring.js';
import { getProfile } from '../lib/profiles.js';
import type { WeatherData, AqiData } from './conditions.js';

const DEFAULT_PROFILE = getProfile('sup', 'recreational');

export interface PublicConditions {
  score: number;
  rating: 'GO' | 'CAUTION' | 'NO_GO';
  current: {
    windSpeed: number | null;
    windDirection: string | null;
    airTemp: number | null;
    waterTemp: number | null;
    uvIndex: number | null;
    aqi: number | null;
    precipProbability: number | null;
    conditionText: string | null;
  };
}

export function computePublicConditions(
  weather: WeatherData,
  water: { waterTempF: number | null; streamflowCfs: number | null; [key: string]: unknown },
  aqi: AqiData,
  waterBodyType: string,
): PublicConditions {
  const paddleScore = computePaddleScore({
    windSpeed: weather.windSpeed,
    windGusts: weather.windGusts,
    aqi: aqi.aqi,
    airTemp: weather.airTemp,
    uvIndex: weather.uvIndex,
    visibility: weather.visibility,
    precipitation: weather.precipProbability,
    streamflowCfs: water.streamflowCfs,
    hasThunderstorm: weather.hasThunderstorm,
    waterBodyType,
    profile: DEFAULT_PROFILE,
    waterTempF: water.waterTempF,
  });

  return {
    score: paddleScore.value,
    rating: paddleScore.rating,
    current: {
      windSpeed: weather.windSpeed,
      windDirection: weather.windDirection ?? null,
      airTemp: weather.airTemp,
      waterTemp: water.waterTempF,
      uvIndex: weather.uvIndex,
      aqi: aqi.aqi,
      precipProbability: weather.precipProbability,
      conditionText: weather.conditionText ?? null,
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd api && npx vitest run tests/services/public-conditions.test.ts`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
cd api && git add src/services/public-conditions.ts tests/services/public-conditions.test.ts
git commit -m "feat: add public conditions service with SUP recreational scoring"
```

---

## Task 3: GET /public/spot/:slug Endpoint

**Files:**
- Create: `api/src/routes/public/spot.ts`
- Create: `api/tests/routes/public-spot.test.ts`
- Modify: `api/src/index.ts`

- [ ] **Step 1: Write the failing test**

Create `api/tests/routes/public-spot.test.ts`:

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { buildApp } from '../helpers/app.js';
import type { FastifyInstance } from 'fastify';

let app: FastifyInstance;

beforeAll(async () => {
  app = await buildApp();
});

afterAll(async () => {
  await app.close();
});

describe('GET /public/spot/:slug', () => {
  it('returns 404 for non-existent slug', async () => {
    const res = await app.inject({ method: 'GET', url: '/public/spot/does-not-exist' });
    expect(res.statusCode).toBe(404);
  });

  it('returns water body with null conditions when no cache exists', async () => {
    // Seed a water body with a slug but no conditions
    await app.dbPool.execute(
      `INSERT INTO water_bodies (id, name, type, state, lat, lng, source, source_id, slug)
       VALUES ('wb-pub-test-1', 'Test Lake', 'lake', 'CA', 38.5, -121.0, 'manual', 'pub-test-1', 'test-lake')
       ON DUPLICATE KEY UPDATE slug = 'test-lake'`
    );

    const res = await app.inject({ method: 'GET', url: '/public/spot/test-lake' });
    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body.waterBody.name).toBe('Test Lake');
    expect(body.waterBody.type).toBe('lake');
    expect(body.waterBody.slug).toBe('test-lake');
    expect(body.conditions).toBeNull();
  });

  it('returns water body with scored conditions when cache exists', async () => {
    // Seed cached conditions
    const weather = JSON.stringify({
      windSpeed: 5, windGusts: 8, windDirection: 'SW', airTemp: 68, feelsLike: 66,
      humidity: 45, uvIndex: 6, visibility: 10, precipProbability: 0,
      conditionText: 'Sunny', hasThunderstorm: false, hourly: [],
    });
    const water = JSON.stringify({
      waterTempF: 52, waterTempSource: 'usgs', waterTempUpdatedAt: '2026-04-08T12:00:00Z',
      streamflowCfs: 500, tides: null,
    });
    const aqi = JSON.stringify({ aqi: 32, pm25: 8, pm10: 12, ozone: 25 });

    await app.dbPool.execute(
      `INSERT INTO water_body_conditions (water_body_id, weather, water, aqi, fetched_at, user_count)
       VALUES ('wb-pub-test-1', ?, ?, ?, NOW(), 1)
       ON DUPLICATE KEY UPDATE weather = ?, water = ?, aqi = ?, fetched_at = NOW()`,
      [weather, water, aqi, weather, water, aqi]
    );

    const res = await app.inject({ method: 'GET', url: '/public/spot/test-lake' });
    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body.conditions).not.toBeNull();
    expect(body.conditions.score).toBeGreaterThan(0);
    expect(['GO', 'CAUTION', 'NO_GO']).toContain(body.conditions.rating);
    expect(body.conditions.current.windSpeed).toBe(5);
    expect(body.conditions.current.airTemp).toBe(68);
    expect(body.conditions.fetchedAt).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && npx vitest run tests/routes/public-spot.test.ts`

Expected: FAIL -- route not found (404 for all)

- [ ] **Step 3: Implement the route**

Create `api/src/routes/public/spot.ts`:

```typescript
import type { FastifyInstance } from 'fastify';
import { computePublicConditions } from '../../services/public-conditions.js';

export default async function publicSpotRoute(app: FastifyInstance) {
  app.get(
    '/public/spot/:slug',
    {
      config: {
        rateLimit: { max: 30, timeWindow: '1 minute' },
      },
    },
    async (request, reply) => {
      const { slug } = request.params as { slug: string };

      // Look up water body by slug
      const [wbRows] = await app.dbPool.execute(
        `SELECT id, name, type, state, county, lat, lng, slug
         FROM water_bodies WHERE slug = ? LIMIT 1`,
        [slug],
      );

      const rows = wbRows as any[];
      if (rows.length === 0) {
        return reply.status(404).send({ error: 'Spot not found' });
      }

      const wb = rows[0];
      const waterBody = {
        id: wb.id,
        name: wb.name,
        type: wb.type,
        state: wb.state,
        county: wb.county,
        lat: parseFloat(wb.lat),
        lng: parseFloat(wb.lng),
        slug: wb.slug,
      };

      // Look up cached conditions
      const [condRows] = await app.dbPool.execute(
        `SELECT weather, water, aqi, fetched_at FROM water_body_conditions
         WHERE water_body_id = ? AND weather IS NOT NULL LIMIT 1`,
        [wb.id],
      );

      const condRow = (condRows as any[])[0];
      if (!condRow) {
        reply.header('Cache-Control', 'public, s-maxage=900, max-age=60');
        return { waterBody, conditions: null };
      }

      const weather = typeof condRow.weather === 'string' ? JSON.parse(condRow.weather) : condRow.weather;
      const water = typeof condRow.water === 'string' ? JSON.parse(condRow.water) : condRow.water;
      const aqi = condRow.aqi
        ? (typeof condRow.aqi === 'string' ? JSON.parse(condRow.aqi) : condRow.aqi)
        : { aqi: null, pm25: null, pm10: null, ozone: null };

      const scored = computePublicConditions(weather, water, aqi, wb.type);

      reply.header('Cache-Control', 'public, s-maxage=900, max-age=60');
      return {
        waterBody,
        conditions: {
          ...scored,
          fetchedAt: condRow.fetched_at?.toISOString() ?? null,
        },
      };
    },
  );
}
```

- [ ] **Step 4: Register the route in index.ts**

In `api/src/index.ts`, add the import and registration:

```typescript
// After other route imports:
import publicSpotRoute from './routes/public/spot.js';

// After other route registrations:
await app.register(publicSpotRoute);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && npx vitest run tests/routes/public-spot.test.ts`

Expected: PASS (3 tests)

- [ ] **Step 6: Run full test suite**

Run: `cd api && npx vitest run`

Expected: All tests pass (existing + new)

- [ ] **Step 7: Commit**

```bash
cd api && git add src/routes/public/spot.ts src/index.ts tests/routes/public-spot.test.ts
git commit -m "feat: add GET /public/spot/:slug endpoint for public conditions"
```

---

## Task 4: GET /public/spots/nearby Endpoint

**Files:**
- Create: `api/src/routes/public/nearby.ts`
- Create: `api/tests/routes/public-nearby.test.ts`
- Modify: `api/src/index.ts`

- [ ] **Step 1: Write the failing test**

Create `api/tests/routes/public-nearby.test.ts`:

```typescript
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { buildApp } from '../helpers/app.js';
import type { FastifyInstance } from 'fastify';

let app: FastifyInstance;

beforeAll(async () => {
  app = await buildApp();

  // Seed 3 water bodies at known positions
  await app.dbPool.execute(
    `INSERT INTO water_bodies (id, name, type, state, lat, lng, source, source_id, slug)
     VALUES
       ('wb-near-1', 'Lake Alpha', 'lake', 'CA', 38.6, -121.0, 'manual', 'near-1', 'lake-alpha'),
       ('wb-near-2', 'River Beta', 'river', 'CA', 38.7, -121.1, 'manual', 'near-2', 'river-beta'),
       ('wb-near-3', 'Bay Gamma', 'bay', 'CA', 40.0, -122.0, 'manual', 'near-3', 'bay-gamma')
     ON DUPLICATE KEY UPDATE slug = VALUES(slug)`
  );
});

afterAll(async () => {
  await app.close();
});

describe('GET /public/spots/nearby', () => {
  it('returns 400 without lat/lng', async () => {
    const res = await app.inject({ method: 'GET', url: '/public/spots/nearby' });
    expect(res.statusCode).toBe(400);
  });

  it('returns spots sorted by distance', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/nearby?lat=38.6&lng=-121.0&radius=50',
    });
    expect(res.statusCode).toBe(200);

    const body = res.json();
    expect(body.spots.length).toBeGreaterThanOrEqual(2);
    expect(body.spots[0].waterBody.name).toBe('Lake Alpha'); // closest
    expect(body.spots[0].distance).toBeCloseTo(0, 0);

    // Verify sorted ascending
    for (let i = 1; i < body.spots.length; i++) {
      expect(body.spots[i].distance).toBeGreaterThanOrEqual(body.spots[i - 1].distance);
    }
  });

  it('filters by water body type', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/nearby?lat=38.6&lng=-121.0&radius=100&type=river',
    });
    const body = res.json();
    for (const spot of body.spots) {
      expect(spot.waterBody.type).toBe('river');
    }
  });

  it('respects limit parameter', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/nearby?lat=38.6&lng=-121.0&radius=200&limit=1',
    });
    const body = res.json();
    expect(body.spots.length).toBe(1);
  });

  it('returns conditions when cached data exists', async () => {
    // Seed conditions for lake-alpha
    const weather = JSON.stringify({
      windSpeed: 5, windGusts: 8, windDirection: 'SW', airTemp: 68, feelsLike: 66,
      humidity: 45, uvIndex: 6, visibility: 10, precipProbability: 0,
      conditionText: 'Sunny', hasThunderstorm: false, hourly: [],
    });
    const water = JSON.stringify({ waterTempF: 52, waterTempSource: 'usgs', waterTempUpdatedAt: null, streamflowCfs: null, tides: null });
    const aqi = JSON.stringify({ aqi: 32, pm25: 8, pm10: 12, ozone: 25 });

    await app.dbPool.execute(
      `INSERT INTO water_body_conditions (water_body_id, weather, water, aqi, fetched_at, user_count)
       VALUES ('wb-near-1', ?, ?, ?, NOW(), 1)
       ON DUPLICATE KEY UPDATE weather = ?, fetched_at = NOW()`,
      [weather, water, aqi, weather],
    );

    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/nearby?lat=38.6&lng=-121.0&radius=50',
    });
    const body = res.json();
    const alphaSpot = body.spots.find((s: any) => s.waterBody.name === 'Lake Alpha');
    expect(alphaSpot.conditions).not.toBeNull();
    expect(alphaSpot.conditions.score).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && npx vitest run tests/routes/public-nearby.test.ts`

Expected: FAIL -- route not found

- [ ] **Step 3: Implement the route**

Create `api/src/routes/public/nearby.ts`:

```typescript
import type { FastifyInstance } from 'fastify';
import { computePublicConditions } from '../../services/public-conditions.js';

export default async function publicNearbyRoute(app: FastifyInstance) {
  app.get(
    '/public/spots/nearby',
    {
      config: {
        rateLimit: { max: 30, timeWindow: '1 minute' },
      },
    },
    async (request, reply) => {
      const { lat, lng, radius, type, limit } = request.query as {
        lat?: string;
        lng?: string;
        radius?: string;
        type?: string;
        limit?: string;
      };

      if (!lat || !lng) {
        return reply.status(400).send({ error: 'lat and lng are required' });
      }

      const latNum = parseFloat(lat);
      const lngNum = parseFloat(lng);
      if (isNaN(latNum) || isNaN(lngNum) || latNum < -90 || latNum > 90 || lngNum < -180 || lngNum > 180) {
        return reply.status(400).send({ error: 'Invalid lat/lng values' });
      }

      const radiusMiles = Math.min(parseFloat(radius ?? '50') || 50, 100);
      const maxResults = Math.min(parseInt(limit ?? '20', 10) || 20, 50);

      // Haversine distance in miles via SQL
      // Parameters: lat appears 4 times (2 in SELECT, 2 in WHERE), lng appears 2 times
      const haversineParams = [latNum, lngNum, latNum]; // COS(lat)*COS(lat)*COS(lng-lng) + SIN(lat)*SIN(lat)
      const queryParams: any[] = [
        ...haversineParams,  // SELECT haversine
        ...haversineParams,  // WHERE haversine
        radiusMiles,
        ...(type ? [type] : []),
        maxResults,
      ];

      const [rows] = await app.dbPool.execute(
        `SELECT wb.id, wb.name, wb.type, wb.state, wb.lat, wb.lng, wb.slug,
                (3959 * ACOS(LEAST(1.0,
                  COS(RADIANS(?)) * COS(RADIANS(wb.lat)) * COS(RADIANS(wb.lng) - RADIANS(?))
                  + SIN(RADIANS(?)) * SIN(RADIANS(wb.lat))
                ))) AS distance,
                wbc.weather, wbc.water, wbc.aqi, wbc.fetched_at
         FROM water_bodies wb
         LEFT JOIN water_body_conditions wbc ON wbc.water_body_id = wb.id AND wbc.weather IS NOT NULL
         WHERE (3959 * ACOS(LEAST(1.0,
                  COS(RADIANS(?)) * COS(RADIANS(wb.lat)) * COS(RADIANS(wb.lng) - RADIANS(?))
                  + SIN(RADIANS(?)) * SIN(RADIANS(wb.lat))
                ))) <= ?
         ${type ? 'AND wb.type = ?' : ''}
         ORDER BY distance ASC
         LIMIT ?`,
        queryParams,
      );

      const spots = (rows as any[]).map(row => {
        const waterBody = {
          id: row.id,
          name: row.name,
          type: row.type,
          state: row.state,
          lat: parseFloat(row.lat),
          lng: parseFloat(row.lng),
          slug: row.slug,
        };

        let conditions = null;
        if (row.weather) {
          const weather = typeof row.weather === 'string' ? JSON.parse(row.weather) : row.weather;
          const water = typeof row.water === 'string' ? JSON.parse(row.water) : row.water;
          const aqi = row.aqi
            ? (typeof row.aqi === 'string' ? JSON.parse(row.aqi) : row.aqi)
            : { aqi: null, pm25: null, pm10: null, ozone: null };

          const scored = computePublicConditions(weather, water, aqi, row.type);
          conditions = {
            ...scored,
            fetchedAt: row.fetched_at?.toISOString() ?? null,
          };
        }

        return {
          waterBody,
          distance: Math.round(parseFloat(row.distance) * 10) / 10,
          conditions,
        };
      });

      reply.header('Cache-Control', 'public, s-maxage=300, max-age=60');
      return { spots };
    },
  );
}
```

- [ ] **Step 4: Register the route in index.ts**

In `api/src/index.ts`, add:

```typescript
import publicNearbyRoute from './routes/public/nearby.js';

// After publicSpotRoute registration:
await app.register(publicNearbyRoute);
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd api && npx vitest run tests/routes/public-nearby.test.ts`

Expected: PASS (5 tests)

- [ ] **Step 6: Run full test suite**

Run: `cd api && npx vitest run`

Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
cd api && git add src/routes/public/nearby.ts src/index.ts tests/routes/public-nearby.test.ts
git commit -m "feat: add GET /public/spots/nearby endpoint with haversine distance"
```

---

## Task 5: Include waterBodySlug in Sync Response

**Files:**
- Modify: `api/src/services/sync.ts`
- Modify: `app/src/lib/types.ts`

The app needs the water body slug to generate share URLs. The sync pull response currently includes `waterBodyId` in the raw row but not the water body's slug. We need to join and include it.

- [ ] **Step 1: Update the sync service pull to include water body slug**

In `api/src/services/sync.ts`, modify the `pullLocations` method. After the station enrichment (around line 87), add a water body slug lookup:

```typescript
// After the stationMap enrichment block, before the `enriched` mapping:
// Fetch slugs for linked water bodies
const slugMap = new Map<string, string>();
if (waterBodyIds.length > 0) {
  const [slugRows] = await (this.db as any).execute(
    `SELECT id, slug FROM water_bodies WHERE id IN (${waterBodyIds.map(() => '?').join(',')})`,
    waterBodyIds,
  );
  for (const row of slugRows as any[]) {
    if (row.slug) slugMap.set(row.id, row.slug);
  }
}
```

Then in the `enriched` mapping, add `waterBodySlug`:

```typescript
const enriched = rows.map(row => {
  let result: any = { ...row };
  if (row.waterBodyId && stationMap.has(row.waterBodyId)) {
    const config = (row.config as Record<string, unknown>) ?? {};
    result = { ...result, config: { ...config, stations: stationMap.get(row.waterBodyId) } };
  }
  if (row.waterBodyId && slugMap.has(row.waterBodyId)) {
    result.waterBodySlug = slugMap.get(row.waterBodyId);
  }
  return result;
});
```

Note: Check the exact existing mapping code and adapt. The key change is adding `waterBodySlug` to each row that has a linked water body.

- [ ] **Step 2: Update the app Location type**

In `app/src/lib/types.ts`, add `waterBodySlug` to the `Location` interface:

```typescript
export interface Location {
  id: string;
  name: string;
  slug: string | null;
  lat: number;
  lng: number;
  waterBodyType: string;
  profile: string;
  config: LocationConfig | null;
  waterBodySlug?: string | null;  // Add this line
  updatedAt: string;
  deletedAt: string | null;
}
```

- [ ] **Step 3: Run API tests**

Run: `cd api && npx vitest run`

Expected: All pass (sync tests still pass with the added field)

- [ ] **Step 4: Commit**

```bash
cd api && git add src/services/sync.ts
cd ../app && git add src/lib/types.ts
git commit -m "feat: include waterBodySlug in sync pull response for share URLs"
```

---

## Task 6: Share Button in App

**Files:**
- Create: `app/src/components/ShareButton.tsx`
- Modify: `app/src/pages/LocationDetailPage.tsx`

- [ ] **Step 1: Create the ShareButton component**

Create `app/src/components/ShareButton.tsx`:

```typescript
import { useToast } from './Toast.js';

interface Props {
  waterBodySlug: string;
  locationName: string;
}

export default function ShareButton({ waterBodySlug, locationName }: Props) {
  const { show: showToast } = useToast();

  const shareUrl = `https://paddleconditions.com/spot/${waterBodySlug}`;

  async function handleShare() {
    if (navigator.share) {
      try {
        await navigator.share({
          title: `${locationName} - Paddle Conditions`,
          text: `Check out paddle conditions at ${locationName}`,
          url: shareUrl,
        });
      } catch (e) {
        // User cancelled share -- ignore AbortError
        if ((e as Error).name !== 'AbortError') {
          await copyToClipboard();
        }
      }
    } else {
      await copyToClipboard();
    }
  }

  async function copyToClipboard() {
    try {
      await navigator.clipboard.writeText(shareUrl);
      showToast('Link copied to clipboard!', 'success');
    } catch {
      showToast('Failed to copy link', 'error');
    }
  }

  return (
    <button
      onClick={handleShare}
      className="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center"
      aria-label="Share this spot"
    >
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--color-text-muted)' }}>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
      </svg>
    </button>
  );
}
```

- [ ] **Step 2: Add ShareButton to LocationDetailPage header**

In `app/src/pages/LocationDetailPage.tsx`, import the component at the top:

```typescript
import ShareButton from '../components/ShareButton.js';
```

Then find the header's right side (around line 68, the `{location && (` block with the settings button). Wrap both buttons in a flex container:

```typescript
{location && (
  <div className="flex items-center">
    {location.waterBodySlug && (
      <ShareButton waterBodySlug={location.waterBodySlug} locationName={location.name} />
    )}
    <button onClick={() => setSettingsOpen(true)} className="p-2 min-w-[44px] min-h-[44px] flex items-center justify-center">
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--color-text-muted)' }}>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    </button>
  </div>
)}
```

- [ ] **Step 3: Build and verify**

Run: `cd app && npm run build`

Expected: Build succeeds with no TypeScript errors

- [ ] **Step 4: Commit**

```bash
cd app && git add src/components/ShareButton.tsx src/pages/LocationDetailPage.tsx
git commit -m "feat: add share button to location detail page"
```

---

## Task 7: Website SSR Setup

**Files:**
- Modify: `website/astro.config.mjs`
- Modify: `website/package.json`
- Modify: `website/.github/workflows/deploy.yml`

- [ ] **Step 1: Install the Node adapter**

Run: `cd website && npm install @astrojs/node`

- [ ] **Step 2: Update Astro config for hybrid output**

Replace `website/astro.config.mjs`:

```javascript
// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import sitemap from '@astrojs/sitemap';
import node from '@astrojs/node';

export default defineConfig({
  site: 'https://paddleconditions.com',
  output: 'static',
  adapter: node({ mode: 'standalone' }),
  integrations: [
    sitemap({
      filter: (page) => !page.includes('/404'),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
```

Note: With Astro 6, `output: 'static'` is the default and individual pages opt into SSR with `export const prerender = false`. The adapter is needed so those pages have a runtime.

- [ ] **Step 3: Add start script to package.json**

In `website/package.json`, add to the scripts object:

```json
"start": "node ./dist/server/entry.mjs"
```

- [ ] **Step 4: Update deploy workflow**

In `website/.github/workflows/deploy.yml`, after the rsync step, add:

```yaml
      - name: Restart Passenger
        run: |
          ssh -i ~/.ssh/cpanel_deploy_bttp -p 11208 \
            devsac@104.255.174.113 \
            "mkdir -p ~/public_html/paddleconditions.com/tmp && touch ~/public_html/paddleconditions.com/tmp/restart.txt"
```

Also update the rsync to deploy the server build (not just `dist/client/`):

```yaml
      - name: Deploy to cPanel
        run: |
          rsync -avz --delete \
            --exclude='.well-known' \
            --exclude='tmp' \
            -e "ssh -i ~/.ssh/cpanel_deploy_bttp -p 11208" \
            dist/ devsac@104.255.174.113:/home/devsac/public_html/paddleconditions.com/
```

- [ ] **Step 5: Build and verify**

Run: `cd website && npm run build`

Expected: Build succeeds. Output includes both `dist/client/` (static assets) and `dist/server/` (SSR entry).

- [ ] **Step 6: Commit**

```bash
cd website && git add astro.config.mjs package.json package-lock.json .github/workflows/deploy.yml
git commit -m "feat: switch website to hybrid SSR with Node adapter"
```

---

## Task 8: Spot Page (`/spot/[slug]`)

**Files:**
- Create: `website/src/pages/spot/[slug].astro`
- Create: `website/src/components/ConditionsGrid.astro`
- Create: `website/src/components/ScoreCircle.astro`

- [ ] **Step 1: Create the ScoreCircle component**

Create `website/src/components/ScoreCircle.astro`:

```astro
---
interface Props {
  score: number;
  rating: 'GO' | 'CAUTION' | 'NO_GO';
  size?: 'sm' | 'md' | 'lg';
}

const { score, rating, size = 'md' } = Astro.props;

const colors = {
  GO: { bg: '#0ea5e9', text: 'text-sky-500' },
  CAUTION: { bg: '#eab308', text: 'text-yellow-500' },
  NO_GO: { bg: '#ef4444', text: 'text-red-500' },
};

const sizes = {
  sm: { circle: 'w-8 h-8 text-xs', label: 'text-xs' },
  md: { circle: 'w-14 h-14 text-xl', label: 'text-base' },
  lg: { circle: 'w-16 h-16 text-2xl', label: 'text-lg' },
};

const color = colors[rating];
const s = sizes[size];

const ratingLabel = rating === 'NO_GO' ? 'NO GO' : rating;
---

<div class="flex items-center gap-3">
  <div
    class={`${s.circle} rounded-full flex items-center justify-center text-white font-bold shrink-0`}
    style={`background-color: ${color.bg}; box-shadow: 0 2px 6px ${color.bg}66;`}
  >
    {score}
  </div>
  <div>
    <div class={`font-bold ${s.label}`} style={`color: ${color.bg};`}>{ratingLabel}</div>
    <div class="text-xs text-slate-500">Typical paddle score</div>
  </div>
</div>
```

- [ ] **Step 2: Create the ConditionsGrid component**

Create `website/src/components/ConditionsGrid.astro`:

```astro
---
interface Props {
  conditions: {
    windSpeed: number | null;
    windDirection: string | null;
    airTemp: number | null;
    waterTemp: number | null;
    uvIndex: number | null;
    aqi: number | null;
    precipProbability: number | null;
    conditionText: string | null;
  };
}

const { conditions } = Astro.props;

const metrics = [
  { label: 'Wind', value: conditions.windSpeed != null ? `${conditions.windSpeed} mph` : '--', sub: conditions.windDirection },
  { label: 'Air Temp', value: conditions.airTemp != null ? `${conditions.airTemp}\u00B0F` : '--', sub: conditions.conditionText },
  { label: 'Water Temp', value: conditions.waterTemp != null ? `${conditions.waterTemp}\u00B0F` : '--', sub: null },
  { label: 'UV Index', value: conditions.uvIndex != null ? `${conditions.uvIndex}` : '--', sub: conditions.uvIndex != null ? (conditions.uvIndex >= 8 ? 'Very High' : conditions.uvIndex >= 6 ? 'High' : conditions.uvIndex >= 3 ? 'Moderate' : 'Low') : null },
  { label: 'AQI', value: conditions.aqi != null ? `${conditions.aqi}` : '--', sub: conditions.aqi != null ? (conditions.aqi <= 50 ? 'Good' : conditions.aqi <= 100 ? 'Moderate' : 'Unhealthy') : null },
  { label: 'Precip', value: conditions.precipProbability != null ? `${conditions.precipProbability}%` : '--', sub: null },
];
---

<div class="grid grid-cols-2 md:grid-cols-3 gap-2.5">
  {metrics.map(m => (
    <div class="bg-white rounded-xl p-4 text-center shadow-sm">
      <div class="text-[10px] text-slate-400 uppercase tracking-wider">{m.label}</div>
      <div class="text-xl font-bold mt-1">{m.value}</div>
      {m.sub && <div class="text-[11px] text-slate-500">{m.sub}</div>}
    </div>
  ))}
</div>
```

- [ ] **Step 3: Create the spot page**

Create `website/src/pages/spot/[slug].astro`:

```astro
---
export const prerender = false;

import BaseLayout from '../../layouts/BaseLayout.astro';
import ScoreCircle from '../../components/ScoreCircle.astro';
import ConditionsGrid from '../../components/ConditionsGrid.astro';

const { slug } = Astro.params;
const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';

let data: any = null;
let error = false;

try {
  const res = await fetch(`${API_BASE}/public/spot/${slug}`);
  if (res.ok) {
    data = await res.json();
  } else if (res.status === 404) {
    return Astro.redirect('/404');
  } else {
    error = true;
  }
} catch {
  error = true;
}

const wb = data?.waterBody;
const conditions = data?.conditions;

const title = wb ? `${wb.name} Paddle Conditions | Current Wind, Water & Weather` : 'Spot Not Found';
const description = wb && conditions
  ? `${wb.name} is rated ${conditions.rating} with a score of ${conditions.score}. Wind ${conditions.current.windSpeed ?? '--'} mph, Air ${conditions.current.airTemp ?? '--'}°F, Water ${conditions.current.waterTemp ?? '--'}°F.`
  : wb ? `Check paddle conditions at ${wb.name}, ${wb.state}.` : '';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ago`;
}

const typeLabels: Record<string, string> = {
  lake: 'LAKE', river: 'RIVER', reservoir: 'RESERVOIR', bay: 'BAY', coastal: 'COASTAL',
};

Astro.response.headers.set('Cache-Control', 'public, s-maxage=900, max-age=60');
---

<BaseLayout title={title} description={description}>
  <div class="max-w-xl mx-auto px-4 py-8">
    {error && (
      <div class="text-center py-16">
        <h1 class="text-2xl font-bold text-slate-900 mb-2">Something went wrong</h1>
        <p class="text-slate-600">Could not load conditions. Please try again later.</p>
      </div>
    )}

    {wb && !error && (
      <>
        {/* Header: name left, score right */}
        <div class="flex justify-between items-center mb-6">
          <div>
            <div class="flex items-center gap-2.5 mb-1">
              <h1 class="text-2xl font-bold text-slate-900">{wb.name}</h1>
              <span class="bg-sky-100 text-sky-700 px-2 py-0.5 rounded text-[11px] font-semibold">
                {typeLabels[wb.type] ?? wb.type.toUpperCase()}
              </span>
            </div>
            <p class="text-sm text-slate-500">{wb.state}{wb.county ? ` \u00B7 ${wb.county}` : ''}</p>
          </div>
          {conditions && (
            <ScoreCircle score={conditions.score} rating={conditions.rating} />
          )}
        </div>

        {/* Conditions or no-data */}
        {conditions ? (
          <>
            <ConditionsGrid conditions={conditions.current} />
            <p class="text-xs text-slate-400 text-center mt-4 mb-8">
              Last updated {timeAgo(conditions.fetchedAt)}
            </p>
          </>
        ) : (
          <div class="text-center py-12 mb-8">
            <p class="text-slate-500 text-lg mb-2">No current conditions available</p>
            <p class="text-slate-400 text-sm">Be the first to monitor this spot!</p>
          </div>
        )}

        {/* Premium CTA */}
        <div class="bg-gradient-to-br from-slate-900 to-sky-800 rounded-2xl p-6 text-center text-white mb-8">
          <h2 class="text-lg font-bold mb-1">Want charts, forecasts & alerts?</h2>
          <p class="text-sm opacity-85 mb-4">Get real-time updates with Paddle Conditions Premium</p>
          <a
            href="https://app.paddleconditions.com/subscribe"
            class="inline-block bg-white text-sky-700 font-semibold px-6 py-2.5 rounded-lg text-sm hover:bg-sky-50 transition-colors"
          >
            Subscribe to Premium
          </a>
        </div>

        {/* Map placeholder -- will be replaced with Leaflet in Task 9 */}
        <div class="bg-sky-100 rounded-2xl h-48 flex items-center justify-center text-sky-500 text-sm">
          Map coming soon
        </div>
      </>
    )}
  </div>
</BaseLayout>
```

- [ ] **Step 4: Build and verify**

Run: `cd website && npm run build && npm run preview`

Visit `http://localhost:4321/spot/lake-tahoe` (will 404 until API is deployed, but page should render).

- [ ] **Step 5: Commit**

```bash
cd website && git add src/pages/spot/ src/components/ScoreCircle.astro src/components/ConditionsGrid.astro
git commit -m "feat: add public spot page with SSR conditions display"
```

---

## Task 9: Explore Page with Leaflet Map

**Files:**
- Create: `website/src/pages/explore.astro`
- Create: `website/src/components/ExploreMap.tsx`
- Create: `website/src/components/SpotCard.astro`
- Modify: `website/src/components/Header.astro`
- Modify: `website/package.json`

- [ ] **Step 1: Install Leaflet**

Run: `cd website && npm install leaflet react react-dom @types/leaflet`

Note: The website doesn't currently have React. We need it for the Leaflet island. Astro supports mixing frameworks.

Also install the React integration:

Run: `cd website && npx astro add react`

This will update `astro.config.mjs` to include the React integration.

- [ ] **Step 2: Create the SpotCard component**

Create `website/src/components/SpotCard.astro`:

```astro
---
interface Props {
  name: string;
  type: string;
  state: string;
  slug: string;
  distance: number;
  score?: number | null;
  rating?: string | null;
}

const { name, type, state, slug, distance, score, rating } = Astro.props;

const typeLabels: Record<string, string> = {
  lake: 'LAKE', river: 'RIVER', reservoir: 'RESERVOIR', bay: 'BAY', coastal: 'COASTAL',
};

const ratingColors: Record<string, string> = {
  GO: '#0ea5e9',
  CAUTION: '#eab308',
  NO_GO: '#ef4444',
};

const bgColor = rating ? `${ratingColors[rating]}10` : '#f1f5f9';
---

<a href={`/spot/${slug}`} class="block bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow border border-slate-100 overflow-hidden">
  <div class="p-4">
    <div class="flex justify-between items-start mb-2">
      <div>
        <div class="font-bold text-sm text-slate-900">{name}</div>
        <div class="text-[10px] text-slate-500 mt-0.5">{typeLabels[type] ?? type} &middot; {distance} mi</div>
      </div>
      <span class="bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded text-[9px] font-semibold shrink-0">
        {typeLabels[type] ?? type}
      </span>
    </div>
    <div class="flex items-center gap-2 rounded-lg px-2.5 py-2" style={`background-color: ${bgColor};`}>
      {score != null && rating ? (
        <>
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
            style={`background-color: ${ratingColors[rating]};`}
          >
            {score}
          </div>
          <div>
            <div class="font-bold text-xs" style={`color: ${ratingColors[rating]};`}>
              {rating === 'NO_GO' ? 'NO GO' : rating}
            </div>
          </div>
        </>
      ) : (
        <>
          <div class="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 bg-slate-300">--</div>
          <div>
            <div class="font-semibold text-xs text-slate-400">No data</div>
            <div class="text-[9px] text-slate-400">Not yet monitored</div>
          </div>
        </>
      )}
    </div>
  </div>
</a>
```

- [ ] **Step 3: Create the ExploreMap React component**

Create `website/src/components/ExploreMap.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface Spot {
  waterBody: { id: string; name: string; type: string; state: string; lat: number; lng: number; slug: string };
  distance: number;
  conditions: { score: number; rating: string; current: any; fetchedAt: string } | null;
}

const RATING_COLORS: Record<string, string> = {
  GO: '#0ea5e9',
  CAUTION: '#eab308',
  NO_GO: '#ef4444',
};

function createTeardropIcon(score: number | null, rating: string | null): L.DivIcon {
  const color = rating ? RATING_COLORS[rating] ?? '#cbd5e1' : '#cbd5e1';
  const label = score != null ? String(score) : '--';

  return L.divIcon({
    className: '',
    iconSize: [34, 44],
    iconAnchor: [17, 44],
    popupAnchor: [0, -44],
    html: `
      <svg width="34" height="44" viewBox="0 0 34 44" xmlns="http://www.w3.org/2000/svg">
        <path d="M17 44C17 44 34 26 34 17C34 7.6 26.4 0 17 0C7.6 0 0 7.6 0 17C0 26 17 44 17 44Z"
              fill="${color}" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.3))"/>
        <text x="17" y="20" text-anchor="middle" fill="white" font-size="12" font-weight="700" font-family="system-ui">${label}</text>
      </svg>
    `,
  });
}

interface Props {
  apiBase: string;
}

export default function ExploreMap({ apiBase }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<L.Map | null>(null);
  const [spots, setSpots] = useState<Spot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [radius, setRadius] = useState(50);
  const [typeFilter, setTypeFilter] = useState('');
  const [locationName, setLocationName] = useState('');

  useEffect(() => {
    if (!mapRef.current || mapInstance.current) return;
    mapInstance.current = L.map(mapRef.current).setView([38.5, -121.5], 8);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(mapInstance.current);
  }, []);

  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        fetchSpots(pos.coords.latitude, pos.coords.longitude);
        mapInstance.current?.setView([pos.coords.latitude, pos.coords.longitude], 9);
      },
      () => {
        // Default to Sacramento, CA
        fetchSpots(38.5816, -121.4944);
        setLocationName('Sacramento, CA (default)');
      },
    );
  }, [radius, typeFilter]);

  async function fetchSpots(lat: number, lng: number) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ lat: String(lat), lng: String(lng), radius: String(radius), limit: '30' });
      if (typeFilter) params.set('type', typeFilter);
      const res = await fetch(`${apiBase}/public/spots/nearby?${params}`);
      if (!res.ok) throw new Error('Failed to fetch');
      const data = await res.json();
      setSpots(data.spots);
      updateMarkers(data.spots);

      // Reverse geocode for location name
      if (!locationName) {
        try {
          const geoRes = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=10`);
          const geo = await geoRes.json();
          setLocationName(geo.address?.city ?? geo.address?.town ?? geo.address?.county ?? '');
        } catch { /* ignore */ }
      }
    } catch {
      setError('Could not load nearby spots. Try again later.');
    } finally {
      setLoading(false);
    }
  }

  function updateMarkers(spotList: Spot[]) {
    const map = mapInstance.current;
    if (!map) return;
    map.eachLayer(l => { if (l instanceof L.Marker) map.removeLayer(l); });

    for (const spot of spotList) {
      const { lat, lng, name, slug } = spot.waterBody;
      const score = spot.conditions?.score ?? null;
      const rating = spot.conditions?.rating ?? null;
      const icon = createTeardropIcon(score, rating);
      const marker = L.marker([lat, lng], { icon }).addTo(map);
      marker.bindPopup(`<a href="/spot/${slug}" style="font-weight:600;color:#0369a1">${name}</a>`);
    }
  }

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700 }}>Explore Paddle Spots</h1>
          {locationName && <p style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>Near {locationName}</p>}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <select
            value={typeFilter}
            onChange={e => setTypeFilter(e.target.value)}
            style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 12px', fontSize: '12px', color: '#475569' }}
          >
            <option value="">All types</option>
            <option value="lake">Lake</option>
            <option value="river">River</option>
            <option value="reservoir">Reservoir</option>
            <option value="bay">Bay</option>
            <option value="coastal">Coastal</option>
          </select>
          <select
            value={String(radius)}
            onChange={e => setRadius(Number(e.target.value))}
            style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '6px 12px', fontSize: '12px', color: '#475569' }}
          >
            <option value="10">10 mi</option>
            <option value="25">25 mi</option>
            <option value="50">50 mi</option>
            <option value="100">100 mi</option>
          </select>
        </div>
      </div>

      {/* Map */}
      <div ref={mapRef} style={{ height: '300px', borderRadius: '14px', marginBottom: '20px', zIndex: 0 }} />

      {/* Status */}
      {loading && <p style={{ textAlign: 'center', color: '#94a3b8', padding: '24px 0' }}>Loading nearby spots...</p>}
      {error && <p style={{ textAlign: 'center', color: '#ef4444', padding: '24px 0' }}>{error}</p>}
      {!loading && !error && spots.length === 0 && (
        <p style={{ textAlign: 'center', color: '#94a3b8', padding: '24px 0' }}>No paddle spots found nearby. Try expanding your search radius.</p>
      )}

      {/* Card grid */}
      {!loading && spots.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px' }}>
          {spots.map(spot => (
            <a
              key={spot.waterBody.id}
              href={`/spot/${spot.waterBody.slug}`}
              style={{
                display: 'block', background: 'white', borderRadius: '12px', overflow: 'hidden',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)', textDecoration: 'none', color: 'inherit',
                border: '1px solid #f1f5f9',
              }}
            >
              <div style={{ padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '14px', color: '#0f172a' }}>{spot.waterBody.name}</div>
                    <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                      {spot.waterBody.type.charAt(0).toUpperCase() + spot.waterBody.type.slice(1)} &middot; {spot.distance} mi
                    </div>
                  </div>
                </div>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px', borderRadius: '8px', padding: '8px 10px',
                  backgroundColor: spot.conditions ? `${RATING_COLORS[spot.conditions.rating]}10` : '#f8fafc',
                }}>
                  <div style={{
                    width: '32px', height: '32px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'white', fontSize: '13px', fontWeight: 700, flexShrink: 0,
                    backgroundColor: spot.conditions ? RATING_COLORS[spot.conditions.rating] : '#cbd5e1',
                  }}>
                    {spot.conditions ? spot.conditions.score : '--'}
                  </div>
                  <div>
                    <div style={{
                      fontWeight: 700, fontSize: '13px',
                      color: spot.conditions ? RATING_COLORS[spot.conditions.rating] : '#94a3b8',
                    }}>
                      {spot.conditions ? (spot.conditions.rating === 'NO_GO' ? 'NO GO' : spot.conditions.rating) : 'No data'}
                    </div>
                    {!spot.conditions && (
                      <div style={{ fontSize: '9px', color: '#94a3b8' }}>Not yet monitored</div>
                    )}
                  </div>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create the explore page**

Create `website/src/pages/explore.astro`:

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
import ExploreMap from '../components/ExploreMap.tsx';

const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';
---

<BaseLayout title="Explore Paddle Spots | Paddle Conditions" description="Find paddle spots near you. See current conditions for lakes, rivers, and reservoirs.">
  <div class="max-w-5xl mx-auto px-4 py-8">
    <ExploreMap client:load apiBase={API_BASE} />
  </div>
</BaseLayout>
```

- [ ] **Step 5: Add Explore to navigation**

In `website/src/components/Header.astro`, add to the `navLinks` array:

```typescript
const navLinks = [
  { href: '/explore/', label: 'Explore' },
  { href: '/home-assistant/', label: 'Home Assistant' },
  { href: '/premium/', label: 'Premium', emphasize: true },
  { href: '/docs/', label: 'Docs' },
];
```

- [ ] **Step 6: Build and verify**

Run: `cd website && npm run build`

Expected: Build succeeds. Explore page exists in static output.

- [ ] **Step 7: Commit**

```bash
cd website && git add src/pages/explore.astro src/components/ExploreMap.tsx src/components/SpotCard.astro src/components/Header.astro package.json package-lock.json astro.config.mjs
git commit -m "feat: add explore page with Leaflet map and nearby spots"
```

---

## Task 10: SEO and Open Graph Tags

**Files:**
- Modify: `website/src/pages/spot/[slug].astro`
- Modify: `website/src/components/SEOHead.astro`

- [ ] **Step 1: Check existing SEOHead component**

Read `website/src/components/SEOHead.astro` to understand the current OG tag pattern.

- [ ] **Step 2: Add Open Graph tags to spot page**

In the spot page's frontmatter, the `title` and `description` are already set. Add OG tags by passing them through the layout or adding them directly. In the BaseLayout's `<head>`, the SEOHead component handles meta tags.

If SEOHead accepts `ogTitle`/`ogDescription` props, pass them. Otherwise, add OG meta tags directly in the spot page's `<head>` slot or update SEOHead to support them.

Add to the spot page, inside a `<Fragment slot="head">` or via SEOHead props:

```html
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:type" content="website" />
<meta property="og:url" content={`https://paddleconditions.com/spot/${slug}`} />
```

- [ ] **Step 3: Build and verify**

Run: `cd website && npm run build`

View source of a spot page to confirm OG tags are present.

- [ ] **Step 4: Commit**

```bash
cd website && git add src/pages/spot/ src/components/SEOHead.astro
git commit -m "feat: add Open Graph tags to spot pages for social sharing"
```

---

## Task 11: Changelog & Docs Update

**Files:**
- Modify: `website/data/changelog.json`
- Create or modify: `website/src/pages/docs/web-app/sharing.astro` (optional)

Per CLAUDE.md, every change must update the changelog.

- [ ] **Step 1: Update changelog**

Add entries to `website/data/changelog.json` for:
- Public spot pages with shareable URLs
- Explore nearby spots page with interactive map
- Share button in the web app

- [ ] **Step 2: Commit**

```bash
cd website && git add data/changelog.json
git commit -m "docs: add changelog entries for sharing and explore features"
```

---

## Task 12: Deploy & Verify

This task covers production deployment and manual verification.

- [ ] **Step 1: Run API migration on production**

SSH to prod and apply the migration:
```bash
ssh -i ~/.ssh/paddleconditions_prod -p 11208 devsac@104.255.174.113
cd ~/public_html/api.paddleconditions.com
node -e "..." # or apply migration SQL directly via mysql
```

Then run the backfill script via tunnel.

- [ ] **Step 2: Set up Passenger for website on cPanel**

In cPanel, create a Node.js application:
- Application root: `public_html/paddleconditions.com`
- Application URL: `paddleconditions.com`
- Application startup file: `dist/server/entry.mjs`
- Node version: 22.x

- [ ] **Step 3: Push API changes and verify deploy**

```bash
cd api && git push origin main
```

Wait for GitHub Actions to deploy. Verify:
```bash
curl https://api.paddleconditions.com/public/spot/lake-tahoe
```

Expected: JSON response with waterBody and conditions.

- [ ] **Step 4: Push website changes and verify deploy**

```bash
cd website && git push origin main
```

Wait for deploy. Verify:
- `https://paddleconditions.com/spot/lake-tahoe` renders conditions
- `https://paddleconditions.com/explore` shows map and cards
- Navigation has "Explore" link

- [ ] **Step 5: Push app changes and verify**

```bash
cd app && git push origin main
```

Verify share button appears on a location detail page (only for locations with linked water bodies).

- [ ] **Step 6: Test social sharing**

Share a spot URL on a messaging app. Verify the OG preview shows the spot name and conditions summary.
