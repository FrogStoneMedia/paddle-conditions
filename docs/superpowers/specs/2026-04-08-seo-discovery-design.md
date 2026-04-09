# SEO & Discovery Design Spec

## Overview

Make spot pages discoverable by search engines and shareable on social media. Add browse pages for organic discovery, a dynamic sitemap, structured data, per-spot OG images, and richer spot page content.

## 1. Browse Pages (Static, Pre-rendered)

### `/spots` - Index Page

- **Search bar** at the top. Client-side JavaScript filters the state grid and popular spots list by name as the user types. No API calls from the browser. For users who want to find a specific spot by name, the search filters the visible content on the page. This is not a full-text search engine, just a simple filter over the pre-rendered content.
- **State grid** below search. Each state card shows the state name and spot count, links to `/spots/[state-slug]` (e.g., `/spots/california`). Only states with at least one water body appear.
- **Popular spots section** below the state grid. Shows the top 10-20 spots by popularity, each linking to `/spot/[slug]` with name, type badge, and state.

### `/spots/[state]` - State Page

- **Title**: "Paddle Spots in California | Paddle Conditions"
- **Spots grouped by type** (Lakes, Rivers, Reservoirs, Bays, Coastal). Each group is a section with a heading and a list/grid of spots.
- **Each spot entry** shows: name (links to `/spot/[slug]`), type badge, county.
- **Filter controls** to show/hide types within the page (client-side toggle, no page reload).
- States are identified by a URL-safe slug (e.g., `california`, `new-york`). Map state names to slugs at build time.

### Relationship to `/explore`

The existing `/explore` page is an interactive map-based discovery tool (React component, client-rendered). It serves a different purpose than `/spots`:

- **`/spots`** is the SEO/text browse page. Static, crawlable, organized by state and type. Designed for search engine discovery and users who want to browse by location.
- **`/explore`** is the interactive map. Client-rendered, not crawlable. Designed for users who want to visually find spots near a location.

Cross-link between them: `/spots` includes a "Or explore the map" link to `/explore`. `/explore` includes a "Browse all spots" link to `/spots`.

### Data Source

New API endpoint: `GET /public/spots/directory`

Returns all water bodies grouped by state:

```json
{
  "states": [
    {
      "state": "California",
      "slug": "california",
      "count": 142,
      "spots": [
        {
          "name": "Lake Tahoe",
          "slug": "lake-tahoe",
          "type": "lake",
          "county": "El Dorado County"
        }
      ]
    }
  ],
  "totalSpots": 1247
}
```

- Rate limit: 10 req/min (build-time only, not user-facing).
- Cache-Control: `public, s-maxage=3600, max-age=3600`.
- Astro calls this at build time in `getStaticPaths()` to generate all state pages.

### Build Trigger

Rebuild the website when water bodies are added or modified. Options (in order of simplicity):
1. Manual rebuild via deploy script after importing new water bodies.
2. Webhook from the API after water body changes trigger a website rebuild.
3. Scheduled daily rebuild (cron).

Start with option 1. Upgrade later if the frequency of water body changes increases.

## 2. Dynamic Sitemap

### `GET /sitemap-spots.xml` (SSR Endpoint)

Astro SSR endpoint at `website/src/pages/sitemap-spots.xml.ts`.

Queries the API for all water body slugs and emits a sitemap XML file:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://paddleconditions.com/spot/lake-tahoe</loc>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>
  <!-- ... -->
</urlset>
```

- Includes all `/spot/[slug]` pages and all `/spots/[state]` pages.
- `changefreq`: `daily` for spot pages (conditions change), `weekly` for state pages.
- `priority`: 0.7 for spot pages, 0.6 for state pages, 0.8 for `/spots` index.
- Cache-Control: `public, s-maxage=3600, max-age=3600` (1 hour).

### Sitemap Index Update

The existing `@astrojs/sitemap` (v3.7.1) generates `sitemap-index.xml` at build time. Use the plugin's `customSitemaps` option to include the dynamic spots sitemap in that index. No custom index endpoint needed.

```js
// astro.config.mjs
sitemap({
  filter: (page) => !page.includes('/404'),
  customSitemaps: ['https://paddleconditions.com/sitemap-spots.xml'],
})
```

This produces a `sitemap-index.xml` referencing both `sitemap-0.xml` (static pages) and `sitemap-spots.xml` (dynamic spots). No changes to `robots.txt` needed since it already points to `sitemap-index.xml`.

The `sitemap-spots.xml.ts` endpoint must export `export const prerender = false` so it is server-rendered on each request rather than pre-rendered at build time.

## 3. Spot Page Enhancements

### Rich Descriptions

**Database change:** Add a `description` TEXT column to `water_bodies`.

```sql
ALTER TABLE water_bodies ADD COLUMN description TEXT DEFAULT NULL;
```

**Auto-generation:** For spots without a manual description, generate a baseline from existing fields:

> "Lake Tahoe is a lake in El Dorado County, California."

Template: `"{name} is a {type} in {county}, {state}."`

Extend for spots with station data:

> "Lake Tahoe is a lake in El Dorado County, California. Water conditions are monitored by USGS station 10336610."

The spot page displays `description` if set, otherwise the auto-generated text. Manual descriptions take priority.

**Content strategy:** Write rich descriptions for the top spots by popularity first. Include access info, best activities (SUP, kayak, canoe), best seasons, and any notable features.

### Nearby Spots

Below the map on each spot page, show 3-5 nearby spots. Uses the existing `/public/spots/nearby` endpoint with the spot's lat/lng.

Each nearby spot card shows: name, type badge, distance in miles, link to `/spot/[slug]`.

This creates internal linking between spot pages, which helps both users and crawlers.

### Popularity Tracking

The `water_bodies` table already has a `popularity` INT UNSIGNED column. This is a composite signal: it gets incremented both by page views and by users saving a water body. No new column needed.

**Increment on page view:** The spot API endpoint (`/public/spot/:slug`) increments `popularity` on each request. Use a non-blocking increment with error handling to avoid unhandled promise rejections:

```ts
app.dbPool.execute(
  'UPDATE water_bodies SET popularity = popularity + 1 WHERE slug = ?',
  [slug],
).catch(err => request.log.error(err, 'popularity increment failed'));
```

This does not block the response. Acceptable to lose some counts under load. If the volume gets high enough to matter, batch the increments later.

**Usage:** Sort the "Popular Spots" section on `/spots` by `popularity`. Prioritize writing manual descriptions for high-popularity spots.

### Structured Data (JSON-LD)

Add to the `<head>` of each spot page:

```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Lake Tahoe Paddle Conditions",
  "description": "Check current paddle conditions at Lake Tahoe...",
  "mainEntity": {
    "@type": "Place",
    "name": "Lake Tahoe",
    "description": "Lake Tahoe is a lake in El Dorado County, California.",
    "geo": {
      "@type": "GeoCoordinates",
      "latitude": 39.0968,
      "longitude": -120.0324
    },
    "additionalType": "https://schema.org/LakeBodyOfWater"
  }
}
```

- Map water body types to schema.org types: lake -> `LakeBodyOfWater`, river -> `RiverBodyOfWater`, reservoir -> `Reservoir`, bay -> `BodyOfWater`, coastal -> `BodyOfWater`.
- Include `description` if the spot has one.

## 4. OG Images

### Generation

Node.js batch script using **Satori** (JSX to SVG) + **Sharp** (SVG to PNG).

- Input: Query all water bodies from the database.
- Output: `website/public/og/[slug].png` (1200x630 px).
- Content per image: Spot name (large), type badge, state/county, Paddle Conditions branding.
- Design: Dark gradient background (matching the premium CTA style: slate-900 to sky-800), white text, score circle placeholder area for brand consistency.

### Script Location

`website/scripts/generate-og-images.ts`

Run manually: `npx tsx website/scripts/generate-og-images.ts`

The script:
1. Fetches all water bodies from the API (`/public/spots/directory`).
2. For each spot, checks if `website/public/og/[slug].png` already exists. Skips if so (unless `--force` flag).
3. Renders the template via Satori, converts to PNG via Sharp, writes to disk.
4. Reports: X generated, Y skipped, Z errors.

### Integration

The spot page's `SEOHead` component checks for the OG image:
- OG image URL: `https://paddleconditions.com/og/[slug].png`
- The page always sets this URL. If the file doesn't exist (not yet generated), the browser gets a 404 for the OG image, which is acceptable. Social platforms will fall back to page scraping.
- Alternatively, the spot API response could include an `ogImageExists` boolean, but this adds complexity for little benefit. Just generate images for all spots and keep them in sync.

### Fonts

Bundle 1-2 font files (e.g., Inter Bold, Inter Regular) in the website scripts directory for Satori to use. Satori requires explicit font buffers.

## 5. API Changes Summary

### New Endpoint

**`GET /public/spots/directory`**
- Returns all water bodies grouped by state with slug, name, type, county.
- Rate limit: 10 req/min.
- Cache: 1 hour.
- Used by: Astro build (browse pages), OG image generation script.

### Modified Endpoint

**`GET /public/spot/:slug`**
- Add: non-blocking `popularity` increment with `.catch()` error handling.
- Add: include `description` field in response.
- No breaking changes to existing response shape.

### Database Migrations

1. `ALTER TABLE water_bodies ADD COLUMN description TEXT DEFAULT NULL;`

## 6. SEO Metadata Summary

| Page | Title | Description | OG Image |
|------|-------|-------------|----------|
| `/spots` | Paddle Spots - Find Lakes, Rivers & Reservoirs \| Paddle Conditions | Find paddle spots near you. Browse by state and water body type. | Generic og-image.png |
| `/spots/california` | Paddle Spots in California \| Paddle Conditions | Browse {count} paddle spots in California. Lakes, rivers, reservoirs and more. | Generic og-image.png |
| `/spot/lake-tahoe` | Lake Tahoe Paddle Conditions \| Current Wind, Water & Weather | {dynamic with conditions} | /og/lake-tahoe.png |

## 7. File Changes Summary

### API (`api/`)
- `src/routes/public/spot.ts` - Add popularity increment, include description
- `src/routes/public/directory.ts` - New endpoint
- `src/db/migrations/XXXX_add_description.sql` - Schema change

### Website (`website/`)
- `src/pages/spots/index.astro` - New browse index page
- `src/pages/spots/[state].astro` - New state page (static)
- `src/pages/sitemap-spots.xml.ts` - Dynamic sitemap (prerender = false)
- `src/pages/spot/[slug].astro` - Add structured data, nearby spots, description section, OG image
- `src/components/SpotJsonLd.astro` - New structured data component
- `src/components/NearbySpots.astro` - New nearby spots component
- `scripts/generate-og-images.ts` - New OG image batch script
- `astro.config.mjs` - Add customSitemaps to sitemap plugin config

## 8. Out of Scope

- Search engine submission (Google Search Console) - manual step after deployment.
- Analytics integration beyond popularity increment (Google Analytics, etc.).
- Spot page comments or user-generated content.
- Canonical URL handling for potential duplicate content (not an issue with slug-based URLs).
- AMP pages.
