# <img src="https://brands.home-assistant.io/_/paddle_conditions/icon.png" alt="Paddle Conditions" width="50" height="50"/> Paddle Conditions

[![License](https://img.shields.io/github/license/FrogStoneMedia/paddle-conditions?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)

A [Home Assistant](https://www.home-assistant.io/) custom integration for paddle sport conditions monitoring. Get real-time weather, water, and air quality data for your favorite SUP and kayaking spots with a single-glance **Go / Caution / No-go** score.

All data comes from **free public APIs** — no accounts, API keys, or subscriptions required.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Scoring](#scoring)
- [Dashboard](#dashboard)
- [Data Sources](#data-sources)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Paddle Score
- **Single-glance rating** — Go, Caution, or No-go for any paddle location
- **7 weighted factors** — wind speed, wind gusts, AQI, temperature, UV index, visibility, precipitation
- **Hard vetoes** — automatically blocks for dangerous conditions like thunderstorms or extreme wind
- **24-hour forecast** — eight 3-hour blocks with per-block scores and a "best window" recommendation

### Multi-Sport Profiles
- **Paddle Boarding** — Recreational, Racing, Family
- **Kayaking** — Flatwater, River, Ocean
- Each profile has tuned scoring curves, weights, and veto thresholds
- Fully customizable weights via the options UI

### Multi-Location Support
- Add unlimited paddle locations as subentries
- Each location gets its own set of sensors and independent update cycle
- Supports lakes, rivers, and bays/oceans with location-appropriate data sources

### Bundled Dashboard Cards
Custom Lovelace cards included — **no extra HACS card dependencies required**:
- **paddle-score-card** — Hero score with Go/Caution/No-go rating
- **paddle-factors-card** — Factor breakdown with progress bars
- **paddle-chips-card** — Location navigation chips
- **paddle-forecast-card** — 3-hour forecast table with best window
- **paddle-chart-card** — Chart.js line/bar visualization for score, wind, temp, UV
- **paddle-history-card** — Score history graph with configurable range and statistics

---

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu > **Custom repositories**
3. Add this repository URL as an **Integration**:
   ```
   https://github.com/FrogStoneMedia/paddle-conditions
   ```
4. Search for "Paddle Conditions" and install it
5. Restart Home Assistant

<details>
<summary>Manual Installation</summary>

Copy `custom_components/paddle_conditions/` to your Home Assistant `custom_components/` directory and restart.

</details>

---

## Configuration

### Adding the Integration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "Paddle Conditions" and confirm setup
3. Click the integration card, then **Add Entry** to add your first paddle location

### Adding a Location

For each location you'll need:

| Field | Required | Description |
|-------|----------|-------------|
| Location name | Yes | A friendly name, e.g. "Lake Union" or "Deschutes River" |
| Latitude | Yes | Decimal degrees (tip: right-click on Google Maps to copy coordinates) |
| Longitude | Yes | Decimal degrees |
| Water body type | Yes | Lake, River, or Bay/Ocean — determines which data sources and scoring factors apply |
| USGS station ID | No | For river streamflow data. Find yours at [waterdata.usgs.gov](https://waterdata.usgs.gov) |
| NOAA station ID | No | For water temperature and tide data. Find yours at [tidesandcurrents.noaa.gov](https://tidesandcurrents.noaa.gov) |
| Optimal streamflow | No | Your preferred river flow in CFS (river locations only) |

### Options

Access via the integration card > **Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Activity | Paddle Boarding | Switch between SUP and kayaking — each has its own profiles |
| Profile | Recreational | Preset weight configuration for your paddling style |
| Update interval | 10 min | How often to refresh data (5–60 minutes) |
| Factor weights | Profile defaults | Fine-tune individual scoring weights (auto-normalized to 100%) |

---

## Entities

Each location creates 12 sensor entities:

| Entity | Unit | Description |
|--------|------|-------------|
| `paddle_score` | % | Overall score (0–100) with Go/Caution/No-go rating |
| `wind_speed` | mph | Current wind speed |
| `wind_gusts` | mph | Peak wind gusts |
| `wind_direction` | ° | Wind bearing in degrees |
| `air_temp` | °F | Current air temperature |
| `water_temp` | °F | Water temperature (requires USGS or NOAA station) |
| `uv_index` | — | UV radiation index |
| `aqi` | AQI | US Air Quality Index |
| `visibility` | mi | Atmospheric visibility |
| `precipitation` | % | Precipitation probability |
| `streamflow` | CFS | River flow rate (river locations only, requires USGS station) |
| `condition` | — | Weather description (e.g., "Clear sky", "Thunderstorm") |
| `forecast_3hr` | — | 3-hour forecast blocks with per-block scores |

### Paddle Score Attributes

The `paddle_score` sensor includes rich attributes:

| Attribute | Description |
|-----------|-------------|
| `rating` | GO, CAUTION, or NO_GO |
| `activity` | Current activity (sup or kayaking) |
| `profile` | Active scoring profile |
| `limiting_factor` | The condition most impacting your score |
| `factors` | Individual scores for each weather factor |
| `veto` | Whether a hard veto is active (e.g., thunderstorm) |

### Forecast Attributes

The `forecast_3hr` sensor provides:
- Array of up to 8 forecast blocks (24 hours)
- Each block: score, rating, wind, temperature, UV, start/end times
- `best_block` and `best_score` for quick "when should I go?" answers

---

## Scoring

Seven factors are scored individually using piecewise linear curves tuned to your profile, then combined using weighted averaging:

| Factor | Recreational Weight | What It Measures |
|--------|-------------------|------------------|
| Wind speed | 30% | Sustained wind — the biggest factor for most paddlers |
| Air quality | 20% | US AQI — important for extended exertion outdoors |
| Temperature | 15% | Comfort range with penalties for extremes |
| Wind gusts | 10% | Gust intensity above sustained wind |
| UV index | 10% | Sun exposure risk |
| Visibility | 10% | Fog, haze, and low-visibility hazards |
| Precipitation | 5% | Rain probability |

Weights are fully customizable. Profiles provide sensible defaults — Racing tolerates more wind, Family is stricter across the board.

**Hard vetoes** override the score entirely:
- Thunderstorms (always enforced)
- Extreme wind (profile-dependent threshold)
- Dangerous AQI levels

---

## Dashboard

The integration includes a reference dashboard at `custom_components/paddle_conditions/dashboard/paddle.yaml`.

### Importing the Dashboard

1. Go to **Settings > Dashboards > Add Dashboard**
2. Choose **From scratch** and create a new dashboard
3. Open the dashboard, switch to YAML mode (three dots > Edit > Raw configuration editor)
4. Paste the contents of `paddle.yaml`, replacing location slugs with your configured location names

### Bundled Cards

All cards are automatically registered when the integration loads. Each card has a visual editor accessible from the dashboard UI — no YAML required for customization.

| Card | Purpose |
|------|---------|
| `paddle-score-card` | Large hero card with score, rating, and key conditions |
| `paddle-factors-card` | Horizontal progress bars for each scoring factor |
| `paddle-chips-card` | Compact location chips for multi-spot navigation |
| `paddle-forecast-card` | Tabular 3-hour forecast with highlighted best window |
| `paddle-chart-card` | Chart.js time-series graphs for score, wind, temp, UV |
| `paddle-history-card` | Historical score graph with configurable range (7d, 30d, etc.) |

---

## Data Sources

All APIs are free, public, and require no authentication.

| Source | Data Provided | Required |
|--------|--------------|----------|
| [Open-Meteo Weather](https://open-meteo.com/) | Wind, temperature, UV, visibility, precipitation, weather codes, 48-hour hourly forecast | Yes |
| [Open-Meteo Air Quality](https://open-meteo.com/) | US AQI, PM2.5, PM10, ozone | Yes |
| [USGS Water Services](https://waterservices.usgs.gov/) | Water temperature, streamflow (CFS) | No — river locations |
| [NOAA CO-OPS](https://tidesandcurrents.noaa.gov/) | Water temperature, tide predictions | No — bay/ocean locations |

- Weather and AQI are required; the integration won't load without them
- USGS and NOAA are optional and degrade gracefully — if a station is unavailable, those factors are excluded and weights are renormalized
- All API calls run in parallel for performance
- Retry logic with exponential backoff on server errors

---

## Troubleshooting

### No data after setup
- Verify your coordinates are correct (latitude ±90, longitude ±180)
- Check **Settings > System > Logs** for `paddle_conditions` errors
- Open-Meteo may be temporarily unavailable — the integration retries automatically

### Water temperature or streamflow missing
- These require a USGS or NOAA station ID in your location configuration
- Verify your station ID at [waterdata.usgs.gov](https://waterdata.usgs.gov) or [tidesandcurrents.noaa.gov](https://tidesandcurrents.noaa.gov)
- Not all stations report all parameters — check that your station provides the data you expect

### Score seems wrong
- Check **limiting_factor** on the paddle_score entity — it tells you which condition is dragging the score down
- Review your profile weights in **Configure** — the default profile may not match your preferences
- A hard veto (thunderstorm, extreme wind) overrides the calculated score entirely

### Cards not appearing
- Cards are registered automatically when the integration loads
- If cards don't appear in the card picker, try clearing your browser cache or restarting HA
- Check the browser console (F12) for JavaScript errors

---

## Contributing

See [CONTRIBUTING.md](https://github.com/FrogStoneMedia/paddle-conditions/blob/main/CONTRIBUTING.md) for development setup, testing, and guidelines.

**Quick summary:**
- Python 3.12+, `pip install -r requirements_test.txt`
- TDD is mandatory — write failing tests first
- `pytest tests/ -v` to run the full suite
- `ruff check . && ruff format .` for linting
- Commit prefix: `[ha-integration] Brief description`

---

## License

MIT — see [LICENSE](https://github.com/FrogStoneMedia/paddle-conditions/blob/main/LICENSE).
