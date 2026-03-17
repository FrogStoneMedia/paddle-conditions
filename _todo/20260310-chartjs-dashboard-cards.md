# TPP: Chart.js Dashboard Cards (v2)

## Summary

Add two Chart.js-based Lovelace cards to the PaddleConditions HA integration: a multi-metric forecast chart (`paddle-chart-card`) and a score history chart with stats (`paddle-history-card`). Extends the v1 bundled dashboard cards with visual data exploration.

## Current phase

- [x] Research & Planning
- [x] Design alternatives
- [x] Task breakdown
- [ ] Write breaking tests
- [ ] Implementation
- [ ] Review & Refinement
- [ ] Final Integration
- [ ] Review

## Required reading

- `CLAUDE.md` — project conventions, git prefixes, design principles
- `docs/superpowers/specs/2026-03-10-chartjs-dashboard-cards-design.md` — design spec (NOTE: contains incorrect bundle size and adapter assumptions — this TPP supersedes it)
- `docs/superpowers/plans/2026-03-10-chartjs-dashboard-cards.md` — implementation plan with code (NOTE: adapter code must be replaced with custom adapter per this TPP)
- `ha-integration/frontend/src/cards/paddle-forecast-card.js` — card pattern reference (closest to chart cards)
- `ha-integration/frontend/src/editors/paddle-forecast-editor.js` — editor pattern reference
- `ha-integration/frontend/src/utils.js` — shared utilities (colorForScore, formatScore, FACTOR_META)
- `ha-integration/frontend/src/styles/theme.js` — shared CSS (CARD_STYLES)
- `ha-integration/frontend/build.js` — esbuild config (currently ESM — keep ESM)
- `ha-integration/frontend/package.json` — dependencies (currently only esbuild)

## Description

The v1 bundled dashboard cards (score, factors, chips, forecast table, fitness placeholder) ship pure-JS cards with zero dependencies (~31KB bundle). This v2 TPP adds Chart.js-based visualization cards. Chart.js is tree-shaken (only Line chart components) and bundled directly into the single ESM bundle. A custom minimal date adapter (~50 lines) uses native `Date` and `Intl.DateTimeFormat` APIs, avoiding any external date library dependency.

**Architecture:** Vanilla JS web components (no Lit), Shadow DOM, single esbuild ESM bundle, Chart.js 4.x tree-shaken, custom date adapter (no Luxon/date-fns). Chart.register() deferred until first chart card renders.

## Lore

### Build Format: Keep ESM (corrected 2026-03-10)

- **The v1 bundle is already ESM format and works correctly.** HA's frontend loads extra modules via `import()`, which supports ES modules. The original TPP claimed HA uses classic `<script>` tags — this is incorrect.
- **Do NOT change `build.js` format from `"esm"` to `"iife"`.** The ESM format is working, preferred by esbuild for optimal tree-shaking, and changing it introduces unnecessary risk to working infrastructure.
- **Code splitting is still not viable** — not because of script tag type, but because HA registers a single URL per integration via `add_extra_js_url`. Multiple chunks would need multiple registrations.
- **Dynamic `import()` DOES work** since HA loads as a module, but isn't needed for this design (single bundle approach).

### Date Adapter: Custom Minimal Adapter (corrected 2026-03-10)

- **`chartjs-adapter-luxon` does NOT work as claimed.** The original TPP said "Luxon is already available in HA's frontend runtime." This is FALSE for custom cards. HA bundles Luxon internally into its own webpack output but does NOT expose it globally (`window.luxon` doesn't exist). There is no `externals` configuration exposing bundled libraries to custom cards.
- **If `chartjs-adapter-luxon` is installed, esbuild will bundle ALL of Luxon (~70KB minified)** into the output, completely negating the claimed size advantage over `date-fns`.
- **If Luxon is marked as `external` in esbuild, the IIFE/ESM output will fail at runtime** — the adapter's `import { DateTime } from 'luxon'` won't resolve.
- **`chartjs-adapter-date-fns` has the same problem** — date-fns is also not available globally in HA. Both adapters add ~70KB.
- **Solution: Write a custom minimal date adapter** (~50 lines) using native `Date` and `Intl.DateTimeFormat`. Chart.js supports `_adapters._date.override()` for this. For the simple formats needed (hour labels "3 PM", day labels "Mar 10"), native APIs are sufficient. This adds ~1KB instead of ~70KB.

### Chart.js Bundle Size (corrected 2026-03-10)

- **Tree-shaken Chart.js is ~150-170KB minified, NOT ~40KB.** The original TPP drastically underestimated this.
- Chart.js has substantial core code that can't be tree-shaken even with minimal imports: canvas layer, animations, layouts, scales infrastructure, data parsing, plugin system, event handling, tooltip positioning.
- Tree-shaken imports (LineController, LineElement, PointElement, LinearScale, TimeScale, Filler, Legend, Tooltip) eliminate unused chart types (bar, pie, radar, etc.) but the shared core is ~80-100KB alone.
- **Gzipped transfer size: ~55-65KB** — HA serves gzipped content, so actual network cost is manageable.
- **Expected total bundle: ~185-205KB minified (~65-75KB gzipped).** This is the v1 31KB + Chart.js ~155KB + custom adapter ~1KB + card code ~15KB.

### Chart.js Tree Shaking (verified)

- Import only needed components: `LineController`, `LineElement`, `PointElement`, `LinearScale`, `TimeScale`, `Filler`, `Legend`, `Tooltip`.
- Do NOT import the full `chart.js/auto` — that defeats tree shaking.
- `TimeScale` IS part of the main `chart.js` package — no separate import needed.
- esbuild tree-shaking works correctly with ESM format for Chart.js 4.x.

### Chart.js "Deferred Init" — What It Actually Means

- The term "deferred initialization" in the original plan was misleading. Chart.js code is bundled directly — it loads into memory when the script runs regardless.
- What IS deferred: `Chart.register(LineController, ...)` in `ensureChartReady()` runs on first chart card render, not on page load. This saves a small amount of registration overhead.
- The real performance benefit is that users who don't add chart cards to their dashboard never trigger Chart.js registration or canvas rendering, even though the library code is in memory.

### History Card WebSocket API (verified)

- `hass.callWS({ type: "recorder/statistics_during_period", statistic_ids: [...], period: "hour"|"day", start_time, end_time })` fetches historical statistics from HA's recorder.
- Response: `{ "entity_id": [{ start, mean, state, ... }] }` — use `mean` for hourly/daily averages, fall back to `state`.
- **Score sensors have `state_class=SensorStateClass.MEASUREMENT`** (confirmed in sensor.py), so HA's recorder will track long-term statistics for them. This is required for the WebSocket API to return data.
- Cache results in a component-level Map keyed by `entity+range`. Invalidate when entity's `last_updated` changes or after 15 minutes.

### Async Render Race Condition (verified, with fix)

- The history card's `_render()` is async (awaits WebSocket fetch). If `hass` is set rapidly, multiple renders can race.
- **Solution:** Increment a `_renderGen` counter at the start of each render. After the `await`, check if the generation is still current. If not, bail — a newer render has taken over.
- **Additional fix needed:** The async `_render()` is called from the synchronous `set hass()` setter without `await`. Unhandled rejections would be silently lost. Wrap the async body in try/catch with `console.warn` for error visibility.

### Chart.js API Notes (verified)

- `maxTicksAuto` is NOT a valid Chart.js 4.x option. Use `maxTicksLimit` instead.
- Canvas gradients (`createLinearGradient`) require `chartArea` to exist. Return a fallback color if `chartArea` is null (happens on first render pass).
- Color zone backgrounds (green/amber/red bands) require a custom Chart.js plugin with `beforeDraw` hook that fills rectangles using `scales.y.getPixelForValue()`.
- `getComputedStyle(element)` reads HA theme CSS variables. Call on the card's host element. The element IS in the DOM when `set hass()` is called (HA only sets hass on mounted elements), so computed styles are available.

### Existing Card Patterns (from v1)

- Constructor: `attachShadow({ mode: "open" })`, init `_config = {}`
- `setConfig(config)`: validate required fields, merge defaults
- `set hass(hass)`: memoize state string, skip re-render if unchanged
- `_render()`: clear shadow root, create `<style>` + `<ha-card>`, handle empty states, build DOM imperatively
- `static getStubConfig()`: return default config skeleton
- `static getConfigElement()`: return editor element
- `disconnectedCallback()`: cleanup (Chart.js `destroy()` for chart cards)
- All text set via `.textContent` (XSS-safe)

### Sensor Data Contract (relevant to these cards)

- **Forecast sensor** (`sensor.paddle_conditions_{loc}_forecast_3hr`): attrs `blocks[]` with `{start, end, score, rating, wind_mph, temp_f, uv}`, `best_block`, `best_score`
- **Score sensor** (`sensor.paddle_conditions_{loc}_score`): state = 0-100 int, `state_class=MEASUREMENT`, used by history card

### Code Quality Notes

- **`ratingForScore` in chart-utils.js** replicates threshold logic from `utils.js:colorForScore`. Consider importing SCORE_GO/SCORE_CAUTION from a shared constant, or reusing `colorForScore` logic. Acceptable duplication for now since chart-utils has a different return type (rating string vs color).
- **`computeStats` timezone** — uses `new Date(timestamp).getDay()` which applies local timezone to UTC ISO strings from HA. "Best Day" could shift by a day for users far from UTC. Acceptable for dashboard display.
- **ha-card padding** — ensure chart cards apply consistent padding matching v1 cards (card body has `padding: 16px` in CARD_STYLES).

## Solutions

### Option A (chosen): Single ESM bundle with tree-shaken Chart.js + custom date adapter

Bundle Chart.js directly into `paddle-cards.js`. Tree-shake to ~155KB. Custom date adapter avoids any date library dependency (~1KB vs ~70KB). Total bundle ~185-205KB minified (~65-75KB gzipped). Chart.register() deferred until first chart card renders.

**Pros:** Single file, single registration, no external date library, no code splitting complexity.
**Cons:** Bundle size increase from 31KB to ~195KB. All users load Chart.js code even if they don't use chart cards. Gzipped transfer is ~65-75KB which is acceptable for a dashboard.

### Option B (rejected): chartjs-adapter-luxon "zero-cost" adapter

**Rejected:** Based on false premise that Luxon is available to custom cards. Would actually bundle ~70KB of Luxon for zero benefit over date-fns.

### Option C (rejected): Two separate bundles

Separate `paddle-cards.js` (v1) and `paddle-charts.js` (v2). Users who don't use charts never load Chart.js.

**Rejected:** User preferred single bundle. Would require second `add_extra_js_url()` registration and more complex Python setup.

### Option D (rejected): Lazy-load via dynamic import

Single bundle entry with `import()` for Chart.js chunk.

**Rejected:** While HA does support ES modules (correcting original analysis), this would require multiple registered URLs. Single bundle is simpler.

## Tasks

### Chunk 1: Infrastructure (Tasks 1-4)

- [ ] **Task 1: Install Chart.js and Verify Bundling**
  - Install `chart.js` as devDependency (NO luxon adapter, NO date-fns adapter)
  - Do NOT change `build.js` format — keep `"esm"`
  - Create a temporary test: add `import "chart.js"` to barrel file, build, check bundle size
  - Verify: `npm run build` succeeds, note bundle size increase (~155KB expected)
  - Remove temporary test import after verification
  - **Gate check:** If bundle exceeds 250KB minified, investigate tree-shaking issues before proceeding
  - Files: `frontend/package.json`, `frontend/build.js` (verify no changes needed)

- [ ] **Task 2: Custom Date Adapter (TDD)**
  - TDD: Write `tests/date-adapter.test.js` first — test parse, format, diff, add, startOf, endOf
  - Implement `src/charts/date-adapter.js`: minimal Chart.js date adapter using native `Date` + `Intl.DateTimeFormat`
  - Must implement: `formats()`, `parse()`, `format()`, `add()`, `diff()`, `startOf()`, `endOf()`
  - Register via `_adapters._date.override({...})` as side effect on import
  - Verify: `node --test tests/date-adapter.test.js` passes, `npm test` all pass
  - Files: `frontend/src/charts/date-adapter.js`, `frontend/tests/date-adapter.test.js`

- [ ] **Task 3: Chart Utilities (TDD)**
  - Write `tests/chart-utils.test.js` first: ratingForScore, formatTimestamp, computeStats
  - Implement `src/charts/chart-utils.js`: rating helper, timestamp formatting, stats computation, CHART_METRICS, shared chart config builders (getThresholdGridColor, getZoneBackgrounds, createScoreGradient, resolveHAColor)
  - Verify: `node --test tests/chart-utils.test.js` passes, `npm test` all pass
  - Files: `frontend/src/charts/chart-utils.js`, `frontend/tests/chart-utils.test.js`

- [ ] **Task 4: Chart Loader**
  - Create `src/charts/chart-loader.js`: singleton that registers Chart.js components on first call
  - Tree-shaken imports: `LineController`, `LineElement`, `PointElement`, `LinearScale`, `TimeScale`, `Filler`, `Legend`, `Tooltip`
  - Import `../charts/date-adapter.js` (side-effect — registers the custom adapter)
  - Exports `ensureChartReady()` and `Chart`
  - **Early build verification:** Temporarily import chart-loader in barrel, build, verify Chart.js bundles correctly and check size. Remove temporary import after verification.
  - Verify: `npm run build` succeeds, bundle size is ~185-200KB
  - Files: `frontend/src/charts/chart-loader.js`

### Chunk 2: Forecast Chart Card (Tasks 5-6)

- [ ] **Task 5: paddle-chart-card**
  - Multi-metric line chart: score (always visible) + toggleable wind/temp/UV
  - Clickable legend chips for metric toggling
  - Dual y-axes (score left 0-100, raw values right)
  - Threshold grid lines at 70/40, gradient fill
  - Skeleton placeholder while initializing
  - Config: `entity` (required), `name`, `default_metrics`
  - Verify: `npm run build` succeeds
  - Files: `frontend/src/cards/paddle-chart-card.js`

- [ ] **Task 6: paddle-chart-editor**
  - Entity picker, name input, default_metrics checkboxes (score always checked)
  - Follows existing editor pattern (base-editor.js)
  - Verify: `npm run build` succeeds
  - Files: `frontend/src/editors/paddle-chart-editor.js`

### Chunk 3: History Chart Card (Tasks 7-8)

- [ ] **Task 7: paddle-history-card**
  - Score trend line with gradient fill over 7d/30d/90d
  - WebSocket `recorder/statistics_during_period` data fetching
  - Time range selector chips in header
  - Color-banded zone backgrounds (green/amber/red) via custom Chart.js plugin with `beforeDraw`
  - Stat chips below chart: Avg, Best, Go Days, Best Day
  - Render generation counter to prevent async race conditions
  - **try/catch in async `_render()`** — log errors with `console.warn` since called from sync setter
  - Skeleton placeholder during data fetch
  - Cache with 15-minute TTL + entity last_updated invalidation
  - Config: `entity` (required), `name`, `default_range`, `show_stats`
  - Verify: `npm run build` succeeds
  - Files: `frontend/src/cards/paddle-history-card.js`

- [ ] **Task 8: paddle-history-editor**
  - Entity picker, name input, default_range dropdown (7d/30d/90d), show_stats toggle
  - Verify: `npm run build` succeeds
  - Files: `frontend/src/editors/paddle-history-editor.js`

### Chunk 4: Integration & Finalization (Tasks 9-10)

- [ ] **Task 9: Update Barrel File and Rebuild**
  - Import 2 new cards + 2 new editors in `src/paddle-cards.js`
  - Register both in `window.customCards.push()`
  - Rebuild bundle, verify size ~185-205KB minified
  - Run all JS tests (`npm test`), verify pass
  - Files: `frontend/src/paddle-cards.js`, `frontend/dist/paddle-cards.js`

- [ ] **Task 10: Dashboard YAML and Full Verification**
  - Add `paddle-chart-card` to Forecast tab, `paddle-history-card` to History tab
  - Run full Python test suite (`pytest tests/ -v`) — regression check
  - Run all JS tests (`npm test`)
  - Final bundle size check and document actual size in progress log
  - Files: `custom_components/paddle_conditions/dashboard/paddle.yaml`

## Implementation Plan Reference

Code templates are in `docs/superpowers/plans/2026-03-10-chartjs-dashboard-cards.md`. **Critical modifications from this TPP:**
1. Replace all `chartjs-adapter-luxon` references with custom `date-adapter.js`
2. Keep `format: "esm"` in build.js (do NOT change to IIFE)
3. Add try/catch to history card's async `_render()`
4. Use corrected bundle size estimates (~185-205KB, not 75-85KB)

## Progress Log

- **2026-03-10:** TPP created from approved design spec and reviewed implementation plan.
- **2026-03-10:** TPP re-researched and rewritten:
  - **Fixed critical Luxon assumption:** HA does NOT expose Luxon to custom cards. Replaced `chartjs-adapter-luxon` with custom minimal date adapter (~50 lines, ~1KB vs ~70KB).
  - **Fixed bundle size estimates:** Chart.js tree-shaken is ~155KB minified, not ~40KB. Total bundle ~185-205KB, not 75-85KB. Gzipped ~65-75KB.
  - **Fixed build format:** Keep ESM (not IIFE). HA loads modules via `import()`, not classic `<script>` tags. v1 already works as ESM.
  - **Added early build verification:** Tasks 1 and 4 now include build+size checks to catch bundling issues before writing card code.
  - **Added async error handling:** History card's `_render()` needs try/catch since it's called from a sync setter.
  - **Verified recorder compatibility:** Score sensors have `state_class=MEASUREMENT`, confirming WebSocket statistics API will return data.
  - **Added custom date adapter task** (Task 2, TDD): replaces the Luxon adapter dependency.
  - Increased from 9 to 10 tasks (added date adapter task, added early build verification steps).
  - Added comprehensive lore corrections with evidence for each finding.
