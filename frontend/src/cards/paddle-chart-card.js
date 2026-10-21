// Paddle Chart card: score over the next 24 hours with optional wind,
// temperature, UV and rain layers (Chart.js).

import { ensureChartReady, Chart } from "../charts/chart-loader.js";
import { getThresholdGridColor, createScoreGradient, resolveHAColor } from "../charts/chart-utils.js";
import { PaddleLocation, scoreEntities, signatureChanged, DOMAIN } from "../lib/entities.js";
import { convertSeries, displayUnit } from "../lib/units.js";
import { applyTheme, onSeriesFill, seriesColors } from "../lib/theme.js";
import { formatHour } from "../lib/time.js";
import { el, button, prefersReducedMotion, SR_ONLY_CSS } from "../lib/dom.js";
import { dataTable } from "../lib/table.js";

// Colours come from the theme's series palette (>= 3:1 on the plot, and the
// pressed toggle's text colour is chosen for 4.5:1 on top of them).
const LAYERS = {
  wind: { label: "Wind", series: "wind" },
  temp: { label: "Temp", series: "temp" },
  uv: { label: "UV", series: "uv" },
  rain: { label: "Rain", series: "flow" },
};
const HOURS = 24;

class PaddleChartCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._chart = null;
  }

  static getStubConfig(hass) {
    return { entity: scoreEntities(hass)[0] || "" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: [{ integration: DOMAIN, domain: "sensor" }] } } },
        { name: "name", selector: { text: {} } },
        {
          name: "default_metrics",
          selector: { select: { multiple: true, mode: "list", options: Object.entries(LAYERS).map(([value, l]) => ({ value, label: l.label })) } },
        },
      ],
      computeLabel: (s) => ({ entity: "Paddle Score sensor", name: "Title", default_metrics: "Layers shown by default" })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Choose a Paddle Score sensor");
    this._config = config;
    this._active = new Set((config.default_metrics || []).filter((k) => k in LAYERS));
    this._location = null;
    this._signature = null;
    this._chart?.destroy();
    this._chart = null;
    this._built = false;
    if (this._hass) this.hass = this._hass; // Rebuild the location and render now.
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    if (!this._location || this._location.hass.entities !== hass.entities) this._location = new PaddleLocation(hass, this._config.entity);
    this._location.hass = hass;
    const sig = this._location.signature(hass);
    const dark = Boolean(hass.themes?.darkMode);
    if (!signatureChanged(this._signature, sig) && dark === this._dark) return;
    if (dark !== this._dark && this._built) this._restyle();
    this._signature = sig;
    this._dark = dark;
    this._update();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 5, min_rows: 4 };
  }

  disconnectedCallback() {
    this._chart?.destroy();
    this._chart = null;
    this._built = false;
  }

  connectedCallback() {
    if (this._hass && this._config && !this._built) {
      this._signature = null;
      this._update();
    }
  }

  _series() {
    const forecast = this._location.state("forecast_3hr");
    const a = forecast?.attributes || {};
    const n = Math.min(HOURS, a.hourly_times?.length || 0);
    const times = (a.hourly_times || []).slice(0, n).map((t) => new Date(t));
    const blocks = a.blocks || [];
    const score = times.map((t) => blocks.find((b) => t >= new Date(b.start) && t < new Date(b.end))?.score ?? null);
    const speedUnit = displayUnit(this._location.state("wind_speed"), "speed");
    const tempUnit = displayUnit(this._location.state("air_temp"), "temperature");
    return {
      forecast,
      times,
      score,
      units: { wind: speedUnit, temp: tempUnit, uv: "", rain: "%" },
      wind: convertSeries((a.hourly_wind || []).slice(0, n), "speed", speedUnit),
      temp: convertSeries((a.hourly_temp || []).slice(0, n), "temperature", tempUnit),
      uv: (a.hourly_uv || []).slice(0, n),
      rain: (a.hourly_precip || []).slice(0, n),
    };
  }

  _update() {
    if (!this._hass || !this._location) return;
    applyTheme(this, this._hass);
    const s = this._series();
    if (!s.times.length) {
      this._chart?.destroy();
      this._chart = null;
      this._built = false;
      const msg = s.forecast ? "No forecast yet." : "Enable the 3-Hour Forecast sensor for this location.";
      this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, [this._title(), el("p", { className: "empty", text: msg })]));
      return;
    }
    if (!this._built) {
      // Chart.js measures and observes its container, so build once attached.
      if (!this.isConnected) return;
      this._build();
    }
    this._renderTable(s);
    this._applyData(s);
  }

  _title() {
    return el("h2", { className: "title", text: this._config.name || "Paddle forecast" });
  }

  _build() {
    const toggles = el("div", { className: "layers", role: "group", "aria-label": "Chart layers" });
    for (const [key, layer] of Object.entries(LAYERS)) {
      toggles.append(
        button(
          {
            className: "layer",
            "aria-pressed": String(this._active.has(key)),
            "data-layer": key,
            onClick: (e) => {
              if (this._active.has(key)) this._active.delete(key);
              else this._active.add(key);
              e.currentTarget.setAttribute("aria-pressed", String(this._active.has(key)));
              this._applyData(this._series());
              this._renderTable(this._series());
            },
          },
          layer.label,
        ),
      );
    }
    this._canvas = el("canvas", { "aria-hidden": "true" });
    this._tableSlot = el("div");
    this._status = el("p", { className: "sr-only", "aria-live": "polite" });
    this.shadowRoot.replaceChildren(
      el("style", { text: STYLES }),
      el("ha-card", {}, [this._title(), toggles, el("div", { className: "chart" }, this._canvas), this._tableSlot, this._status]),
    );
    ensureChartReady();
    const text = resolveHAColor(this, "--secondary-text-color", "#757575");
    this._restyleToggles();
    this._chart = new Chart(this._canvas, {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: prefersReducedMotion() ? false : { duration: 300 },
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => formatHour(this._hass, new Date(items[0].parsed.x)) } } },
        scales: {
          x: { type: "time", time: { unit: "hour" }, grid: { display: false }, ticks: { color: text, maxTicksLimit: 6, callback: (v) => formatHour(this._hass, new Date(v)) } },
          y: { position: "left", min: 0, max: 100, title: { display: true, text: "Score", color: text }, grid: { color: (ctx) => getThresholdGridColor(ctx.tick.value) }, ticks: { color: text } },
          y1: { position: "right", display: false, grid: { display: false }, ticks: { color: text } },
        },
      },
    });
    this._built = true;
  }

  /** Theme changed: recolour toggles and axes in place. */
  _restyle() {
    this._restyleToggles();
    if (!this._chart) return;
    const text = resolveHAColor(this, "--secondary-text-color", "#757575");
    for (const axis of ["x", "y", "y1"]) this._chart.options.scales[axis].ticks.color = text;
    this._chart.options.scales.y.title.color = text;
  }

  _restyleToggles() {
    const colors = seriesColors(this._hass);
    for (const b of this.shadowRoot.querySelectorAll(".layer")) {
      b.style.setProperty("--layer", colors[LAYERS[b.dataset.layer].series]);
      b.style.setProperty("--layer-text", onSeriesFill(this._hass));
    }
  }

  _applyData(s) {
    if (!this._chart) return;
    const datasets = [
      { label: "Score", data: s.score, borderColor: seriesColors(this._hass).score, backgroundColor: (ctx) => createScoreGradient(ctx), fill: true, tension: 0.3, pointRadius: 0, yAxisID: "y", stepped: true },
    ];
    for (const key of this._active) {
      datasets.push({
        label: `${LAYERS[key].label}${s.units[key] ? ` (${s.units[key]})` : ""}`,
        data: s[key],
        borderColor: seriesColors(this._hass)[LAYERS[key].series],
        borderDash: [6, 3],
        fill: false,
        tension: 0.3,
        pointRadius: 0,
        yAxisID: "y1",
      });
    }
    this._chart.data.labels = s.times;
    this._chart.data.datasets = datasets;
    this._chart.options.scales.y1.display = this._active.size > 0;
    this._chart.update(prefersReducedMotion() ? "none" : undefined);
    const best = s.score.reduce((b, v, i) => (v != null && (b == null || v > s.score[b]) ? i : b), null);
    this._status.textContent = best == null ? "" : `Best score ${s.score[best]} at ${formatHour(this._hass, s.times[best])}.`;
  }

  _renderTable(s) {
    const keys = [...this._active];
    const fmt = (key, v) => (v == null ? "—" : `${Math.round(v)}${s.units[key] && key !== "temp" ? ` ${s.units[key]}` : s.units[key]}`);
    const headers = ["Time", "Score", ...keys.map((k) => LAYERS[k].label)];
    const rows = s.times.map((t, i) => [formatHour(this._hass, t), s.score[i] == null ? "—" : String(s.score[i]), ...keys.map((k) => fmt(k, s[k][i]))]);
    this._tableSlot.replaceChildren(dataTable("Paddle forecast, hourly", headers, rows));
  }
}

const STYLES = `
  ${SR_ONLY_CSS}
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  ha-card { display: flex; flex-direction: column; height: 100%; }
  .title { margin: 0; padding: 16px 16px 8px; font-size: 16px; font-weight: 500; }
  .layers { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 16px 8px; }
  .layer { min-height: 32px; padding: 4px 12px; border-radius: 16px; border: 2px solid var(--layer); background: none; color: var(--primary-text-color); font: inherit; font-size: 13px; cursor: pointer; }
  .layer[aria-pressed="true"] { background: var(--layer); color: var(--layer-text); }
  .layer:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .chart { position: relative; flex: 1; min-height: 180px; padding: 0 12px 12px; }
  .empty { margin: 0; padding: 8px 16px 16px; color: var(--secondary-text-color); }
`;

if (!customElements.get("paddle-chart-card")) customElements.define("paddle-chart-card", PaddleChartCard);
export { PaddleChartCard };
