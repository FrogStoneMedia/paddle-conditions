# TPP: Bundled Dashboard Cards

## Summary

Replace external HACS card dependencies (Mushroom, ApexCharts, card-mod) with integration-bundled custom Lovelace web components. Zero external frontend dependencies for end users.

**v1 scope:** 5 core cards (score, factors, chips, forecast, fitness placeholder) + editors. Chart.js cards (chart, history) deferred to v2 to reduce risk and bundle size.

## Current phase

- [x] Research & Planning
- [x] Task breakdown
- [x] Write breaking tests
- [x] Implementation
- [ ] Review & Refinement
- [ ] Final Integration
- [ ] Review

## Required reading

- `CLAUDE.md` — project conventions, git prefixes, design principles
- `docs/superpowers/specs/2026-03-10-bundled-dashboard-cards-design.md` — approved design spec
- `ha-integration/custom_components/paddle_conditions/__init__.py` — current init (41 lines, no `async_setup` yet)
- `ha-integration/custom_components/paddle_conditions/sensor.py` — sensor entity definitions (data contract, 13 sensors)
- `ha-integration/custom_components/paddle_conditions/models.py` — PaddleScore, PaddleConditions, ForecastBlock dataclasses
- `ha-integration/custom_components/paddle_conditions/const.py` — DOMAIN, score thresholds (SCORE_GO=70, SCORE_CAUTION=40)
- `ha-integration/custom_components/paddle_conditions/manifest.json` — v1.0.0, `dependencies: []` (needs updating)
- `ha-integration/custom_components/paddle_conditions/dashboard/paddle.yaml` — current Mushroom dashboard (655 lines)

## Description

The current HA dashboard requires users to install 3 external HACS cards (Mushroom, ApexCharts, card-mod). This TPP replaces them with bundled custom Lovelace cards inside the integration itself. The Python side registers a static path + JS resource via a new `async_setup()` function. esbuild bundles all cards into a single ES module. Dashboard YAML uses `type: custom:paddle-*-card`.

**Architecture:** Vanilla JS web components (no Lit), Shadow DOM, esbuild bundler, Node.js built-in test runner for JS utils, pytest for Python frontend registration tests.

**v1 vs v2 split:** v1 ships the 5 cards that need no external charting library (~20-40KB bundle). v2 adds Chart.js-based chart and history cards (~140-160KB bundle with Chart.js + zoom plugin + Hammer.js + date adapter). This split reduces risk — v1 is independently useful and testable.

## Lore

### HA Frontend Registration (verified 2026-03-10)

- **`register_static_path()` (sync) was REMOVED in HA 2025.7.** Must use `hass.http.async_register_static_paths([StaticPathConfig(url_path, path, cache_headers)])`. Import `StaticPathConfig` from `homeassistant.components.http`.
- **`add_extra_js_url(hass, url)`** from `homeassistant.components.frontend` is the stable API for registering Lovelace JS resources. Import it inside `async_setup()`, not at module level.
- **`manifest.json` must declare `"dependencies": ["frontend", "http"]`** — without these, HA may not load those components before ours runs, and imports will fail.
- **Deferred registration pattern:** Frontend registration should be deferred until HA is fully started. Use `hass.state == CoreState.running` check with `EVENT_HOMEASSISTANT_STARTED` listener fallback. This prevents race conditions if HTTP server isn't ready.
- **`window.customCards` array** — cards must push to `window.customCards` for HA's card picker to discover them. Without this, cards only work via manual YAML `type: custom:paddle-*-card`.

### async_setup() vs async_setup_entry()

- `async_setup()` is NEW to this codebase — existing code only has `async_setup_entry()`.
- HA calls `async_setup()` once per domain load (before any config entries), then `async_setup_entry()` per config entry.
- `async_setup()` must return `True` and must not interfere with the entry setup flow.
- `async_setup()` must have full type annotations — the codebase passes mypy strict mode.

### Codebase Conventions (from existing code and past bugs)

- Import statements in `__init__.py` must come AFTER `from __future__ import annotations`.
- Tests require the `enable_custom_integrations` fixture for HA custom component testing (past bug #13159).
- `AsyncMock` has known incompatibility with aiohttp sync methods (past bug #13160) — use `MagicMock` for sync HTTP methods.
- All Python code must pass mypy strict mode (completed in Phase 8).

### Sensor Data Contract (from sensor.py + models.py)

- **Score sensor** (`key="score"`): `state` = 0-100 int, attrs: `rating` ("GO"/"CAUTION"/"NO_GO"), `activity`, `profile`, `limiting_factor`, `factors` (dict: `wind_speed`→int, `wind_gusts`→int, `air_quality`→int, `temperature`→int, `uv_index`→int, `visibility`→int, `precipitation`→int), `missing_factors` (list), `vetoed` (bool), `veto_reason`
- **Forecast sensor** (`key="forecast_3hr"`): `state` = first block score or None, attrs: `blocks` (array of `{start, end, score, rating, wind_mph, temp_f, uv}`), `best_block` (start time string), `best_score` (0-100 int)
- **Individual sensors**: `wind_speed` (mph float), `wind_gusts` (mph float), `air_temp` (°F float), `water_temp` (°F float, nullable), `uv_index` (float), `aqi` (int), `visibility` (miles float), `precipitation` (% int), `streamflow` (CFS float), `condition` (string)
- **Entity ID pattern**: `sensor.paddle_conditions_{location_slug}_{sensor_key}` — uses `_attr_has_entity_name = True` with device name = location name, manufacturer = "Paddle Conditions"

### Entity ID Derivation for Factors Card

- Score entity: `sensor.paddle_conditions_{loc}_score`
- To get raw value entity: replace `_score` suffix with `_{sensor_suffix}`
- Factor-to-sensor mapping (from scoring factors dict key → sensor entity key):
  - `wind_speed` → `wind_speed`, `wind_gusts` → `wind_gusts`, `air_quality` → `aqi`, `temperature` → `air_temp`, `uv_index` → `uv_index`, `visibility` → `visibility`, `precipitation` → `precipitation`
- Note: `air_quality` maps to `aqi` sensor, `temperature` maps to `air_temp` sensor — these are NOT 1:1 name matches

### Frontend Build

- `package.json` must have `"type": "module"` for ES module support in Node.js 20+.
- No `--experimental-vm-modules` flag needed — `"type": "module"` is sufficient.
- `build.js` must use `import esbuild from "esbuild"` (ESM), not `require()` (CJS).
- `frontend/dist/paddle-cards.js` is committed (not gitignored) for HACS distribution.
- `frontend/node_modules/` IS gitignored.

### Shadow DOM and innerHTML Safety

- Cards use `this.shadowRoot.innerHTML` for rendering. All data comes from HA's trusted state objects. Entity states and attributes are set by the integration's Python backend from known API responses. Shadow DOM provides isolation. This is the standard pattern used by HA's built-in cards and community cards.
- HA custom elements (`ha-icon`, `ha-entity-picker`) need imperative property binding, not HTML attributes. They are globally registered by HA's frontend and available in any custom element's shadow root.

### Chart.js (v2 scope, documenting for future)

- Chart.js vendor files are UMD format — esbuild may need shimming. Fallback: install via npm as devDependencies.
- Chart.js `time` scale requires a date adapter (`chartjs-adapter-date-fns`) — must be vendored/installed alongside Chart.js.
- CSS variables don't work in `<canvas>` — resolve HA theme colors at render time via `getComputedStyle()`.
- `chartjs-plugin-zoom` requires `Hammer.js` as peer dependency for touch gestures.
- History card needs `hass.callWS({ type: "recorder/statistics_during_period" })` for historical data.

## Solutions

### Option A (preferred for v1): Pure JS cards, no Chart.js

Ship 5 cards with zero charting dependency. Score, factors, chips, forecast (HTML table), and fitness placeholder are all achievable with plain DOM + CSS. Bundle size ~20-40KB.

**Pros:** Small bundle, no UMD/ESM headaches, fast to implement, independently useful.
**Cons:** No charts until v2.

### Option B (full): All 7 cards with Chart.js

Ship all 7 cards including Chart.js-based chart and history cards. Bundle size ~140-160KB.

**Pros:** Complete feature set from day one.
**Cons:** Chart.js UMD bundling risk, date adapter dependency, larger scope, more failure modes.

**Decision:** v1 = Option A. v2 = extend to Option B. The implementation plan below covers v1. The design spec and v2 plan remain valid references for later.

## Tasks

### Chunk 1: Infrastructure (Tasks 1-3)

- [x] **Task 1: Build Tooling Setup**
  - Create `frontend/` directory structure: `src/cards/`, `src/editors/`, `src/styles/`, `dist/`, `tests/`
  - Create `package.json` with `"type": "module"`, esbuild devDependency, build/watch/test scripts
  - Create `build.js` using ESM imports
  - Add `frontend/node_modules/` to `.gitignore`
  - Create placeholder `src/paddle-cards.js` entry point
  - Verify: `npm install && npm run build` succeeds, `dist/paddle-cards.js` exists
  - Files: `frontend/package.json`, `frontend/build.js`, `frontend/src/paddle-cards.js`

- [x] **Task 2: Shared Styles & Utility Functions**
  - TDD: Write `tests/utils.test.js` first (colorForRating, colorForScore, formatScore, FACTOR_META, FACTOR_SENSOR_SUFFIX)
  - Implement `src/utils.js` with color/format helpers, factor metadata, sensor suffix map, fireMoreInfo helper, iconForRating
  - Implement `src/styles/theme.js` with shared CSS using HA theme variables
  - Verify: `node --test tests/utils.test.js` passes
  - Files: `frontend/src/utils.js`, `frontend/src/styles/theme.js`, `frontend/tests/utils.test.js`

- [x] **Task 3: Python Frontend Registration + manifest.json update**
  - **Update `manifest.json`**: Add `"dependencies": ["frontend", "http"]`
  - TDD: Write `tests/test_frontend.py` using proper HA test fixtures
    - Must use `async_register_static_paths([StaticPathConfig(...)])` (NOT the removed sync API)
    - Must use `enable_custom_integrations` fixture
    - Test that `async_setup()` registers static path and JS resource URL
    - Test that version string is in the URL for cache-busting
  - Add `async_setup(hass: HomeAssistant, config: ConfigType) -> bool` to `__init__.py`
    - Use deferred registration pattern (check `hass.state == CoreState.running`, else listen for `EVENT_HOMEASSISTANT_STARTED`)
    - Call `hass.http.async_register_static_paths([StaticPathConfig(url, path, cache_headers=True)])`
    - Call `add_extra_js_url(hass, url_with_version)`
    - Full type annotations for mypy strict
  - Verify: `pytest tests/test_frontend.py -v` passes, all 168+ existing tests still pass, `mypy` passes
  - Files: `__init__.py`, `manifest.json`, `tests/test_frontend.py`

### Chunk 2: Core Cards (Tasks 4-8)

Each card follows this pattern:
1. Extends `HTMLElement`, attaches Shadow DOM in constructor
2. Implements `setConfig(config)`, `set hass(hass)`, `getCardSize()`, `static getStubConfig()`, `static getConfigElement()`
3. Renders inside `<ha-card>` using shared styles from `theme.js`
4. Registers via `customElements.define("paddle-*-card", ...)`
5. Pushes to `window.customCards` array for card picker discovery
6. Gets imported in barrel file `src/paddle-cards.js` and rebuilt

- [x] **Task 4: paddle-score-card**
  - Hero card: colored left border (Go/Caution/No-go), icon circle with tinted background, score %, rating badge, profile/activity info, limiting factor or veto reason
  - Config: `entity` (required), `name`, `show_profile` (default true), `show_limiting_factor` (default true)
  - Tap action: fires `hass-more-info` event
  - Data: reads score sensor state + attributes

- [x] **Task 5: paddle-factors-card**
  - 7 rows showing factor breakdown from score entity's `factors` attribute
  - Each row: colored icon circle, factor name (from FACTOR_META), raw value + unit (from individual sensor entity), animated progress bar, numeric sub-score
  - Uses FACTOR_SENSOR_SUFFIX to derive individual sensor entity IDs from score entity ID
  - Config: `entity` (score entity), `show_factors` (array of factor keys, default all 7)

- [x] **Task 6: paddle-chips-card**
  - Horizontal row of pill-shaped chips, one per location score entity
  - Each chip: status dot (rating color), location name (from friendly_name), score %
  - Active chip has colored border; optional refresh chip with spin animation
  - Config: `entities` (required, array of score entity IDs), `show_refresh` (default true)

- [x] **Task 7: paddle-forecast-card**
  - "Best Window" banner at top with star icon + time + score
  - HTML table: Time, Score (colored pill), Rating (colored text), Wind, Temp, UV
  - Best window row highlighted with accent background
  - Empty state when no blocks available
  - Config: `entity` (forecast sensor), `max_blocks` (default 8)

- [x] **Task 8: paddle-fitness-card**
  - Branded placeholder: paddle icon, "Session Tracking" title, feature list
  - Always shows placeholder in v1 (no session data exists yet)
  - Config: `entity` (optional, future), `monthly_goal` (default 12)

### Chunk 3: Editors (Task 9)

- [x] **Task 9: Card Editors**
  - Create `editors/base-editor.js` with shared `fireConfigChanged()` helper and editor styles
  - Create 5 editor elements (one per card):
    - `paddle-score-editor`: entity picker, name textfield, show_profile switch, show_limiting_factor switch
    - `paddle-factors-editor`: entity picker, show_factors checkboxes
    - `paddle-chips-editor`: entity picker list (add/remove), show_refresh switch
    - `paddle-forecast-editor`: entity picker, max_blocks number
    - `paddle-fitness-editor`: entity picker (optional), monthly_goal number
  - Wire `getConfigElement()` in each card to return the corresponding editor
  - `ha-entity-picker` properties must be set imperatively (not via HTML attributes)
  - Import all editors in barrel file and rebuild

### Chunk 4: Dashboard & Finalization (Tasks 10-12)

- [x] **Task 10: Dashboard Migration**
  - Move `dashboard/paddle.yaml` → `dashboard/legacy/paddle-mushroom.yaml`
  - Create new `dashboard/paddle.yaml` with 4 tabs:
    - Conditions: chips, score, native entities card, factors
    - Forecast: forecast card, native entities for wind/temp details
    - Fitness: fitness placeholder
    - History: native `logbook` card (Chart.js history card deferred to v2)
  - Use `lake_austin` as placeholder location slug with comments

- [x] **Task 11: Documentation**
  - Create `dashboard/REFERENCE.md` documenting design lineage (Mushroom, ApexCharts, card-mod — pattern references only, no code copied)
  - Update `ha-integration/README.md`: replace "Required Frontend Cards" with "Dashboard Setup" showing zero-dependency install

- [x] **Task 12: Final Build & Verification**
  - Finalize barrel file `src/paddle-cards.js` with all 5 cards + 5 editors + `window.customCards` registrations + console.info load message
  - Run `npm run build`, verify bundle size (~20-40KB expected)
  - Run `node --test tests/utils.test.js` — all JS tests pass
  - Run `pytest tests/ -v` — all Python tests pass (168+ existing + new frontend tests)
  - Run `mypy` — zero errors
  - Commit built bundle

## v2 Roadmap (not in this TPP)

- **paddle-chart-card**: Chart.js dual-axis line chart with zoom, gradient fill, date adapter
- **paddle-history-card**: Score trend with stat summary, WebSocket recorder API
- **Chart.js vendor/npm setup**: Vendor Chart.js 4.x + chartjs-plugin-zoom + Hammer.js + chartjs-adapter-date-fns
- **Chart card editors**: paddle-chart-editor (complex dynamic series list), paddle-history-editor

## Progress Log

- **2026-03-10:** TPP created from approved design spec and implementation plan.
- **2026-03-10:** All 12 tasks implemented:
  - Chunk 1: Build tooling (esbuild), shared utils (20 JS tests), Python frontend registration (6 pytest tests, async_setup with deferred pattern)
  - Chunk 2: 5 cards — score, factors, chips, forecast, fitness (all imperative DOM, no innerHTML)
  - Chunk 3: 5 editors + base-editor with HA entity pickers
  - Chunk 4: Dashboard migration (legacy preserved), docs updated, README updated
  - Final: 29.8KB bundle, 20/20 JS tests, 166/166 Python tests, mypy strict 0 errors
  - Branch: `feature/bundled-dashboard-cards` in `.worktrees/bundled-dashboard-cards`
- **2026-03-10:** TPP reviewed and rewritten:
  - Split scope: v1 = 5 pure-JS cards, v2 = Chart.js cards. Reduces risk and bundle size.
  - Fixed critical API bug: `register_static_path()` removed in HA 2025.7 → use `async_register_static_paths([StaticPathConfig(...)])`
  - Fixed missing manifest dependencies: must declare `["frontend", "http"]`
  - Fixed test approach: must use `enable_custom_integrations` fixture, mock async API
  - Added deferred registration pattern for frontend setup
  - Added `window.customCards` registration (was missing entirely)
  - Added mypy strict mode requirement for new Python code
  - Reduced from 14 tasks to 12 tasks, renumbered
  - Added comprehensive lore from codebase exploration and HA API research
