# Changelog

## 2.0.0

Requires Home Assistant 2026.9 or later.

### Breaking
- Conditions sensor states are now keys such as `partly_cloudy` instead of English text. The displayed text is unchanged and now translatable. Update automations that compared against the old text.
- Cloud sync is removed. It posted to an endpoint the Paddle Conditions API no longer has, so it never worked; the saved URL and token are deleted on upgrade.
- 3-Hour Forecast is enabled by default and no longer a diagnostic entity. Streamflow is enabled for locations with a USGS station. On upgrade, these sensors are enabled if the old defaults disabled them; ones you disabled yourself stay disabled.
- The paddle-spots-card opens a location's details when tapped instead of scrolling to its card.
- Forecast attributes (`blocks`, `best_block`, `best_score`, `daylight` and the `hourly_*` arrays) are no longer written to the recorder. Live attributes are unchanged, but history graphs and statistics of those attributes stop growing.

### Added
- Six dashboard cards in one bundle: score, spots, factors, forecast, chart and history, with visual editors and sections-view sizing. Existing `paddle-score-card` and `paddle-spots-card` dashboards keep working.
- Forecast blocks now score hourly air quality and visibility, like the current score does, and the profile vetoes for poor air and low visibility apply to each block
- Picking a Paddle Score sensor in the card picker suggests the Paddle cards
- Each location's own sunrise and sunset, used for "best time"
- Rating sensor (Go / Caution / No-go) for automations
- Optional free USGS API key for faster river updates (every 15 to 20 minutes instead of hourly)
- Repair issue when USGS rate limits your network, cleared automatically on recovery
- Wind gusts in the hourly forecast and in each forecast block
- Automation example, known limitations and removal instructions in the README

### Changed
- USGS data comes from the new USGS Water Data API. The old WaterServices API slows down from November 16, 2026 and shuts down February 22, 2027.
- USGS is polled hourly (every 15 to 20 minutes with a key; it is checked on each regular update) instead of on every weather update
- USGS and NOAA readings older than six hours are dropped, even when the service still returns them
- Forecast starts at the current hour; hourly times are UTC with an explicit offset
- Wind Direction uses angle statistics, so long-term averages are correct
- Locations follow their display order in the generated dashboard
- Diagnostics redact coordinates, location names and the USGS key, and show which sources are failing

### Fixed
- Cards showed °F and mph on metric systems, and used the Home Assistant home's sunrise instead of the spot's
- The card details overlay could get stuck invisible over the dashboard and didn't keep keyboard focus inside it
- Rating colours failed contrast on some backgrounds; spots-card scores were nearly unreadable on their badges
- The spots card couldn't navigate to a location's card
- The history card could stay on its loading placeholder
- A 223 KB unused card bundle was shipped to every install
- Adding two locations back to back left the second without sensors until restart
- The 3-hour forecast showed blocks from earlier in the day
- Rain chance had no effect on forecast block scores
- Saving options removed the streamflow and tide weights, so river locations stopped scoring flow. Weights lost this way are restored on upgrade.
- When the weather API was down, the last score stayed on screen as current indefinitely. It now goes unavailable after an hour, or two update intervals if that is longer.
- Editing a location reloaded the integration twice
- Dashboard cards could be added to Lovelace more than once; existing duplicates are cleaned up
- The generated dashboard guessed entity IDs; it now uses your actual score entities, and the score card re-renders for a renamed score entity
- A factor weighted 0 could still be reported as the limiting factor
- Missing hourly values from Open-Meteo could stop updates
- Unknown weather codes (freezing rain, snow grains, snow showers) showed as empty conditions

## 1.0.0

### Added
- Accessibility: keyboard navigation (Enter/Space) on all interactive elements
- Accessibility: ARIA roles, labels, and states for screen readers
- Accessibility: focus-visible outlines on all focusable elements
- Accessibility: prefers-reduced-motion support to disable animations
- Accessibility: dialog focus trap on detail overlay
- Accessibility: progressbar roles on factor score bars
- Retina-quality mobile screenshots in README documentation
- Accessibility section in README

### Fixed
- Improved color contrast throughout all cards (chart thresholds, zone backgrounds, score colors, inactive elements)

## 0.9.0

### Added
- Entity categories: streamflow, condition, and forecast sensors marked as diagnostic
- Disabled by default: streamflow and forecast sensors (enable in entity settings if needed)
- Icons: custom MDI icons for all 13 sensors and the dashboard service
- Config flow validation: weather API connectivity tested when adding/editing locations
- Quality scale tracking: quality_scale.yaml documents compliance with all 51 HA rules
- Comprehensive documentation: data updates, sensors reference, automation examples, troubleshooting
- Overlay centering on wide screens with max-width constraint

### Fixed
- Removed duplicate comment in frontend registration code
- CI: use system Python on self-hosted runners, run HACS validation only on tags

## 0.7.0

### Added
- Detail overlay: tap the score hero to see full-screen stacked line charts for paddle score, wind, temperature, UV index, and precipitation
- Smooth rounded SVG lines with synced "now" marker across all charts
- Sunrise/sunset markers on score chart, wind direction arrows, UV danger zones
- Swipe-down-to-close and Escape key dismiss on overlay

### Fixed
- Companion app "configuration error" on pull-to-refresh: register cards through Lovelace resources collection instead of add_extra_js_url
- Overlay header layout: centered score with separated close button (no overlap)
- Disabled cache_headers on static paths to prevent stale JS in mobile WebViews

## 0.6.0

### Fixed
- Sensor crash when coordinator.data is None (added None guards)
- Response pool leak: read body inside async context manager timeout
- USGS -999999 no-data sentinel values now filtered
- Weather fetch runs in parallel with other API calls (was sequential)
- Frontend JS double-registration on integration reload
- KeyError in options flow when activity has no default profile
- Zero-duration forecast blocks no longer generated
- Corrected scoring docstring and documentation arithmetic examples

## 0.5.0

### Fixed
- Startup freeze: parallelize coordinator refresh with asyncio.gather
- Use cache fallback when first refresh fails
- Hourly data timezone: use local time instead of UTC

## 0.4.0

### Added
- Dashboard cards: paddle-score-card and paddle-spots-card
- Service action for generating dashboard YAML
- Subentry reconfigure flow for editing existing locations

## 0.3.0

### Added
- 3-hour forecast blocks with per-block scoring
- Hourly data arrays (wind, temp, UV, precipitation)
- Factor drill-down in score card

## 0.2.0

### Added
- USGS water temperature and streamflow support
- NOAA tide and coastal water temperature
- Multiple paddler profiles (Recreational, Racing, Family)

## 0.1.0

### Added
- Initial release
- Open-Meteo weather and AQI integration
- Paddle score computation with 7 weighted factors
- Config flow with location subentries
- Cloud sync (optional)
