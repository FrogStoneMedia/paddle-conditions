# Sharing & Explore Design Spec

## Summary

Two public-facing features on paddleconditions.com:

1. **Spot pages** (`/spot/:slug`) -- Public read-only conditions view for a water body. Shared via URL by app users. Shows current conditions from cached data, with a premium CTA for charts/forecasts.
2. **Explore page** (`/explore`) -- Browse nearby paddle spots via browser geolocation. Interactive map with teardrop score markers + card grid sorted by distance.

Both features serve as discovery/marketing surfaces. They only display cached data from `water_body_conditions` -- they never trigger new data fetches. Water bodies with no premium users monitoring them show metadata only.

## Architecture

### Data Flow

```
Share link → paddleconditions.com/spot/lake-tahoe
                ↓
        Cloudflare edge cache (15 min TTL)
                ↓ (cache miss)
        Astro SSR renders page
                ↓
        API: GET /public/spot/:slug
                ↓
        Reads water_bodies + water_body_conditions
                ↓
        Returns metadata + cached conditions (or null)
```

```
/explore → browser requests geolocation
                ↓
        API: GET /public/spots/nearby?lat=X&lng=Y
                ↓
        Returns water bodies sorted by distance
                ↓
        Client renders map (Astro island) + card grid
                ↓
        Click card → /spot/:slug
```

### Key Rule

Public endpoints never trigger data fetches from external sources (NOAA, USGS, etc.). They read from the existing `water_body_conditions` cache, which stores raw JSON blobs (`weather`, `water`, `aqi`). Scores and ratings are computed at request time by running `computePaddleScore()` against the cached data -- this is fast (no I/O) but requires an activity profile. Public pages use the **SUP recreational** profile as a general-purpose default, labeled "Typical paddle score." Premium users see personalized scores based on their chosen activity and skill level.

Water bodies with `user_count = 0` have no cached data and show a "No data" state with a CTA to subscribe.

## Spot Page (`/spot/:slug`)

### URL

`paddleconditions.com/spot/{waterBodySlug}` (e.g., `/spot/lake-tahoe`)

Water body slugs are canonical -- one URL per water body regardless of which user shares it.

### Layout (Full-Width Stacked)

Content flows vertically in a centered column (max ~640px):

1. **Header row** -- Water body name + type badge (left), score circle + rating (right). Side-by-side on both desktop and mobile.
2. **Conditions grid** -- 3-column on desktop, 2-column on mobile. Metrics: wind speed, air temp, water temp, UV index, AQI, precipitation.
3. **Last updated timestamp** -- "Last updated X minutes ago" from `water_body_conditions.fetchedAt`.
4. **Premium CTA** -- Gradient banner: "Want charts, forecasts & alerts? Get real-time updates with Paddle Conditions Premium." Subscribe button links to `app.paddleconditions.com/subscribe`.
5. **Map** -- Small interactive map showing the water body's location.

### No-Data State

When a water body has no cached conditions (`water_body_conditions` row missing or `user_count = 0`):

- Show water body metadata (name, type, state/county, map)
- Replace conditions grid with: "No current conditions available. Be the first to monitor this spot!"
- Premium CTA remains

### SEO

- `<title>`: "{Name} Paddle Conditions | Current Wind, Water & Weather"
- Meta description includes current score and key metrics if available
- Open Graph tags for social sharing previews (score + conditions summary)

### 404

"Spot not found" page with link to `/explore`.

## Explore Page (`/explore`)

### URL

`paddleconditions.com/explore`

Public, no auth required.

### Flow

1. Page loads, requests browser geolocation via `navigator.geolocation.getCurrentPosition()`
2. If granted: fetch nearby water bodies from API, render map + card grid
3. If denied: show search-by-name input + browse-by-state dropdown as fallback

### Layout

**Header:** "Explore Paddle Spots" title, subtitle showing detected location ("Near Sacramento, CA"). Filter dropdowns for water body type (All, Lake, River, Reservoir, Bay, Coastal) and radius (10, 25, 50, 100 mi).

**Map:** Interactive map centered on user's location with teardrop markers for each water body. Markers are colored by rating (blue = GO, yellow = CAUTION, red = NO_GO, grey = no data) with the score number inside. Clicking a marker highlights the corresponding card below.

**Card grid:** Below the map. 3-column on desktop, single-column list on mobile.

Each card shows:
- Water body name, type badge, distance
- Score circle + rating if conditions are cached
- Grey "No data / Not yet monitored" state if not
- Click navigates to `/spot/:slug`

Mobile cards are compact rows: name + type/distance on the left, score on the right.

### Empty State

"No paddle spots found nearby. Try expanding your search radius."

### Map Pin Style

Teardrop markers (classic map pin shape) with score inside, colored by rating:
- GO: `#0ea5e9` (blue) with drop shadow
- CAUTION: `#eab308` (yellow)
- NO_GO: `#ef4444` (red)
- No data: `#cbd5e1` (grey)

## Share Button in the App

### Location

Detail page header (`/location/:idOrSlug`), next to the existing settings gear icon.

### Behavior

- **Mobile:** `navigator.share({ title, text, url })` for native share sheet
- **Desktop:** Copy URL to clipboard with confirmation toast
- **URL format:** `paddleconditions.com/spot/{waterBodySlug}` -- derived from the location's linked water body

### Visibility

- Shown only when the location has a linked water body (`waterBodyId` is not null)
- Hidden when no water body is linked (share URL can't be generated without a slug)

## API Endpoints

Two new public endpoints under `/public/` prefix. No auth required, rate-limited.

### `GET /public/spot/:slug`

Fetch a water body and its cached conditions by slug. Reads raw cached JSON from `water_body_conditions` (weather, water, aqi columns), then computes score/rating at request time using the SUP recreational profile via `computePaddleScore()`.

**Response:**
```json
{
  "waterBody": {
    "id": "uuid",
    "name": "Lake Tahoe",
    "type": "lake",
    "state": "CA",
    "county": "El Dorado",
    "lat": 39.0968,
    "lng": -120.0324,
    "slug": "lake-tahoe"
  },
  "conditions": {
    "score": 78,
    "rating": "GO",
    "current": {
      "windSpeed": 5,
      "windDirection": "SW",
      "airTemp": 68,
      "waterTemp": 52,
      "uvIndex": 6,
      "aqi": 32,
      "precipProbability": 0,
      "conditionText": "Sunny"
    },
    "fetchedAt": "2026-04-08T15:30:00Z"
  }
}
```

`conditions` is `null` if no cached data exists.

**Errors:** 404 if slug not found.

**Rate limit:** 30 requests/minute per IP.

### `GET /public/spots/nearby`

Find water bodies near a geographic point. For spots with cached conditions, computes score/rating using the SUP recreational profile.

**Query params:**
- `lat` (required) -- latitude
- `lng` (required) -- longitude
- `radius` (optional, default 50, max 100) -- search radius in miles
- `type` (optional) -- filter by water body type
- `limit` (optional, default 20, max 50) -- max results

**Response:**
```json
{
  "spots": [
    {
      "waterBody": { "id", "name", "type", "state", "lat", "lng", "slug" },
      "distance": 2.4,
      "conditions": { "score", "rating", "current": { "windSpeed", "airTemp", "waterTemp" }, "fetchedAt" } | null
    }
  ]
}
```

Sorted by distance ascending. Uses Haversine formula in SQL.

**Rate limit:** 30 requests/minute per IP.

## Database Changes

### Water bodies table: add `slug` column

```sql
ALTER TABLE water_bodies ADD COLUMN slug VARCHAR(255) UNIQUE;
```

- Slugs are derived from the water body name: lowercase, spaces to hyphens, strip special characters, dedup collisions with numeric suffix
- Backfill migration generates slugs for all existing rows
- New water bodies get slugs on insert
- Unique constraint prevents collisions

No new tables. Both endpoints read from existing `water_bodies` and `water_body_conditions`.

## Website Infrastructure

### Astro SSR

The website currently uses a static adapter. This feature requires switching to hybrid rendering:

- `/spot/[slug].astro` -- server-rendered (SSR), fetches from API at request time
- `/explore.astro` -- static shell with client-side Astro island for map + cards
- All other pages remain prerendered (static)

Uses the Node adapter since the website is hosted on cPanel with a self-hosted deploy runner.

### Map Library

Leaflet (lightweight, free, no API key needed) loaded as an Astro client island via `client:only="react"` or `client:load`. Zero JS impact on pages that don't use the map.

Tile provider: OpenStreetMap (free) or Stadia Maps (better looking, free tier).

### Edge Caching

- Spot pages: `Cache-Control: public, s-maxage=900` (15 min at Cloudflare edge)
- Nearby API responses: `Cache-Control: public, s-maxage=300` (5 min)

This aligns with the refresh tier schedule -- data changes at most every 6 hours for active spots, so 15-minute edge caching is well within freshness.

## Navigation

Add "Explore" link to the website navigation bar, linking to `/explore`. This appears alongside Features, Docs, and the Get Premium CTA.

## Infrastructure Prerequisites

### Passenger Setup for Website

The website is currently pure static files served by Apache. SSR requires a persistent Node process via Passenger:

1. **cPanel:** Create a Node.js application for `paddleconditions.com` (same pattern as the API)
2. **package.json:** Add `"start": "node ./dist/server/entry.mjs"` script
3. **Deploy workflow:** Add Passenger restart step (`touch tmp/restart.txt`) after rsync
4. **Astro config:** Switch from `output: 'static'` to hybrid mode with `@astrojs/node` adapter

Passenger is already proven on this cPanel account (used by the API). The setup is straightforward.

## Known Limitations

### California-Only Water Body Data

The `water_bodies` table contains ~4,100 entries imported from the NHD California dataset. The explore page will show no results for users outside California. This is acceptable for initial launch since the user base is CA-focused, but national expansion requires running the NHD import for additional states. The import script (`_todo/20260318-water-body-database.md`) documents the process.

### No Spatial Index

The water_bodies table has no spatial index on lat/lng. At ~4K rows, Haversine queries via full table scan are fast enough. If the dataset grows past 50K rows (national expansion), add a spatial index or use bounding-box pre-filtering.

## Testing

- **API:** Unit tests for public endpoints (slug lookup, nearby query, haversine math, rate limiting, null conditions handling)
- **Website:** Manual testing of SSR rendering, edge caching headers, map interaction, geolocation fallback
- **App:** Test share button visibility (with/without water body), share action (clipboard/native share), URL generation
- **E2e:** Add a test for the share flow if feasible (navigate to detail page, click share, verify URL format)
