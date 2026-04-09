# Web App — Remaining Work & Next Features

## Spec
`docs/superpowers/specs/2026-03-17-premium-web-app-design.md`

## Plans
- `docs/superpowers/plans/2026-03-17-conditions-api.md` (DONE)
- `docs/superpowers/plans/2026-03-17-premium-web-app-frontend.md` (DONE)

## Phases

- [x] Conditions API (8 tasks, 334 tests)
- [x] React SPA frontend (10 tasks, deployed)
- [x] Polish pass (code-split, favicon, 404, tap targets, theme sync, spot management)
- [x] Water body conditions cache (10 tasks, 379 tests, deployed)
- [x] Dashboard & Add Location redesign (12 tasks, deployed — plan moved to `_done/2026-03-20-dashboard-addlocation-redesign.md`)
- [x] Code quality follow-ups from caching work (all 9 items resolved)
- [x] Offline data caching (localStorage persistence, offline banner, optimistic mutations, deployed)
- [x] Linked accounts (12 tasks, 513 tests, social login + account linking + password management)
- [x] End-to-end testing (17 Playwright tests, 4 suites)
- [x] Location-based sharing & nearby spots (12 tasks, 533 API tests, deployed — spec at `docs/superpowers/specs/2026-04-08-sharing-and-explore-design.md`, plan at `docs/superpowers/plans/2026-04-08-sharing-and-explore.md`)
- [x] SEO & discovery (15 tasks, deployed — spec at `docs/superpowers/specs/2026-04-08-seo-discovery-design.md`, plan at `docs/superpowers/plans/2026-04-08-seo-discovery.md`)

## Remaining Tasks

### Needs API work first
- [x] Linked accounts (Google/Apple): `GET /auth/me`, `POST /auth/link/{google,apple}`, `DELETE /auth/unlink/{google,apple}`, `POST /auth/set-password`, `POST /auth/change-password` endpoints + frontend UI (social login on Login/Register, linked accounts on AccountPage, avatar in header)
- [x] Location-based sharing: Public spot pages (`/spot/:slug`), explore nearby page (`/explore`), share button in app, 2 public API endpoints, website SSR via Passenger

### Code quality follow-ups (from caching implementation reviews)
- [x] Validate waterBodyIds before insert to prevent FK violations (was critical bug — fixed with batch validation)
- [x] COALESCE(fetched_at, NOW()) for NULL arithmetic (already in code)
- [x] Water body unlinking uses `!== undefined` not `??` (already correct)
- [x] Extract shared scoring logic from `computeFromRawData` and `computeConditions` into `buildConditionsResponse` (~40 lines duplicated)
- [x] Batch cache reads in `getConditionsBulk` by waterBodyId (was N+1, now single bulk query via `getCachedBulk`)
- [x] Add test for stale-cache-serve-and-refresh path (async refresh fires when cache data is stale)
- [x] Add "Can't find your spot?" CTA in AddLocationPage for when both catalog and geocoding return empty
- [x] Add exit animation to RefreshBar (fade-out + slide with 300ms transition)
- [x] Deduplicate water bodies: SQL migration script at `api/scripts/dedup-water-bodies.sql` (needs manual run on prod)

### Frontend-only
- [x] End-to-end testing — spec at `docs/superpowers/specs/2026-03-21-e2e-testing-design.md`, plan at `docs/superpowers/plans/2026-04-07-e2e-testing.md` (Playwright, 17 tests, 4 suites, deployed)

### Future (v1.1+)
- [ ] Multi-point compare view (overlay charts, side-by-side metrics)
- [x] ~~Location-based sharing: "Share conditions" button, shareable public link~~ (done — public spot pages + share button)
- [x] ~~Nearby paddle spots: browser geolocation + geocoding suggestions~~ (done — explore page with Leaflet map)
- [ ] Push notifications for condition changes
- [x] ~~Offline support / service worker caching~~ (done via localStorage persistence, not service worker)

## Lore

- **Turnstile required on app login/register**: The API enforces Turnstile when enabled. App uses sitekey `0x4AAAAAACsMxuk7cAUe95vr`.
- **Sync locations body shape**: API expects `{ locations: [...] }` array wrapper, max 100 items. IDs are client-generated UUID v7. `updatedAt` required as ISO datetime.
- **GET /auth/me returns user profile**: email, emailVerified, hasPassword, providers (google/apple booleans), displayName, avatarUrl, createdAt. Used by `useProfile()` hook. Not persisted to offline cache.
- **Subscription plan details not in API**: `/subscription/status` returns status/source/periodEnd/cancelAtPeriodEnd but not plan tier or payment method. Users manage these through Stripe portal.
- **Code-split charts**: Recharts lazy-loaded via `React.lazy()`. Main bundle 321KB, chart chunk 337KB. Only loads on location detail.
- **Theme sync**: localStorage for fast initial load (no flash), API sync in background. On mount, fetches server preference and overrides if different.
- **Cloudflare DNS**: `app.paddleconditions.com` A record pointing to `104.255.174.113`, proxied. Created via Cloudflare API using credentials in `.env.secrets`.
- **cPanel subdomain**: Created via `uapi SubDomain addsubdomain domain=app rootdomain=paddleconditions.com`. Use short name (not FQDN) to avoid double-suffix bug.
- **Open-Meteo lake temp bug**: Grid-cell models return wildly wrong temps for coordinates over large water bodies. Lake Tahoe shows 19F when actual is 52F. Sharp 33F discontinuity at lat 38.96-38.98. Affects all cells over the lake. Not fixable with cell_selection parameter.
- **NWS API quirks**: Data comes as ISO 8601 duration periods (`validTime: "2026-03-20T11:00:00+00:00/PT3H"`) that need expansion into hourly slots. Must call `/points/{lat},{lng}` first to get grid coordinates (cacheable forever), then `/gridpoints/{wfo}/{x},{y}`. Requires User-Agent header. No UV index or reliable visibility data.
- **drizzle-kit push breaks on MariaDB**: `drizzle-kit push` crashes with `checkConstraint TypeError` when pulling existing schema. Use manual SQL migrations instead.
- **NWS only has future hours**: NWS hourly forecast starts from current time. For full-day charts, merge with Open-Meteo: OM provides full 24h base, NWS overlays wind/temp/precip for future hours. Current conditions still use NWS (more accurate over water). UV/visibility/conditionText/thunderstorm come from Open-Meteo.
- **NWS timezone conversion**: NWS returns UTC times. Must convert to local using `Intl.DateTimeFormat` with timezone from `/points/` endpoint (`en-CA` locale, `hour12: false`). Without this, chart X-axis shows UTC hours.
- **MariaDB JSON columns are strings**: mysql2/drizzle returns JSON as strings. Must JSON.parse() via `parseConfig()` helper. Without this, config.dataSources is silently undefined.
- **Changelog lives on website repo**: `website/data/changelog.json` covers ALL repos (api, app, website, HA). Must update with every change. CLAUDE.md enforces this on /handoff too.
- **Chart X-axis ticks**: Use `getEvenTicks()` helper with Recharts `ticks` prop for even 2-hour spacing. All data points kept for tooltip interaction.
- **SSH PQ warnings are noise**: OpenSSH 9.x warns "not using post-quantum key exchange" when connecting to cPanel server. Safe to ignore — server just needs upgrading (hosting provider's responsibility). Auth failures (`Exit code 5/255`) are separate issues (key/password problems), investigate only if deploys fail.
- **Google Search Console**: Verified via Cloudflare DNS TXT record on paddleconditions.com. Sitemap at `/sitemap-index.xml` (includes `sitemap-spots.xml` via `customSitemaps`). Sitemap submitted 2026-04-08. App subdomain not worth indexing (gated SPA).
- **OG images are pre-generated, not in git**: Run `npx tsx scripts/generate-og-images.ts` from `website/`. Output goes to `website/public/og/` (gitignored). Must rsync to server separately after deploy: `rsync -avz -e "ssh -i ~/.ssh/paddleconditions_prod -p 11208" website/public/og/ devsac@104.255.174.113:/home/devsac/public_html/paddleconditions.com/client/og/`
- **Google Fonts URL returns HTML, not font**: `fonts.gstatic.com` URLs redirect to HTML. Download Inter from GitHub releases instead: `https://github.com/rsms/inter/releases/`. Use TTF format for Satori (not woff/woff2).
- **`popularity` is composite**: The `water_bodies.popularity` column is incremented by spot page views AND user saves. No separate `view_count` needed. Sort browse pages by this field.
- **Astro hybrid mode**: `output: 'static'` in Astro 6 is actually hybrid. Pages default to prerender. Use `export const prerender = false` to opt into SSR. Spot pages and sitemap use SSR; browse pages are static via `getStaticPaths`.
- **@astrojs/sitemap customSitemaps**: Version 3.7.1 supports `customSitemaps: string[]` to include external sitemaps in the generated index. No need for custom index endpoints.
- **water_body_conditions has 4 JSON columns**: weather, water, aqi, forecast. Each stored separately for clean data boundaries. AQI was initially packed into weather as an envelope `{weatherData, aqi}` — refactored to its own column.
- **Refresh tiers are user-count based**: 0 users = dormant, 1-2 = 24h, 3-5 = 12h, 6+ = 6h. `user_count` is DISTINCT users, not location rows. Nightly reconciliation corrects drift.
- **cron_locks table for multi-process safety**: Passenger spawns multiple workers. Only one runs the refresh job. Lock uses 10-min self-healing expiry via UPDATE with timestamp check.
- **Production DB access**: SSH tunnel via `ssh -i ~/.ssh/paddleconditions_prod -p 11208 -L 13306:localhost:3306 devsac@104.255.174.113`. DB creds in `.env.secrets`. Migrations NOT auto-applied by deploy pipeline — must run manually via tunnel or SSH.
- **Drizzle migration tracking**: Production had migration 0000-0003 applied manually but not tracked in `__drizzle_migrations`. Had to backfill tracking rows before `db:migrate` would work. All 7 migrations (0000-0006) now tracked.
- **Water body dedup completed**: Lake Natoma and Lake Tahoe duplicates (manual seed vs NHD import) resolved 2026-03-21. Locations repointed to manual entries, NHD rows deleted. Script at `api/scripts/dedup-water-bodies.sql` for reference.
- **`int().unsigned()` not a method chain in this Drizzle version**: Use `int('col', { unsigned: true })` config syntax instead.
- **NULL fetched_at gotcha**: `reconcileWaterBodyUserCount` uses `COALESCE(fetched_at, NOW())` in the CASE expression. Without this, `NULL + INTERVAL` = `NULL`, breaking fetch scheduling for newly-created rows.
- **App .gitignore was missing**: Created one to exclude node_modules/, dist/, .DS_Store. A subagent accidentally committed 8000+ files before this was caught.
- **waterBodyId FK validation**: `locations.water_body_id` has FK to `water_bodies(id)` with `onDelete: 'set null'`. Client-sent waterBodyIds must be validated before INSERT or the whole push crashes. Batch-check with `inArray` query, nullify invalid ones.
- **Stripe webhook signature verification**: `/stripe/webhook` calls `stripe.webhooks.constructEvent()` which requires valid signature. Can't just POST test events. Need either a test seed endpoint (`POST /test/seed-subscription` behind `NODE_ENV=test`) or `stripe.webhooks.generateTestHeaderString()`.
- **API_BASE centralized (2026-03-21)**: All hardcoded `API_BASE`, `TURNSTILE_SITE_KEY`, and `GEOCODING_URL` consolidated into `app/src/lib/api.ts` as environment-configurable exports (`import.meta.env.VITE_*` with production fallbacks). 8 files updated, `vite-env.d.ts` added for types. For e2e tests, create `app/.env.test` with overrides and run Vite with `--mode test`.
- **Vite .env.test loading**: Must pass `--mode test` to load `.env.test`. Playwright's `webServer.env` doesn't auto-load dotenv files.
- **NWS hourly index bug**: `parseNwsGridpoints()` built hourly arrays starting from 24h ago but took `[0]` for "current" conditions. Fix: find the entry closest to `now` via min `|time - nowMs|`. Affected all current condition values (temp, wind, feels-like, etc.).
- **iOS Safari auto-zoom**: Safari zooms in on any input with `font-size < 16px`. Fix with `text-base` (16px) on all form inputs AND `maximum-scale=1` on the viewport meta tag. The font fix prevents trigger, the viewport fix prevents cached zoom state.
- **Forecast blocks were mistaken for temperatures**: Users confused the 0-100 paddle scores in the forecast blocks with actual temperatures. Removed them from the dashboard entirely. Paddle scores now only appear as a chart on the detail page where they're clearly labeled.
- **`invalidateQueries` vs `refetchQueries`**: `invalidateQueries()` marks queries stale but doesn't force immediate refetch (lazy on next render). `refetchQueries()` triggers an immediate fetch. Use `refetchQueries` for user-initiated refresh buttons.
- **Score colors shifted to blue for water theme**: GO scores now use `--color-water` (#0ea5e9) instead of `--color-go` (#4CAF50) on the dashboard. The green is still used in the ScoreCircle on the detail page and in the spot selector dots. `scoreTextColor()` and `accentColor()` utilities handle this.
- **API deploy is GitHub Actions on self-hosted runner**: Triggers on push to main. Uses rsync over SSH. Restarts Passenger via `touch tmp/restart.txt`. Key at `~/.ssh/cpanel_deploy_bttp`. If deploy fails with simdjson error, run `brew upgrade simdjson` on the runner machine.
- **Force-refreshing production cache**: To invalidate all cached conditions after a data-affecting code fix, SSH in and run: `mysql -u devsac_paddle -p'...' devsac_paddle -e "UPDATE water_body_conditions SET next_fetch_at = NOW() - INTERVAL 1 HOUR WHERE user_count > 0;"`
- **Offline caching uses localStorage, not IndexedDB**: React Query cache persisted under `PADDLE_CONDITIONS_CACHE` key. ~120KB for 20 locations. Only conditions, forecast, and locations queries are persisted (subscription/preferences excluded via `shouldDehydrateQuery` filter in `app/src/lib/persist.ts`).
- **Offline mutations don't auto-queue**: With `networkMode: 'offlineFirst'`, mutations fire once and throw if offline. The catch blocks show error toasts. Optimistic updates flash briefly then rollback on failure. True offline mutation queuing would need `@tanstack/query-persist-client` mutation persistence. The `onSettled` callbacks guard against refetching while offline with `navigator.onLine` check.
- **OfflineBanner uses query fetch timestamp**: `queryClient.getQueryState(queryKeys.bulk())?.dataUpdatedAt` gives when the client last fetched, not when the server last computed. This is the right signal for "how old is the data on this device."
- **Google OAuth uses paddleconditions.com as homepage**: Google requires a public, non-login homepage for OAuth verification. The app (app.paddleconditions.com) is behind a login page, so the consent screen points to paddleconditions.com instead. Privacy and terms pages live only on the website. App links out to them.
- **Apple Hide My Email creates relay addresses**: Apple's email proxy (`abc123@privaterelay.appleid.com`) won't match existing account emails, so auto-linking fails on first sign-in. Subsequent sign-ins match on Apple `sub` ID. Hint text on login page tells existing users to sign in with email first, then link Apple from Account settings.
- **OAuth client IDs via GitHub Actions secrets**: `VITE_GOOGLE_CLIENT_ID` and `VITE_APPLE_CLIENT_ID` are GitHub repo secrets passed to Vite build in `app/.github/workflows/deploy.yml`. Local dev uses `app/.env`.
- **Google OAuth client**: ID `443744018085-5nvn0s49hephlt1qlqp9oggka8j9e9u8.apps.googleusercontent.com`, authorized origin `https://app.paddleconditions.com`. Verification submitted.
- **Apple OAuth client**: Services ID `com.paddleconditions.web`, App ID `com.paddleconditions.api`, Team ID `XX6LPA6VS9`. Domain `app.paddleconditions.com`, return URL `https://app.paddleconditions.com/auth/callback`.
- **DST gap in MariaDB timestamps**: Tests creating past dates can land in DST spring-forward gaps (e.g., 2 AM on March 8, 2026 doesn't exist in Pacific time). Fix: use noon UTC for test dates. See `dateAgo()`/`dateAhead()` helpers in jobs tests.
- **change-password returns fresh tokens**: `/auth/change-password` revokes all sessions then creates a new token pair. Frontend calls `login()` with the fresh tokens to stay authenticated.
- **Form labels lack htmlFor**: Login, Register, ForgotPassword forms use `<label>` without `htmlFor`/`id` association. Playwright's `getByLabel()` doesn't work. Use `locator('input[type="email"]')` and `locator('input[type="password"]')` instead.
- **Rate limit keyGenerator body parsing race**: `@fastify/rate-limit` runs `keyGenerator` before Fastify parses the request body. So `req.body?.email` is always `undefined`, falling back to IP. All registrations from the same IP share one rate limit bucket. Rate limiting is disabled in test mode (`NODE_ENV=test`).
- **Stripe fake keys break account deletion**: The delete account endpoint calls `stripe.subscriptions.cancel()` for Stripe subscriptions. With `STRIPE_SECRET_KEY=sk_test_fake`, this fails. E2e tests intercept the DELETE /auth/account call at the browser level and call the cleanup endpoint instead.
- **E2e test subscription redirect race**: `useSubscription()` fires before `AuthProvider` completes token refresh. The 401 from `/subscription/status` triggers `window.location.href = '/'` in `apiFetch`. Fix: `Promise.all([waitForResponse('/auth/refresh'), page.goto('/dashboard')])`.
- **Website Passenger setup**: Registered via `uapi PassengerApps register_application`, then `enable_application`. SSL config must be manually copied from `std/` to `ssl/` in `/etc/apache2/conf.d/userdata/` and Apache rebuilt via `/scripts/rebuildhttpdconf && /scripts/restartsrv_httpd` (requires WHM root terminal).
- **Astro Node adapter needs runtime deps on server**: The standalone build imports `piccolore` (terminal colors) at runtime. Deploy must rsync `node_modules` (production only) alongside `dist/`. Use `npm ci --omit=dev` to strip devDeps first.
- **Passenger entry point is `app.js`**: cPanel Passenger looks for `app.js` in the app root. For the website: `import "./server/entry.mjs";`. Must be created in `dist/` before rsync so `--delete` doesn't remove it.
- **Drizzle migration journal**: New migrations must be added to `api/src/db/migrations/meta/_journal.json` or `db:migrate` won't pick them up. CI drops all tables and re-migrates from scratch, so missing journal entries break CI.
- **Astro SSR `Astro.url` is localhost in Passenger**: `Astro.url` reflects the internal server URL (`http://localhost:PORT`), not the public URL. Use `Astro.site` (configured in `astro.config.mjs`) for canonical/OG URLs. The `astro-seo` package needs explicit `url` in `openGraph.basic` to avoid this.
- **Public scores are profile-dependent**: `computePaddleScore()` requires a `ProfileConfig`. Public endpoints use `getProfile('sup', 'recreational')` as default. Same conditions give very different scores for different activities (e.g., 12 mph wind: CAUTION for SUP family, fine for kayaking river).

## Session Notes — 2026-04-09

### Completed
- **SEO & Discovery** (full design + review + implementation + deploy):
  - Spec: `docs/superpowers/specs/2026-04-08-seo-discovery-design.md`
  - Plan: `docs/superpowers/plans/2026-04-08-seo-discovery.md`
  - API: `GET /public/spots/directory` endpoint (all water bodies grouped by state), `us-states.ts` mapping utility, `description` TEXT column migration, popularity increment on spot views. 540 total tests.
  - Website: `/spots` browse index (state grid, popular spots, search filter), `/spots/[state]` static pages (type grouping, filter buttons), `/sitemap-spots.xml` SSR endpoint (4108 URLs), `SpotJsonLd` structured data, `NearbySpots` component, enhanced spot page (JSON-LD, description, nearby spots, OG image), cross-link between `/explore` and `/spots`, OG image batch script (Satori + Sharp, 4106 images generated).
  - Deploy: Both API and website deployed. OG images rsynced to production. Sitemap submitted to Google Search Console.
- **Review findings fixed**: non-mutating sort for topSpots, aria-label on search input

### Known Limitations
- **California-only water body data**: ~4100 water bodies from NHD CA import. Browse/explore pages empty outside CA.
- **No spatial index**: Haversine queries do full table scan. Fine at 4K rows, needs index at 50K+.
- **Browse state pages require API at build time**: `getStaticPaths` fetches from directory endpoint. If API is down during build, state pages won't generate.
- **OG images must be deployed separately**: Not in git. Must run generation script + rsync after adding new water bodies.
- **No `<lastmod>` in sitemap**: Google prefers lastmod over changefreq/priority. Could add water body updatedAt in future.

### Next Steps
- Write rich descriptions for top-popularity spots (manual content for best SEO value)
- Expand water body database to more states (NHD import script needs parameterization)
- Dashboard screenshots in docs are stale (still show old design)
- Consider CI integration for e2e tests (currently local only)
- Fix form label accessibility (`htmlFor`/`id` on Login, Register, ForgotPassword forms)
- Add slug validation schema to spot API endpoint (Fastify JSON Schema)
