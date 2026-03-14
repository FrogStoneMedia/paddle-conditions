# Changelog

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
