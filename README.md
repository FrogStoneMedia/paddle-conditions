# Paddle Conditions

A Home Assistant custom integration for paddle sport conditions monitoring. Get real-time weather, water, and air quality data for your favorite SUP and kayaking spots with a single-glance Go / Caution / No-go score.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu > Custom repositories
3. Add `FrogStoneMedia/paddle-conditions` as an Integration
4. Install "Paddle Conditions"
5. Restart Home Assistant

### Manual

Copy `custom_components/paddle_conditions/` to your HA `custom_components/` directory.

## Quick Start

1. Go to Settings > Devices & Services > Add Integration
2. Search for "Paddle Conditions" and confirm
3. Click the integration card > Add Entry > add your first paddle location
4. Import the bundled dashboard: Settings > Dashboards > Add > Import from `custom_components/paddle_conditions/dashboard/paddle.yaml`

### Dashboard Setup

The integration includes bundled custom Lovelace cards — **no external HACS card dependencies required**. Cards are automatically registered when the integration loads.

Available cards:
- **paddle-score-card** — Hero score with Go/Caution/No-go rating
- **paddle-factors-card** — Factor breakdown with progress bars
- **paddle-chips-card** — Location navigation chips
- **paddle-forecast-card** — 3-hour forecast table with best window
- **paddle-fitness-card** — Session tracking (coming soon)

## Scoring

See [docs/SCORING.md](docs/SCORING.md) for how the Paddle Score works and how to customize it.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT — see [LICENSE](LICENSE).
