# SEO & Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make spot pages discoverable via search engines and social sharing. Add browse pages, dynamic sitemap, structured data, OG images, and richer spot page content.

**Architecture:** API-first. New `/public/spots/directory` endpoint feeds both the static browse pages (built at Astro build time) and the OG image generation script. Spot detail pages stay SSR. The Astro sitemap plugin's `customSitemaps` option wires the dynamic sitemap into the existing index.

**Tech Stack:** Fastify + mysql2 (API), Astro 6 + Tailwind 4 (website), Satori + Sharp (OG images)

**Spec:** `docs/superpowers/specs/2026-04-08-seo-discovery-design.md`

---

## File Structure

### API (`api/`)
- **Create:** `src/routes/public/directory.ts` - Directory endpoint returning all water bodies grouped by state
- **Create:** `src/lib/us-states.ts` - State code to name/slug mapping utility
- **Create:** `src/db/migrations/0011_add_description.sql` - Add description column to water_bodies
- **Create:** `tests/routes/public/directory.test.ts` - Tests for directory endpoint
- **Modify:** `src/routes/public/spot.ts` - Add popularity increment + description field
- **Modify:** `src/db/schema.ts` - Add description column to schema
- **Modify:** `src/db/migrations/meta/_journal.json` - Register new migration
- **Modify:** `src/index.ts` - Register directory route
- **Modify:** `tests/helpers/app.ts` - Register directory route in test app
- **Modify:** `tests/routes/public/spot.test.ts` - Test description field + popularity increment

### Website (`website/`)
- **Create:** `src/pages/spots/index.astro` - Browse index page
- **Create:** `src/pages/spots/[state].astro` - State browse page (static)
- **Create:** `src/pages/sitemap-spots.xml.ts` - Dynamic sitemap endpoint
- **Create:** `src/components/SpotJsonLd.astro` - JSON-LD structured data component
- **Create:** `src/components/NearbySpots.astro` - Nearby spots section component
- **Create:** `scripts/generate-og-images.ts` - OG image batch generation script
- **Modify:** `src/pages/spot/[slug].astro` - Add JSON-LD, nearby spots, description, OG image
- **Modify:** `src/pages/explore.astro` - Add cross-link to /spots
- **Modify:** `astro.config.mjs` - Add customSitemaps config

---

### Task 1: Database Migration - Add Description Column

**Files:**
- Create: `api/src/db/migrations/0011_add_description.sql`
- Modify: `api/src/db/migrations/meta/_journal.json`
- Modify: `api/src/db/schema.ts`

- [ ] **Step 1: Create the migration SQL**

Create `api/src/db/migrations/0011_add_description.sql`:

```sql
ALTER TABLE `water_bodies` ADD COLUMN `description` text DEFAULT NULL;
```

- [ ] **Step 2: Register migration in the journal**

Add this entry to the `entries` array in `api/src/db/migrations/meta/_journal.json`:

```json
{
  "idx": 11,
  "version": "5",
  "when": 1744156900000,
  "tag": "0011_add_description",
  "breakpoints": true
}
```

- [ ] **Step 3: Update the Drizzle schema**

In `api/src/db/schema.ts`, add the `description` column to the `waterBodies` table definition, after the `slug` line:

```typescript
description: text('description'),
```

- [ ] **Step 4: Verify types compile**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Run migration on the database**

Run: `cd api && mysql -u paddle_prod -p -P 11208 paddle_conditions < src/db/migrations/0011_add_description.sql`

(Use credentials from `.env.secrets`. Adapt host/port for local vs production.)

- [ ] **Step 6: Commit**

```bash
cd api && git add src/db/migrations/0011_add_description.sql src/db/migrations/meta/_journal.json src/db/schema.ts
git commit -m "feat: add description column to water_bodies"
```

---

### Task 2: US States Mapping Utility

**Files:**
- Create: `api/src/lib/us-states.ts`

- [ ] **Step 1: Create the state mapping module**

Create `api/src/lib/us-states.ts`:

```typescript
export interface StateInfo {
  code: string;
  name: string;
  slug: string;
}

const STATES: StateInfo[] = [
  { code: 'AL', name: 'Alabama', slug: 'alabama' },
  { code: 'AK', name: 'Alaska', slug: 'alaska' },
  { code: 'AZ', name: 'Arizona', slug: 'arizona' },
  { code: 'AR', name: 'Arkansas', slug: 'arkansas' },
  { code: 'CA', name: 'California', slug: 'california' },
  { code: 'CO', name: 'Colorado', slug: 'colorado' },
  { code: 'CT', name: 'Connecticut', slug: 'connecticut' },
  { code: 'DE', name: 'Delaware', slug: 'delaware' },
  { code: 'FL', name: 'Florida', slug: 'florida' },
  { code: 'GA', name: 'Georgia', slug: 'georgia' },
  { code: 'HI', name: 'Hawaii', slug: 'hawaii' },
  { code: 'ID', name: 'Idaho', slug: 'idaho' },
  { code: 'IL', name: 'Illinois', slug: 'illinois' },
  { code: 'IN', name: 'Indiana', slug: 'indiana' },
  { code: 'IA', name: 'Iowa', slug: 'iowa' },
  { code: 'KS', name: 'Kansas', slug: 'kansas' },
  { code: 'KY', name: 'Kentucky', slug: 'kentucky' },
  { code: 'LA', name: 'Louisiana', slug: 'louisiana' },
  { code: 'ME', name: 'Maine', slug: 'maine' },
  { code: 'MD', name: 'Maryland', slug: 'maryland' },
  { code: 'MA', name: 'Massachusetts', slug: 'massachusetts' },
  { code: 'MI', name: 'Michigan', slug: 'michigan' },
  { code: 'MN', name: 'Minnesota', slug: 'minnesota' },
  { code: 'MS', name: 'Mississippi', slug: 'mississippi' },
  { code: 'MO', name: 'Missouri', slug: 'missouri' },
  { code: 'MT', name: 'Montana', slug: 'montana' },
  { code: 'NE', name: 'Nebraska', slug: 'nebraska' },
  { code: 'NV', name: 'Nevada', slug: 'nevada' },
  { code: 'NH', name: 'New Hampshire', slug: 'new-hampshire' },
  { code: 'NJ', name: 'New Jersey', slug: 'new-jersey' },
  { code: 'NM', name: 'New Mexico', slug: 'new-mexico' },
  { code: 'NY', name: 'New York', slug: 'new-york' },
  { code: 'NC', name: 'North Carolina', slug: 'north-carolina' },
  { code: 'ND', name: 'North Dakota', slug: 'north-dakota' },
  { code: 'OH', name: 'Ohio', slug: 'ohio' },
  { code: 'OK', name: 'Oklahoma', slug: 'oklahoma' },
  { code: 'OR', name: 'Oregon', slug: 'oregon' },
  { code: 'PA', name: 'Pennsylvania', slug: 'pennsylvania' },
  { code: 'RI', name: 'Rhode Island', slug: 'rhode-island' },
  { code: 'SC', name: 'South Carolina', slug: 'south-carolina' },
  { code: 'SD', name: 'South Dakota', slug: 'south-dakota' },
  { code: 'TN', name: 'Tennessee', slug: 'tennessee' },
  { code: 'TX', name: 'Texas', slug: 'texas' },
  { code: 'UT', name: 'Utah', slug: 'utah' },
  { code: 'VT', name: 'Vermont', slug: 'vermont' },
  { code: 'VA', name: 'Virginia', slug: 'virginia' },
  { code: 'WA', name: 'Washington', slug: 'washington' },
  { code: 'WV', name: 'West Virginia', slug: 'west-virginia' },
  { code: 'WI', name: 'Wisconsin', slug: 'wisconsin' },
  { code: 'WY', name: 'Wyoming', slug: 'wyoming' },
];

const byCode = new Map(STATES.map((s) => [s.code, s]));
const bySlug = new Map(STATES.map((s) => [s.slug, s]));

export function stateByCode(code: string): StateInfo | undefined {
  return byCode.get(code.toUpperCase());
}

export function stateBySlug(slug: string): StateInfo | undefined {
  return bySlug.get(slug.toLowerCase());
}

export function allStates(): StateInfo[] {
  return STATES;
}
```

- [ ] **Step 2: Verify types compile**

Run: `cd api && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd api && git add src/lib/us-states.ts
git commit -m "feat: add US states code/name/slug mapping utility"
```

---

### Task 3: Directory API Endpoint

**Files:**
- Create: `api/src/routes/public/directory.ts`
- Create: `api/tests/routes/public/directory.test.ts`
- Modify: `api/src/index.ts`
- Modify: `api/tests/helpers/app.ts`

- [ ] **Step 1: Write the failing test**

Create `api/tests/routes/public/directory.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { v7 as uuidv7 } from 'uuid';
import { buildApp } from '../../helpers/app.js';
import type { FastifyInstance } from 'fastify';

describe('GET /public/spots/directory', () => {
  let app: FastifyInstance;

  beforeEach(async () => {
    app = await buildApp();
    await app.dbPool.execute(
      `DELETE FROM water_bodies WHERE source = 'manual' AND source_id LIKE 'test-dir-%'`,
    );
  });

  async function insertWaterBody(overrides: Record<string, any> = {}) {
    const id = uuidv7();
    const slug = overrides.slug ?? `test-dir-${id}`;
    await app.dbPool.execute(
      `INSERT INTO water_bodies (id, name, type, state, county, lat, lng, source, source_id, slug, popularity)
       VALUES (?, ?, ?, ?, ?, ?, ?, 'manual', ?, ?, ?)`,
      [
        id,
        overrides.name ?? 'Test Lake',
        overrides.type ?? 'lake',
        overrides.state ?? 'CA',
        overrides.county ?? 'Test County',
        overrides.lat ?? '38.5000',
        overrides.lng ?? '-121.0000',
        `test-dir-${id}`,
        slug,
        overrides.popularity ?? 0,
      ],
    );
    return { id, slug };
  }

  it('returns 200 with states grouped by state code', async () => {
    await insertWaterBody({ name: 'Lake Alpha', state: 'CA', type: 'lake' });
    await insertWaterBody({ name: 'River Beta', state: 'CA', type: 'river' });
    await insertWaterBody({ name: 'Lake Gamma', state: 'NV', type: 'lake' });

    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/directory',
    });

    expect(res.statusCode).toBe(200);
    const body = res.json();
    expect(body.totalSpots).toBeGreaterThanOrEqual(3);
    expect(body.states).toBeInstanceOf(Array);

    const ca = body.states.find((s: any) => s.slug === 'california');
    expect(ca).toBeDefined();
    expect(ca.state).toBe('California');
    expect(ca.count).toBeGreaterThanOrEqual(2);
    expect(ca.spots.length).toBeGreaterThanOrEqual(2);
    expect(ca.spots[0]).toHaveProperty('name');
    expect(ca.spots[0]).toHaveProperty('slug');
    expect(ca.spots[0]).toHaveProperty('type');
    expect(ca.spots[0]).toHaveProperty('county');
  });

  it('returns spots sorted by popularity within each state', async () => {
    await insertWaterBody({ name: 'Popular Lake', state: 'CA', popularity: 100 });
    await insertWaterBody({ name: 'Unknown Lake', state: 'CA', popularity: 0 });

    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/directory',
    });

    const body = res.json();
    const ca = body.states.find((s: any) => s.slug === 'california');
    const names = ca.spots.map((s: any) => s.name);
    const popularIdx = names.indexOf('Popular Lake');
    const unknownIdx = names.indexOf('Unknown Lake');
    expect(popularIdx).toBeLessThan(unknownIdx);
  });

  it('sets cache-control header', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/directory',
    });

    expect(res.headers['cache-control']).toBe('public, s-maxage=3600, max-age=3600');
  });

  it('includes top spots sorted by popularity', async () => {
    const res = await app.inject({
      method: 'GET',
      url: '/public/spots/directory',
    });

    expect(res.json()).toHaveProperty('topSpots');
    expect(res.json().topSpots).toBeInstanceOf(Array);
  });
});
```

- [ ] **Step 2: Register the route in the test app helper**

In `api/tests/helpers/app.ts`, add after the `publicNearbyRoute` import:

```typescript
import publicDirectoryRoute from '../../src/routes/public/directory.js';
```

And after `await app.register(publicNearbyRoute);`:

```typescript
await app.register(publicDirectoryRoute);
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd api && npx vitest run tests/routes/public/directory.test.ts`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement the directory endpoint**

Create `api/src/routes/public/directory.ts`:

```typescript
import type { FastifyInstance } from 'fastify';
import { stateByCode } from '../../lib/us-states.js';

interface SpotRow {
  name: string;
  slug: string;
  type: string;
  county: string | null;
  state: string;
  popularity: number;
}

interface StateGroup {
  state: string;
  slug: string;
  count: number;
  spots: { name: string; slug: string; type: string; county: string | null }[];
}

export default async function publicDirectoryRoute(app: FastifyInstance) {
  app.get(
    '/public/spots/directory',
    {
      config: {
        rateLimit: { max: 10, timeWindow: '1 minute' },
      },
    },
    async (_request, reply) => {
      const [rows] = await app.dbPool.execute(
        `SELECT name, slug, type, county, state, popularity
         FROM water_bodies
         ORDER BY state ASC, popularity DESC, name ASC`,
      );

      const spotRows = rows as SpotRow[];

      // Group by state
      const stateMap = new Map<string, SpotRow[]>();
      for (const row of spotRows) {
        const existing = stateMap.get(row.state);
        if (existing) {
          existing.push(row);
        } else {
          stateMap.set(row.state, [row]);
        }
      }

      const states: StateGroup[] = [];
      for (const [code, spots] of stateMap) {
        const info = stateByCode(code);
        if (!info) continue; // Skip unknown state codes
        states.push({
          state: info.name,
          slug: info.slug,
          count: spots.length,
          spots: spots.map((s) => ({
            name: s.name,
            slug: s.slug,
            type: s.type,
            county: s.county,
          })),
        });
      }

      // Sort states alphabetically
      states.sort((a, b) => a.state.localeCompare(b.state));

      // Top spots across all states by popularity
      const topSpots = spotRows
        .sort((a, b) => b.popularity - a.popularity)
        .slice(0, 20)
        .map((s) => {
          const info = stateByCode(s.state);
          return {
            name: s.name,
            slug: s.slug,
            type: s.type,
            state: info?.name ?? s.state,
            stateSlug: info?.slug ?? s.state.toLowerCase(),
          };
        });

      reply.header('Cache-Control', 'public, s-maxage=3600, max-age=3600');
      return {
        states,
        totalSpots: spotRows.length,
        topSpots,
      };
    },
  );
}
```

- [ ] **Step 5: Register the route in the main app**

In `api/src/index.ts`, add after the `publicNearbyRoute` import:

```typescript
import publicDirectoryRoute from './routes/public/directory.js';
```

And after `await app.register(publicNearbyRoute);`:

```typescript
await app.register(publicDirectoryRoute);
```

- [ ] **Step 6: Run the tests**

Run: `cd api && npx vitest run tests/routes/public/directory.test.ts`
Expected: All 4 tests PASS

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `cd api && npx vitest run`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
cd api && git add src/routes/public/directory.ts tests/routes/public/directory.test.ts src/index.ts tests/helpers/app.ts
git commit -m "feat: add /public/spots/directory endpoint for browse pages"
```

---

### Task 4: Modify Spot Endpoint - Popularity Increment + Description

**Files:**
- Modify: `api/src/routes/public/spot.ts`
- Modify: `api/tests/routes/public/spot.test.ts`

- [ ] **Step 1: Write the failing tests**

Add these tests to the existing `describe` block in `api/tests/routes/public/spot.test.ts`:

```typescript
it('increments popularity on each request', async () => {
  const { slug } = await insertWaterBody({ name: 'Popular Lake' });

  // Get initial popularity
  const [before] = await app.dbPool.execute(
    `SELECT popularity FROM water_bodies WHERE slug = ?`,
    [slug],
  );
  const initialPop = (before as any[])[0].popularity;

  await app.inject({ method: 'GET', url: `/public/spot/${slug}` });

  // Wait briefly for the fire-and-forget to complete
  await new Promise((r) => setTimeout(r, 100));

  const [after] = await app.dbPool.execute(
    `SELECT popularity FROM water_bodies WHERE slug = ?`,
    [slug],
  );
  expect((after as any[])[0].popularity).toBe(initialPop + 1);
});

it('returns description field when set', async () => {
  const { id, slug } = await insertWaterBody({ name: 'Described Lake' });
  await app.dbPool.execute(
    `UPDATE water_bodies SET description = ? WHERE id = ?`,
    ['A beautiful lake for paddling.', id],
  );

  const res = await app.inject({ method: 'GET', url: `/public/spot/${slug}` });
  const body = res.json();
  expect(body.waterBody.description).toBe('A beautiful lake for paddling.');
});

it('returns null description when not set', async () => {
  const { slug } = await insertWaterBody({ name: 'No Description Lake' });

  const res = await app.inject({ method: 'GET', url: `/public/spot/${slug}` });
  const body = res.json();
  expect(body.waterBody.description).toBeNull();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd api && npx vitest run tests/routes/public/spot.test.ts`
Expected: FAIL (description not in response, popularity not incrementing)

- [ ] **Step 3: Update the spot endpoint**

Modify `api/src/routes/public/spot.ts`. Update the SELECT to include `description`:

```typescript
const [wbRows] = await app.dbPool.execute(
  `SELECT id, name, type, state, county, lat, lng, slug, description
   FROM water_bodies WHERE slug = ? LIMIT 1`,
  [slug],
);
```

Add `description` to the waterBody response object:

```typescript
const waterBody = {
  id: wb.id,
  name: wb.name,
  type: wb.type,
  state: wb.state,
  county: wb.county,
  lat: parseFloat(wb.lat),
  lng: parseFloat(wb.lng),
  slug: wb.slug,
  description: wb.description ?? null,
};
```

Add the non-blocking popularity increment right after the `const wb = rows[0];` line:

```typescript
// Non-blocking popularity increment
app.dbPool.execute(
  'UPDATE water_bodies SET popularity = popularity + 1 WHERE slug = ?',
  [slug],
).catch((err) => request.log.error(err, 'popularity increment failed'));
```

- [ ] **Step 4: Run the tests**

Run: `cd api && npx vitest run tests/routes/public/spot.test.ts`
Expected: All tests PASS (including the 3 new ones)

- [ ] **Step 5: Commit**

```bash
cd api && git add src/routes/public/spot.ts tests/routes/public/spot.test.ts
git commit -m "feat: add description field and popularity tracking to spot endpoint"
```

---

### Task 5: Astro Config - Custom Sitemaps

**Files:**
- Modify: `website/astro.config.mjs`

- [ ] **Step 1: Update sitemap config**

In `website/astro.config.mjs`, update the sitemap integration:

```javascript
integrations: [sitemap({
  filter: (page) => !page.includes('/404'),
  customSitemaps: ['https://paddleconditions.com/sitemap-spots.xml'],
}), react()],
```

- [ ] **Step 2: Verify build succeeds**

Run: `cd website && npx astro build`
Expected: Build succeeds. Check that `dist/client/sitemap-index.xml` includes a reference to `sitemap-spots.xml`.

- [ ] **Step 3: Commit**

```bash
cd website && git add astro.config.mjs
git commit -m "feat: add spots sitemap to sitemap index via customSitemaps"
```

---

### Task 6: Dynamic Sitemap Endpoint

**Files:**
- Create: `website/src/pages/sitemap-spots.xml.ts`

- [ ] **Step 1: Create the SSR sitemap endpoint**

Create `website/src/pages/sitemap-spots.xml.ts`:

```typescript
export const prerender = false;

import type { APIRoute } from 'astro';

const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';
const SITE = 'https://paddleconditions.com';

export const GET: APIRoute = async ({ request }) => {
  let states: { slug: string; spots: { slug: string }[] }[] = [];

  try {
    const res = await fetch(`${API_BASE}/public/spots/directory`);
    if (res.ok) {
      const data = await res.json();
      states = data.states;
    }
  } catch {
    // Return empty sitemap on API failure
  }

  const urls: string[] = [];

  // /spots index
  urls.push(`  <url>
    <loc>${SITE}/spots/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>`);

  // State pages
  for (const state of states) {
    urls.push(`  <url>
    <loc>${SITE}/spots/${state.slug}/</loc>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>`);

    // Spot pages
    for (const spot of state.spots) {
      urls.push(`  <url>
    <loc>${SITE}/spot/${spot.slug}/</loc>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>`);
    }
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join('\n')}
</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'public, s-maxage=3600, max-age=3600',
    },
  });
};
```

- [ ] **Step 2: Test locally**

Run: `cd website && npx astro dev`

Visit `http://localhost:4321/sitemap-spots.xml` in a browser. Verify it returns valid XML with spot URLs. (Requires the API to be running.)

- [ ] **Step 3: Commit**

```bash
cd website && git add src/pages/sitemap-spots.xml.ts
git commit -m "feat: add dynamic sitemap for spot and browse pages"
```

---

### Task 7: SpotJsonLd Component

**Files:**
- Create: `website/src/components/SpotJsonLd.astro`

- [ ] **Step 1: Create the structured data component**

Create `website/src/components/SpotJsonLd.astro`:

```astro
---
interface Props {
  name: string;
  type: string;
  state: string;
  county: string | null;
  lat: number;
  lng: number;
  description: string | null;
  pageTitle: string;
  pageDescription: string;
}

const { name, type, state, county, lat, lng, description, pageTitle, pageDescription } = Astro.props;

const typeMap: Record<string, string> = {
  lake: 'https://schema.org/LakeBodyOfWater',
  river: 'https://schema.org/RiverBodyOfWater',
  reservoir: 'https://schema.org/Reservoir',
  bay: 'https://schema.org/BodyOfWater',
  coastal: 'https://schema.org/BodyOfWater',
};

const locationDesc = description ?? `${name} is a ${type} in ${county ? `${county}, ` : ''}${state}.`;

const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: pageTitle,
  description: pageDescription,
  mainEntity: {
    '@type': 'Place',
    name,
    description: locationDesc,
    geo: {
      '@type': 'GeoCoordinates',
      latitude: lat,
      longitude: lng,
    },
    ...(typeMap[type] ? { additionalType: typeMap[type] } : {}),
  },
};
---

<script type="application/ld+json" set:html={JSON.stringify(jsonLd)} />
```

- [ ] **Step 2: Commit**

```bash
cd website && git add src/components/SpotJsonLd.astro
git commit -m "feat: add SpotJsonLd structured data component"
```

---

### Task 8: NearbySpots Component

**Files:**
- Create: `website/src/components/NearbySpots.astro`

- [ ] **Step 1: Create the nearby spots component**

Create `website/src/components/NearbySpots.astro`:

```astro
---
interface NearbySpot {
  waterBody: {
    name: string;
    slug: string;
    type: string;
    distanceMiles: number;
  };
}

interface Props {
  lat: number;
  lng: number;
  currentSlug: string;
}

const { lat, lng, currentSlug } = Astro.props;
const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';

let nearbySpots: NearbySpot[] = [];

try {
  const res = await fetch(
    `${API_BASE}/public/spots/nearby?lat=${lat}&lng=${lng}&limit=6&radius=100`,
  );
  if (res.ok) {
    const data = await res.json();
    nearbySpots = (data.spots as NearbySpot[]).filter(
      (s) => s.waterBody.slug !== currentSlug,
    ).slice(0, 5);
  }
} catch {
  // Silently fail - nearby spots are supplemental
}

const typeLabels: Record<string, string> = {
  lake: 'Lake',
  river: 'River',
  reservoir: 'Reservoir',
  bay: 'Bay',
  coastal: 'Coastal',
};
---

{nearbySpots.length > 0 && (
  <div class="mt-8">
    <h2 class="text-lg font-bold text-slate-900 mb-4">Nearby Spots</h2>
    <div class="grid gap-3">
      {nearbySpots.map((s) => (
        <a
          href={`/spot/${s.waterBody.slug}/`}
          class="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-sky-200 hover:shadow-sm transition-all"
        >
          <div class="flex items-center gap-2">
            <span class="font-medium text-slate-900">{s.waterBody.name}</span>
            <span class="bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded text-[10px] font-semibold">
              {typeLabels[s.waterBody.type] ?? s.waterBody.type.toUpperCase()}
            </span>
          </div>
          <span class="text-sm text-slate-400">{s.waterBody.distanceMiles} mi</span>
        </a>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
cd website && git add src/components/NearbySpots.astro
git commit -m "feat: add NearbySpots component for spot page internal linking"
```

---

### Task 9: Enhance Spot Detail Page

**Files:**
- Modify: `website/src/pages/spot/[slug].astro`

- [ ] **Step 1: Add imports and structured data**

In `website/src/pages/spot/[slug].astro`, add imports after the existing ones:

```astro
import SpotJsonLd from '../../components/SpotJsonLd.astro';
import NearbySpots from '../../components/NearbySpots.astro';
```

Update the API SELECT to also include `description` (already returned by the updated endpoint, just need to use it).

Add the `stateNames` mapping for auto-generated descriptions. Add after the `typeLabels` const:

```typescript
const stateNames: Record<string, string> = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri',
  MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
  NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
  OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
};

const spotDescription = wb?.description
  ?? (wb ? `${wb.name} is a ${wb.type} in ${wb.county ? `${wb.county}, ` : ''}${stateNames[wb.state] ?? wb.state}.` : '');
```

- [ ] **Step 2: Update the OG image path**

Change the `BaseLayout` opening tag to pass the custom OG image:

```astro
<BaseLayout title={title} description={description} ogImage={wb ? `/og/${wb.slug}.png` : undefined}>
```

Note: `BaseLayout` needs to pass `ogImage` through to `SEOHead`. Check if it already does. If not, add `ogImage` to BaseLayout's Props interface and pass it to `<SEOHead ogImage={ogImage} />`.

- [ ] **Step 3: Add JSON-LD and description section to the template**

Inside the `{wb && !error && (...)}` block, add the JSON-LD component right after the opening `<>`:

```astro
<SpotJsonLd
  name={wb.name}
  type={wb.type}
  state={wb.state}
  county={wb.county}
  lat={wb.lat}
  lng={wb.lng}
  description={wb.description}
  pageTitle={title}
  pageDescription={description}
/>
```

Add the description section after the conditions grid / no-data block and before the premium CTA:

```astro
{spotDescription && (
  <div class="mb-8">
    <h2 class="text-base font-semibold text-slate-900 mb-2">About {wb.name}</h2>
    <p class="text-sm text-slate-600 leading-relaxed">{spotDescription}</p>
  </div>
)}
```

Add NearbySpots after the map:

```astro
<NearbySpots lat={wb.lat} lng={wb.lng} currentSlug={wb.slug} />
```

- [ ] **Step 4: Update BaseLayout to pass ogImage (if needed)**

Check `website/src/layouts/BaseLayout.astro`. If it doesn't accept `ogImage`, add it:

In the Props interface:
```typescript
interface Props {
  title?: string;
  description?: string;
  ogImage?: string;
}
```

In the destructuring:
```typescript
const { title, description, ogImage } = Astro.props;
```

Pass to SEOHead:
```astro
<SEOHead title={title} description={description} ogImage={ogImage} />
```

- [ ] **Step 5: Test locally**

Run: `cd website && npx astro dev`

Visit `http://localhost:4321/spot/lake-tahoe` (or any valid slug). Verify:
- JSON-LD appears in page source
- Description section shows auto-generated text
- Nearby spots section appears below the map
- No console errors

- [ ] **Step 6: Commit**

```bash
cd website && git add src/pages/spot/[slug].astro src/layouts/BaseLayout.astro
git commit -m "feat: add structured data, description, nearby spots, and OG image to spot pages"
```

---

### Task 10: Browse Index Page (`/spots`)

**Files:**
- Create: `website/src/pages/spots/index.astro`

- [ ] **Step 1: Create the browse index page**

Create `website/src/pages/spots/index.astro`:

```astro
---
import BaseLayout from '../../layouts/BaseLayout.astro';

const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';

let states: any[] = [];
let topSpots: any[] = [];
let totalSpots = 0;

try {
  const res = await fetch(`${API_BASE}/public/spots/directory`);
  if (res.ok) {
    const data = await res.json();
    states = data.states;
    topSpots = data.topSpots;
    totalSpots = data.totalSpots;
  }
} catch {
  // Build will use empty data
}

const typeLabels: Record<string, string> = {
  lake: 'Lake', river: 'River', reservoir: 'Reservoir', bay: 'Bay', coastal: 'Coastal',
};
---

<BaseLayout
  title="Paddle Spots - Find Lakes, Rivers & Reservoirs | Paddle Conditions"
  description={`Browse ${totalSpots} paddle spots across the US. Find lakes, rivers, and reservoirs with current conditions.`}
>
  <div class="max-w-5xl mx-auto px-4 py-12">
    {/* Header */}
    <div class="text-center mb-10">
      <h1 class="text-3xl font-bold text-slate-900 mb-3">Paddle Spots</h1>
      <p class="text-slate-600 max-w-lg mx-auto">
        Browse {totalSpots.toLocaleString()} spots across the US. Find current conditions for lakes, rivers, and reservoirs.
      </p>
      <a href="/explore/" class="inline-block mt-3 text-sm text-sky-600 hover:text-sky-700 font-medium">
        Or explore the map &rarr;
      </a>
    </div>

    {/* Search filter */}
    <div class="mb-10">
      <input
        type="text"
        id="spot-search"
        placeholder="Filter by name..."
        class="w-full max-w-md mx-auto block px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400"
      />
    </div>

    {/* Popular Spots */}
    {topSpots.length > 0 && (
      <section class="mb-12" data-search-section>
        <h2 class="text-xl font-bold text-slate-900 mb-4">Popular Spots</h2>
        <div class="grid sm:grid-cols-2 gap-3">
          {topSpots.map((spot: any) => (
            <a
              href={`/spot/${spot.slug}/`}
              class="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-sky-200 hover:shadow-sm transition-all"
              data-search-name={spot.name.toLowerCase()}
            >
              <div class="flex items-center gap-2">
                <span class="font-medium text-slate-900">{spot.name}</span>
                <span class="bg-sky-100 text-sky-700 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                  {typeLabels[spot.type] ?? spot.type.toUpperCase()}
                </span>
              </div>
              <span class="text-sm text-slate-400">{spot.state}</span>
            </a>
          ))}
        </div>
      </section>
    )}

    {/* State Grid */}
    <section>
      <h2 class="text-xl font-bold text-slate-900 mb-4">Browse by State</h2>
      <div class="grid sm:grid-cols-2 md:grid-cols-3 gap-3" id="state-grid">
        {states.map((state: any) => (
          <a
            href={`/spots/${state.slug}/`}
            class="p-4 rounded-xl border border-slate-200 hover:border-sky-200 hover:shadow-sm transition-all"
            data-search-name={state.state.toLowerCase()}
          >
            <div class="font-medium text-slate-900">{state.state}</div>
            <div class="text-sm text-slate-400">{state.count} {state.count === 1 ? 'spot' : 'spots'}</div>
          </a>
        ))}
      </div>
    </section>
  </div>

  <script>
    const input = document.getElementById('spot-search') as HTMLInputElement;
    if (input) {
      input.addEventListener('input', () => {
        const query = input.value.toLowerCase().trim();
        document.querySelectorAll('[data-search-name]').forEach((el) => {
          const name = (el as HTMLElement).dataset.searchName ?? '';
          (el as HTMLElement).style.display = name.includes(query) ? '' : 'none';
        });
      });
    }
  </script>
</BaseLayout>
```

- [ ] **Step 2: Test locally**

Run: `cd website && npx astro dev`

Visit `http://localhost:4321/spots/`. Verify:
- State grid loads with counts
- Popular spots section appears
- Search filter works (type to filter)
- Links to `/spots/[state]` and `/spot/[slug]` work

- [ ] **Step 3: Commit**

```bash
cd website && git add src/pages/spots/index.astro
git commit -m "feat: add /spots browse index page with state grid and popular spots"
```

---

### Task 11: State Browse Page (`/spots/[state]`)

**Files:**
- Create: `website/src/pages/spots/[state].astro`

- [ ] **Step 1: Create the state page with getStaticPaths**

Create `website/src/pages/spots/[state].astro`:

```astro
---
import BaseLayout from '../../layouts/BaseLayout.astro';

export async function getStaticPaths() {
  const API_BASE = import.meta.env.API_BASE ?? 'https://api.paddleconditions.com';

  try {
    const res = await fetch(`${API_BASE}/public/spots/directory`);
    if (!res.ok) return [];
    const data = await res.json();

    return data.states.map((state: any) => ({
      params: { state: state.slug },
      props: { stateName: state.state, spots: state.spots, count: state.count },
    }));
  } catch {
    return [];
  }
}

interface Props {
  stateName: string;
  spots: { name: string; slug: string; type: string; county: string | null }[];
  count: number;
}

const { state } = Astro.params;
const { stateName, spots, count } = Astro.props;

const typeLabels: Record<string, string> = {
  lake: 'Lakes', river: 'Rivers', reservoir: 'Reservoirs', bay: 'Bays', coastal: 'Coastal',
};

const typeOrder = ['lake', 'river', 'reservoir', 'bay', 'coastal'];

// Group spots by type
const grouped = new Map<string, typeof spots>();
for (const spot of spots) {
  const existing = grouped.get(spot.type);
  if (existing) {
    existing.push(spot);
  } else {
    grouped.set(spot.type, [spot]);
  }
}

const sortedGroups = typeOrder
  .filter((t) => grouped.has(t))
  .map((t) => ({ type: t, label: typeLabels[t] ?? t, spots: grouped.get(t)! }));
---

<BaseLayout
  title={`Paddle Spots in ${stateName} | Paddle Conditions`}
  description={`Browse ${count} paddle spots in ${stateName}. Lakes, rivers, reservoirs and more with current conditions.`}
>
  <div class="max-w-5xl mx-auto px-4 py-12">
    {/* Breadcrumb */}
    <nav class="text-sm text-slate-400 mb-6">
      <a href="/spots/" class="hover:text-sky-600">All Spots</a>
      <span class="mx-1.5">/</span>
      <span class="text-slate-700">{stateName}</span>
    </nav>

    <div class="mb-8">
      <h1 class="text-3xl font-bold text-slate-900 mb-2">Paddle Spots in {stateName}</h1>
      <p class="text-slate-600">{count} {count === 1 ? 'spot' : 'spots'} available</p>
    </div>

    {/* Type filter buttons */}
    {sortedGroups.length > 1 && (
      <div class="flex flex-wrap gap-2 mb-8" id="type-filters">
        <button
          class="px-3 py-1.5 rounded-lg text-sm font-medium border border-sky-200 bg-sky-50 text-sky-700"
          data-filter="all"
        >
          All ({count})
        </button>
        {sortedGroups.map((g) => (
          <button
            class="px-3 py-1.5 rounded-lg text-sm font-medium border border-slate-200 text-slate-600 hover:border-sky-200 hover:text-sky-700"
            data-filter={g.type}
          >
            {g.label} ({g.spots.length})
          </button>
        ))}
      </div>
    )}

    {/* Spot groups */}
    {sortedGroups.map((group) => (
      <section class="mb-10" data-type-group={group.type}>
        <h2 class="text-lg font-bold text-slate-900 mb-3">{group.label}</h2>
        <div class="grid sm:grid-cols-2 gap-3">
          {group.spots.map((spot) => (
            <a
              href={`/spot/${spot.slug}/`}
              class="flex items-center justify-between p-3 rounded-xl border border-slate-200 hover:border-sky-200 hover:shadow-sm transition-all"
            >
              <span class="font-medium text-slate-900">{spot.name}</span>
              {spot.county && (
                <span class="text-sm text-slate-400">{spot.county}</span>
              )}
            </a>
          ))}
        </div>
      </section>
    ))}

    {/* Cross-link */}
    <div class="text-center mt-8">
      <a href="/explore/" class="text-sm text-sky-600 hover:text-sky-700 font-medium">
        Explore spots on the map &rarr;
      </a>
    </div>
  </div>

  <script>
    const filters = document.getElementById('type-filters');
    if (filters) {
      filters.addEventListener('click', (e) => {
        const btn = (e.target as HTMLElement).closest('button');
        if (!btn) return;
        const filter = btn.dataset.filter;

        // Update button styles
        filters.querySelectorAll('button').forEach((b) => {
          b.classList.remove('border-sky-200', 'bg-sky-50', 'text-sky-700');
          b.classList.add('border-slate-200', 'text-slate-600');
        });
        btn.classList.remove('border-slate-200', 'text-slate-600');
        btn.classList.add('border-sky-200', 'bg-sky-50', 'text-sky-700');

        // Show/hide groups
        document.querySelectorAll('[data-type-group]').forEach((section) => {
          (section as HTMLElement).style.display =
            filter === 'all' || (section as HTMLElement).dataset.typeGroup === filter
              ? ''
              : 'none';
        });
      });
    }
  </script>
</BaseLayout>
```

- [ ] **Step 2: Test locally**

Run: `cd website && npx astro dev`

Visit `http://localhost:4321/spots/california/`. Verify:
- Spots grouped by type
- Filter buttons work
- Links to individual spot pages work
- Breadcrumb links back to /spots/

- [ ] **Step 3: Commit**

```bash
cd website && git add src/pages/spots/
git commit -m "feat: add /spots/[state] static browse pages with type filters"
```

---

### Task 12: Cross-Link Explore Page

**Files:**
- Modify: `website/src/pages/explore.astro`

- [ ] **Step 1: Add cross-link to /spots**

In `website/src/pages/explore.astro`, add a link above or below the map component. Update the content inside `<BaseLayout>`:

```astro
<BaseLayout title="Explore Paddle Spots | Paddle Conditions" description="Find paddle spots near you. See current conditions for lakes, rivers, and reservoirs.">
  <div class="max-w-5xl mx-auto px-4 py-8">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold text-slate-900">Explore</h1>
      <a href="/spots/" class="text-sm text-sky-600 hover:text-sky-700 font-medium">
        Browse all spots &rarr;
      </a>
    </div>
    <ExploreMap client:load apiBase={API_BASE} />
  </div>
</BaseLayout>
```

- [ ] **Step 2: Commit**

```bash
cd website && git add src/pages/explore.astro
git commit -m "feat: add cross-link from /explore to /spots"
```

---

### Task 13: OG Image Generation Script

**Files:**
- Create: `website/scripts/generate-og-images.ts`

- [ ] **Step 1: Install satori**

Run: `cd website && npm install satori`

- [ ] **Step 2: Download a font file for Satori**

Satori requires explicit font buffers. Download Inter Bold:

Run: `mkdir -p website/scripts/fonts && curl -L -o website/scripts/fonts/Inter-Bold.woff "https://fonts.gstatic.com/s/inter/v18/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKv0.woff"`

- [ ] **Step 3: Create the generation script**

Create `website/scripts/generate-og-images.ts`:

```typescript
import satori from 'satori';
import sharp from 'sharp';
import { readFileSync, existsSync, mkdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = join(__dirname, '..', 'public', 'og');
const API_BASE = process.env.API_BASE ?? 'https://api.paddleconditions.com';
const FORCE = process.argv.includes('--force');

const fontData = readFileSync(join(__dirname, 'fonts', 'Inter-Bold.woff'));

const typeLabels: Record<string, string> = {
  lake: 'LAKE',
  river: 'RIVER',
  reservoir: 'RESERVOIR',
  bay: 'BAY',
  coastal: 'COASTAL',
};

async function generateImage(
  name: string,
  type: string,
  state: string,
): Promise<Buffer> {
  const svg = await satori(
    {
      type: 'div',
      props: {
        style: {
          width: '1200px',
          height: '630px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #0f172a 0%, #0c4a6e 100%)',
          color: 'white',
          fontFamily: 'Inter',
          padding: '60px',
        },
        children: [
          {
            type: 'div',
            props: {
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                marginBottom: '20px',
              },
              children: [
                {
                  type: 'div',
                  props: {
                    style: {
                      background: 'rgba(56, 189, 248, 0.2)',
                      border: '1px solid rgba(56, 189, 248, 0.4)',
                      borderRadius: '8px',
                      padding: '6px 14px',
                      fontSize: '18px',
                      letterSpacing: '1px',
                    },
                    children: typeLabels[type] ?? type.toUpperCase(),
                  },
                },
              ],
            },
          },
          {
            type: 'div',
            props: {
              style: {
                fontSize: name.length > 30 ? '48px' : '56px',
                fontWeight: 700,
                textAlign: 'center',
                lineHeight: 1.2,
                marginBottom: '16px',
              },
              children: name,
            },
          },
          {
            type: 'div',
            props: {
              style: {
                fontSize: '24px',
                opacity: 0.7,
              },
              children: state,
            },
          },
          {
            type: 'div',
            props: {
              style: {
                position: 'absolute',
                bottom: '40px',
                fontSize: '20px',
                opacity: 0.5,
              },
              children: 'paddleconditions.com',
            },
          },
        ],
      },
    },
    {
      width: 1200,
      height: 630,
      fonts: [
        {
          name: 'Inter',
          data: fontData,
          weight: 700,
          style: 'normal',
        },
      ],
    },
  );

  return sharp(Buffer.from(svg)).png().toBuffer();
}

async function main() {
  console.log(`Fetching spots from ${API_BASE}/public/spots/directory...`);
  const res = await fetch(`${API_BASE}/public/spots/directory`);
  if (!res.ok) {
    console.error(`API error: ${res.status} ${res.statusText}`);
    process.exit(1);
  }

  const data = await res.json();
  const allSpots: { name: string; slug: string; type: string; state: string }[] = [];

  for (const state of data.states) {
    for (const spot of state.spots) {
      allSpots.push({ ...spot, state: state.state });
    }
  }

  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  let generated = 0;
  let skipped = 0;
  let errors = 0;

  for (const spot of allSpots) {
    const outPath = join(OUTPUT_DIR, `${spot.slug}.png`);

    if (!FORCE && existsSync(outPath)) {
      skipped++;
      continue;
    }

    try {
      const buf = await generateImage(spot.name, spot.type, spot.state);
      writeFileSync(outPath, buf);
      generated++;
    } catch (err) {
      console.error(`Error generating ${spot.slug}:`, err);
      errors++;
    }
  }

  console.log(`Done. Generated: ${generated}, Skipped: ${skipped}, Errors: ${errors}`);
}

main();
```

- [ ] **Step 4: Test the script**

Run: `cd website && npx tsx scripts/generate-og-images.ts`

Expected: Images generated in `website/public/og/`. Check one to verify it looks correct (1200x630, dark gradient, spot name visible).

- [ ] **Step 5: Add og/ to .gitignore**

The generated PNGs are build artifacts. Add to `website/.gitignore` (create if needed):

```
public/og/
```

- [ ] **Step 6: Commit**

```bash
cd website && git add scripts/generate-og-images.ts scripts/fonts/Inter-Bold.woff .gitignore package.json package-lock.json
git commit -m "feat: add OG image batch generation script using Satori + Sharp"
```

---

### Task 14: Update Changelog and Docs

**Files:**
- Modify: `website/data/changelog.json`

- [ ] **Step 1: Add changelog entry**

Add a new entry at the beginning of the `website/data/changelog.json` array:

```json
{
  "date": "2026-04-08",
  "headline": "Spot Discovery & SEO",
  "entries": [
    {
      "type": "new-feature",
      "title": "Browse Spots",
      "text": "New /spots directory page. Browse paddle spots by state and water body type."
    },
    {
      "type": "new-feature",
      "title": "Spot Page Enhancements",
      "text": "Spot pages now show nearby spots, descriptions, and structured data for better search visibility."
    },
    {
      "type": "new-feature",
      "title": "Dynamic Sitemap",
      "text": "All spot pages are now included in the sitemap for search engine discovery."
    },
    {
      "type": "new-feature",
      "title": "Social Sharing Images",
      "text": "Each spot gets a custom OG image with the spot name and location for better social sharing previews."
    },
    {
      "type": "improvement",
      "title": "Popularity Tracking",
      "text": "Spot page views now contribute to popularity ranking, helping surface the most visited spots."
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
cd website && git add data/changelog.json
git commit -m "docs: add SEO & discovery changelog entry"
```

---

### Task 15: Build and Verify

- [ ] **Step 1: Build the API**

Run: `cd api && npm run build`
Expected: No TypeScript errors

- [ ] **Step 2: Run API tests**

Run: `cd api && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Build the website**

Run: `cd website && npx astro build`
Expected: Build succeeds. Static pages generated for /spots/ and /spots/[state]/. Check `dist/client/sitemap-index.xml` includes `sitemap-spots.xml`.

- [ ] **Step 4: Verify the built site**

Run: `cd website && npx astro preview`

Check:
- `/spots/` loads with state grid
- `/spots/california/` loads with grouped spots
- `/spot/lake-tahoe/` has JSON-LD in source, nearby spots section, description
- `/sitemap-spots.xml` returns valid XML
- `/sitemap-index.xml` references both `sitemap-0.xml` and `sitemap-spots.xml`
