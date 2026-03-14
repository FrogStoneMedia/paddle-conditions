# <img src="custom_components/paddle_conditions/brand/icon.png" alt="Paddle Conditions" width="50" height="50"/> Paddle Conditions

[![License](https://img.shields.io/github/license/FrogStoneMedia/paddle-conditions?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.3%2B-41BDF5?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)

Paddle Conditions is a [Home Assistant](https://www.home-assistant.io/) custom integration that fetches weather, water, and air quality data for your paddle spots, scores each one **Go / Caution / No-go**, and shows a 24-hour forecast so you can pick the best window. All data comes from free public APIs. No accounts, no API keys, no subscriptions.

I built this because I was tired of checking four different apps before every paddle. Wind on one site, AQI on another, water temp somewhere else, streamflow on a USGS page that looks like it was designed in 1998. I paddle year-round on spots like [Lake Natoma](https://www.mklibrary.com/lake-natoma-california/), [Sand Harbor at Tahoe](https://www.mklibrary.com/sand-harbor-state-park-paddle-boarding/), and [New Bullards Bar Reservoir](https://www.mklibrary.com/new-bullards-bar-reservoir-california/), and I do [distance sessions](https://www.mklibrary.com/why-you-bonk-on-long-paddle-board-sessions/) where conditions at launch can be completely different from conditions at mile 5. I needed one place that pulled it all together and told me: should I go, or not?

---

## Table of contents

- [Features](#features)
- [Use cases](#use-cases)
- [Installation](#installation)
- [Configuration](#configuration)
- [Data updates](#data-updates)
- [Sensors & entities](#sensors--entities)
- [Scoring](#scoring)
- [Dashboard](#dashboard)
- [Automation examples](#automation-examples)
- [Data sources](#data-sources)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Removal](#removal)
- [Contributing](#contributing)
- [License](#license)

---

## Features

### Paddle score
- **Go / Caution / No-go rating** for any paddle location
- **7 weighted factors**: wind speed, wind gusts, AQI, temperature, UV index, visibility, precipitation
- **Hard vetoes** block automatically for thunderstorms or extreme wind
- **24-hour forecast** in eight 3-hour blocks with a "best window" pick

### Profiles
- **Paddle boarding**: Recreational, Racing, Family
- **Kayaking**: Flatwater, River, Ocean
- Each profile has its own scoring curves, weights, and veto thresholds
- Weights are customizable in the options UI

### Multiple locations
- Add as many paddle locations as you want (each is a subentry)
- Each location gets its own sensors and update cycle
- Supports lakes, rivers, and bays/oceans with the right data sources for each

### Bundled dashboard cards
Custom Lovelace cards ship with the integration. No extra HACS card downloads needed.
- **`paddle-score-card`**: all-in-one card with hero score, Go/Caution/No-go rating, best time to paddle, factor grid with tap-to-expand hourly forecasts, and 3-hour forecast timeline
- **`paddle-spots-card`**: multi-location comparison with color-coded score badges for quick spot selection

### Caching
API data is cached to disk after each successful fetch. On restart, cached data loads immediately so your dashboard renders before APIs respond. If a weather API call fails, the integration falls back to cached data instead of going unavailable.

---

## Use cases

- **Morning paddle planning**: Check conditions before heading out. The paddle score tells you at a glance whether it is a Go, Caution, or No-go day, and the 3-hour forecast shows you the best window.
- **Multi-location comparison**: Compare scores across your favorite spots. The paddle-spots-card shows all your locations side by side with color-coded badges so you can pick the best one today.
- **Automated notifications**: Get alerted when conditions are ideal. Set up automations to notify you when the paddle score crosses a threshold or when wind drops below your comfort level. See [Automation examples](#automation-examples) below.
- **Trip planning**: Use 3-hour forecast blocks to find the best window for your session. Each block has its own score, wind, temperature, and UV data so you can plan around the weather instead of guessing.

---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu > **Custom repositories**
3. Add this repository URL as an **Integration**:
   ```
   https://github.com/FrogStoneMedia/paddle-conditions
   ```
4. Search for "Paddle Conditions" and install it
5. Restart Home Assistant

<details>
<summary>Manual installation</summary>

Copy `custom_components/paddle_conditions/` to your Home Assistant `custom_components/` directory and restart.

</details>

---

## Configuration

### Adding the integration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "Paddle Conditions" and confirm setup
3. Click the integration card, then **Add Entry** to add your first paddle location

### Adding a location

The integration ships with preset locations (Lake Natoma, Lake Clementine, Sand Harbor at Lake Tahoe, and New Bullards Bar Reservoir) that come pre-filled with coordinates and USGS station IDs. Pick a preset to start, or choose "Custom location" to enter everything yourself.

For each location you need:

| Field | Required | Description |
|-------|----------|-------------|
| Location name | Yes | A friendly name, e.g. "Lake Union" or "Deschutes River" |
| Latitude | Yes | Decimal degrees (right-click on Google Maps to copy) |
| Longitude | Yes | Decimal degrees |
| Water body type | Yes | Lake, River, or Bay/Ocean. Controls which data sources and scoring factors apply. |
| USGS station ID | No | For water temperature and river streamflow. Find yours at [waterdata.usgs.gov](https://waterdata.usgs.gov) |
| NOAA station ID | No | For water temperature and tides. Find yours at [tidesandcurrents.noaa.gov](https://tidesandcurrents.noaa.gov) |
| Optimal streamflow | No | Preferred river flow in CFS (river locations only) |

### Editing a location

To change a location's settings (e.g. adding a USGS station ID for water temperature):

1. Go to **Settings > Devices & Services > Paddle Conditions**
2. Click the three-dot menu next to the location you want to edit
3. Select **Reconfigure**
4. Update any fields and submit — the integration reloads automatically

### Options

Access via the integration card > **Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Activity | Paddle Boarding | SUP or kayaking, each with its own profiles |
| Profile | Recreational | Preset weight config for your paddling style |
| Update interval | 10 min | How often to refresh data (5 to 60 minutes) |
| Factor weights | Profile defaults | Adjust individual scoring weights (auto-normalized to 100%) |

---

## Data updates

The integration polls four API sources in parallel on a configurable interval:

- **Default polling interval**: 10 minutes, configurable from 5 to 60 minutes in the Options flow (Settings > Devices & Services > Paddle Conditions > Configure).

### API sources fetched each cycle

| Source | Data provided | Required |
|--------|---------------|----------|
| Open-Meteo Weather | Wind, temperature, UV, visibility, precipitation, weather codes, 48-hour hourly forecast | Yes |
| Open-Meteo Air Quality | US AQI, PM2.5, PM10, ozone | Yes (fails gracefully) |
| USGS Water Services | Water temperature, streamflow (CFS) | No (fails gracefully) |
| NOAA CO-OPS | Water temperature, tide predictions | No (fails gracefully) |

All four sources are fetched in parallel for each update cycle. Weather data from Open-Meteo is required to produce a paddle score. USGS, NOAA, and AQI data fail gracefully: if any of these sources are unavailable, the remaining factors are scored and weights are renormalized automatically.

### Cache and persistence

- API data is **persisted to disk** after each successful fetch.
- On startup, **cached data loads immediately** so sensors have values before the first API call completes.
- If APIs are unreachable at startup, the integration uses **cached data from the last successful fetch** as a fallback instead of showing sensors as unavailable.
- This means fast restarts with no data gaps, even when APIs are temporarily down.

---

## Sensors & entities

Each location creates 13 sensors:

| Sensor | Device Class | Unit | Description |
|--------|-------------|------|-------------|
| Paddle Score | - | % | Overall conditions score (0-100) |
| Wind Speed | wind_speed | mph | Current wind speed |
| Wind Gusts | wind_speed | mph | Current wind gusts |
| Wind Direction | - | ° | Wind direction in degrees |
| Air Temperature | temperature | °F | Current air temperature |
| Water Temperature | temperature | °F | Water temperature (USGS/NOAA) |
| UV Index | - | - | UV radiation index |
| Air Quality Index | aqi | - | Air quality index |
| Visibility | distance | mi | Visibility distance |
| Precipitation Chance | - | % | Precipitation probability |
| Streamflow | - | CFS | River streamflow (diagnostic, disabled by default) |
| Conditions | - | - | Weather condition text (diagnostic) |
| 3-Hour Forecast | - | - | Forecast block score (diagnostic, disabled by default) |

### Paddle Score attributes

The `paddle_score` sensor exposes these extra attributes:

- `rating`: GO, CAUTION, or NO_GO
- `activity`: current activity (sup or kayaking)
- `profile`: active scoring profile
- `limiting_factor`: the condition hurting your score the most
- `factors`: individual scores for each weather factor
- `missing_factors`: factors that could not be scored (e.g. water temp without a station)
- `vetoed`: whether a hard veto is active
- `veto_reason`: reason for the veto (e.g. thunderstorm, extreme wind)

### 3-Hour Forecast attributes

The `forecast_3hr` sensor provides these extra attributes:

- `blocks`: array of up to 8 forecast blocks (24 hours), each with score, rating, wind, temperature, UV, precipitation, and start/end times
- `best_block`: the block with the highest score
- `best_score`: the score of the best block
- `hourly_times`: array of hourly timestamps
- `hourly_wind`: array of hourly wind speed values
- `hourly_temp`: array of hourly temperature values
- `hourly_uv`: array of hourly UV index values
- `hourly_precip`: array of hourly precipitation probability values
- All times are in the location's local timezone

---

## Scoring

Seven factors are scored individually using piecewise linear curves matched to your profile, then combined by weighted average:

| Factor | Recreational weight | What it measures |
|--------|-------------------|------------------|
| Wind speed | 30% | Sustained wind, the biggest factor for most paddlers |
| Air quality | 20% | US AQI, matters for extended exertion outdoors |
| Temperature | 15% | Comfort range with penalties for extremes |
| Wind gusts | 10% | Gust intensity above sustained wind |
| UV index | 10% | Sun exposure risk |
| Visibility | 10% | Fog, haze, low-visibility hazards |
| Precipitation | 5% | Rain probability |

Weights are customizable. Profiles provide good defaults: Racing tolerates more wind, Family is stricter across the board.

**Hard vetoes** override the score entirely:
- Thunderstorms (always enforced)
- Extreme wind (profile-dependent threshold)
- Dangerous AQI levels

---

## Dashboard

The integration bundles two custom Lovelace cards and a service action that generates a complete dashboard config for all your locations.

### Cards

**`paddle-score-card`** — The main card for each location. Shows:
- Hero section with paddle score, Go/Caution/No-go rating, and date
- Best time to paddle (filtered to daylight hours, at least 2 hours before sunset)
- Factor grid (wind, AQI, temperature, UV, visibility, precipitation) with score bars
- Tap any factor tile to expand hourly forecasts (sunrise-1h to sunset+1h)
- 3-hour forecast timeline with per-block scores, wind, and temperature

**`paddle-spots-card`** — Multi-location comparison card with color-coded score badges. Useful when you have several spots and want to see at a glance which one is best today.

### Getting the dashboard

1. Go to **Developer Tools > Actions** (may be labeled "Services" in older versions)
2. Search for `paddle_conditions.get_dashboard_yaml`
3. Click **Perform action** — the response contains your complete dashboard config
4. Copy the entire response
5. Go to **Settings > Dashboards > Add Dashboard > From scratch**
6. Open the new dashboard, click the three-dot menu > **Edit Dashboard** > three-dot menu > **Raw configuration editor**
7. Paste the copied config and save

The dashboard is generated from your current locations. If you add or remove a location, run the action again to get an updated config.

---

## Automation examples

### Notification when conditions are GO

```yaml
automation:
  - alias: "Paddle conditions alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.lake_natoma_paddle_score
        above: 70
    action:
      - service: notify.mobile_app
        data:
          title: "Go paddle!"
          message: >
            {{ state_attr('sensor.lake_natoma_paddle_score', 'rating') }} conditions
            at Lake Natoma — Score: {{ states('sensor.lake_natoma_paddle_score') }}%
```

### Template sensor for best location

```yaml
template:
  - sensor:
      - name: "Best Paddle Spot"
        state: >
          {% set spots = [
            states.sensor.lake_natoma_paddle_score,
            states.sensor.lake_clementine_paddle_score
          ] | selectattr('state', 'is_number') | list %}
          {% if spots %}
            {{ spots | sort(attribute='state', reverse=true) | first | attr('object_id') | replace('_paddle_score', '') | replace('_', ' ') | title }}
          {% else %}
            Unknown
          {% endif %}
```

### Wind speed warning

```yaml
automation:
  - alias: "High wind warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.lake_natoma_wind_gusts
        above: 20
    action:
      - service: notify.mobile_app
        data:
          title: "Wind advisory"
          message: "Wind gusts at {{ states('sensor.lake_natoma_wind_gusts') }} mph — not recommended for paddling"
```

---

## Data sources

All APIs are free, public, and need no authentication.

| Source | Data | Required |
|--------|------|----------|
| [Open-Meteo Weather](https://open-meteo.com/) | Wind, temperature, UV, visibility, precipitation, weather codes, 48-hour hourly forecast (local timezone) | Yes |
| [Open-Meteo Air Quality](https://open-meteo.com/) | US AQI, PM2.5, PM10, ozone | Yes |
| [USGS Water Services](https://waterservices.usgs.gov/) | Water temperature, streamflow (CFS) | No, river locations |
| [NOAA CO-OPS](https://tidesandcurrents.noaa.gov/) | Water temperature, tide predictions | No, bay/ocean locations |

Weather and AQI are required for scoring. Without them the integration won't produce a score.

USGS and NOAA are optional. If a station is unavailable, those factors drop out and weights renormalize automatically. All API calls run in parallel, both across data sources and across locations. Failed requests retry with exponential backoff. If APIs are unreachable on startup, the integration loads from cached data instead of blocking.

---

## Known limitations

- **Tide current scoring not yet implemented**: Bay and ocean locations do not yet factor in tidal currents for scoring.
- **Water temperature requires a station ID**: Water temperature data requires a USGS or NOAA station ID configured in the location settings. Not all locations have a nearby station.
- **Open-Meteo accuracy in remote areas**: Open-Meteo provides global coverage but may have reduced accuracy in remote or sparsely instrumented areas.
- **USGS is US-only**: USGS data is available for US waterways only. NOAA data is available for US coastal and Great Lakes stations only.
- **Cloud sync requires a backend**: Cloud sync is an optional feature that requires a separate backend service to be running.
- **Scoring profiles are preset**: Fully custom scoring curve definitions are not yet exposed in the UI. You can adjust weights but not the underlying scoring curves.

---

## Troubleshooting

### No data after setup
- Check that your coordinates are correct (latitude +/-90, longitude +/-180)
- Look in **Settings > System > Logs** for `paddle_conditions` errors
- Open-Meteo may be temporarily down. The integration retries automatically.

### No water temperature data
- You need to configure a USGS or NOAA station ID in the location settings.
- Find USGS stations at [waterdata.usgs.gov](https://waterdata.usgs.gov)
- Find NOAA stations at [tidesandcurrents.noaa.gov](https://tidesandcurrents.noaa.gov)
- Not all stations report all parameters. Check that yours provides the data you expect.

### Sensors showing "unavailable"
- The weather API may be temporarily unreachable. The integration will retry automatically on the next update interval.
- Check **Settings > System > Logs** for details.

### Slow startup after install
- The first launch fetches all data from scratch. Subsequent starts use cached data and are much faster.

### Score seems wrong
- Check `limiting_factor` on the `paddle_score` entity. It tells you which condition is dragging the score down.
- Review your profile weights in **Configure**. The default profile may not match how you paddle.
- Check the Options flow: your scoring weights and profile may not match your activity. Wind speed and air quality have the highest default weights.
- Hard vetoes (thunderstorm, extreme wind) override the calculated score entirely.

### Custom cards not showing
- Go to **Settings > Dashboards > Resources** and verify `paddle-score-card.js` and `paddle-spots-card.js` are listed.
- Try clearing your browser cache.
- Cards register when the integration loads. If they don't show in the card picker, restart HA.
- Check the browser console (F12) for JavaScript errors.

### Cards show "Configuration error" on startup
- This usually means the HA server was too busy to serve the card JavaScript while APIs were timing out. Version 1.0.4 fixed this by refreshing all locations in parallel and falling back to cached data when APIs are slow.
- If you still see it, restart HA. Once the first successful fetch completes, cached data prevents this on future restarts.

### Hourly temperatures seem wrong
- Make sure you're on version 1.0.3 or later. Earlier versions fetched hourly data in UTC, causing temperature/wind values to be offset by your timezone difference.
- After updating, restart HA and wait for the next data refresh.

---

## Removal

To remove the integration:

1. Go to **Settings > Devices & Services**
2. Find "Paddle Conditions"
3. Click the three-dot menu and select **Delete**
4. Cached data files are cleaned up automatically

---

## Contributing

See [CONTRIBUTING.md](https://github.com/FrogStoneMedia/paddle-conditions/blob/main/CONTRIBUTING.md) for development setup, testing, and guidelines.

Quick version:
- Python 3.14+, `pip install -r requirements_test.txt`
- TDD is mandatory. Write failing tests first.
- `pytest tests/ -v` to run the suite
- `ruff check . && ruff format .` for linting
- Commit prefix: `[ha-integration] Brief description`

---

## License

MIT. See [LICENSE](https://github.com/FrogStoneMedia/paddle-conditions/blob/main/LICENSE).
