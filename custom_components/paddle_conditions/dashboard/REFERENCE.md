# Dashboard Design Reference

## Design Lineage

The bundled dashboard cards were designed to replace external HACS card dependencies while preserving the dashboard layout and user experience established by the original Mushroom-based dashboard.

### Pattern References (no code copied)

- **Mushroom Cards** — Inspired the clean card layout patterns (score hero card, chip navigation, factor breakdown rows)
- **ApexCharts Card** — Informed the forecast table layout; Chart.js-based replacements are planned for v2
- **card-mod** — The original dashboard used card-mod for custom styling; the bundled cards use Shadow DOM with CSS custom properties for HA theme integration instead

### Architecture

- Vanilla JavaScript web components (no Lit dependency)
- Shadow DOM for style encapsulation
- esbuild for bundling (single ES module output)
- HA theme variable integration via CSS custom properties

### Legacy Dashboard

The original Mushroom-based dashboard is preserved at `legacy/paddle-mushroom.yaml` for reference. It requires external HACS installations (Mushroom, ApexCharts, card-mod) and is no longer actively maintained.
