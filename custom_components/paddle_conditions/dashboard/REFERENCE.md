# Dashboard design reference

## Design lineage

The bundled dashboard cards replace external HACS card dependencies while keeping the layout and UX from the original Mushroom-based dashboard.

### Pattern references (no code copied)

- **Mushroom Cards**: inspired the card layout patterns (score hero card, chip navigation, factor breakdown rows)
- **ApexCharts Card**: informed the forecast table layout
- **card-mod**: the original dashboard used card-mod for custom styling; the bundled cards use Shadow DOM with CSS custom properties instead

### Architecture

- Vanilla JavaScript web components (no Lit dependency)
- Shadow DOM for style encapsulation
- esbuild for bundling (single ES module output)
- HA theme integration via CSS custom properties

### Legacy dashboard

The original Mushroom-based dashboard is at `legacy/paddle-mushroom.yaml` for reference. It requires Mushroom, ApexCharts, and card-mod from HACS. It is no longer maintained.
