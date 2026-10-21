// Paddle History card: long-term score statistics from the recorder.

import { ensureChartReady, Chart } from "../charts/chart-loader.js";
import { computeStats, getThresholdGridColor, resolveHAColor } from "../charts/chart-utils.js";
import { PaddleLocation, scoreEntities, DOMAIN } from "../lib/entities.js";
import { applyTheme, ratingForScore, ratingVar, seriesColors } from "../lib/theme.js";
import { dayKey, formatDateTime, formatDay, weekday } from "../lib/time.js";
import { el, button, prefersReducedMotion, SR_ONLY_CSS } from "../lib/dom.js";
import { dataTable } from "../lib/table.js";

const RANGES = {
  "7d": { days: 7, period: "hour", label: "7 days" },
  "30d": { days: 30, period: "day", label: "30 days" },
  "90d": { days: 90, period: "day", label: "90 days" },
};
const CACHE_TTL_MS = 15 * 60 * 1000;

class PaddleHistoryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._cache = new Map(); // "entity|range" -> { promise, fetchedAt, lastUpdated }
    this._chart = null;
    this._gen = 0; // Bumped by every render and disconnect; stale async work checks it.
  }

  static getStubConfig(hass) {
    return { entity: scoreEntities(hass)[0] || "" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: [{ integration: DOMAIN, domain: "sensor" }] } } },
        { name: "name", selector: { text: {} } },
        { name: "default_range", selector: { select: { mode: "dropdown", options: Object.entries(RANGES).map(([value, r]) => ({ value, label: r.label })) } } },
        { name: "show_stats", selector: { boolean: {} } },
      ],
      computeLabel: (s) => ({ entity: "Paddle Score sensor", name: "Title", default_range: "Range", show_stats: "Show summary" })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Choose a Paddle Score sensor");
    this._config = { show_stats: true, ...config };
    this._range = RANGES[config.default_range] ? config.default_range : "7d";
    this._scoreId = null;
    this._shown = null;
    if (this._hass) this._sync();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) this._sync();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 5, min_rows: 4 };
  }

  disconnectedCallback() {
    this._gen++;
    clearTimeout(this._retry);
    this._chart?.destroy();
    this._chart = null;
    this._shown = null; // Render again on reconnect: Chart.js needs an attached canvas.
  }

  connectedCallback() {
    if (this._hass && this._config) this._sync();
  }

  /**
   * Render when the score updates, the range or theme changes, or the cached
   * result has expired. Rendering only while attached keeps Chart.js happy.
   */
  _sync() {
    if (!this.isConnected) return;
    if (!this._scoreId || this._hass.entities !== this._entitiesRef) {
      this._entitiesRef = this._hass.entities;
      this._scoreId = new PaddleLocation(this._hass, this._config.entity).id("paddle_score") || this._config.entity;
    }
    const state = this._hass.states[this._scoreId];
    const bucket = Math.floor(Date.now() / CACHE_TTL_MS);
    const key = `${this._scoreId}|${this._range}|${state?.last_updated}|${Boolean(this._hass.themes?.darkMode)}|${bucket}`;
    if (key === this._shown) return;
    this._shown = key;
    this._render(state);
  }

  _fetch(scoreId, rangeKey, lastUpdated) {
    const key = `${scoreId}|${rangeKey}`;
    const hit = this._cache.get(key);
    if (hit && Date.now() - hit.fetchedAt < CACHE_TTL_MS && hit.lastUpdated === lastUpdated) return hit.promise;
    const range = RANGES[rangeKey];
    const end = new Date();
    const promise = this._hass
      .callWS({
        type: "recorder/statistics_during_period",
        statistic_ids: [scoreId],
        period: range.period,
        start_time: new Date(end.getTime() - range.days * 86400000).toISOString(),
        end_time: end.toISOString(),
        types: ["mean"],
      })
      .then((result) =>
        (result[scoreId] || [])
          .filter((s) => s.mean != null)
          .map((s) => ({ timestamp: new Date(s.start).toISOString(), value: Math.round(s.mean) })),
      )
      .catch((err) => {
        this._cache.delete(key);
        throw err;
      });
    this._cache.set(key, { promise, fetchedAt: Date.now(), lastUpdated });
    return promise;
  }

  async _render(state) {
    const gen = ++this._gen;
    clearTimeout(this._retry);
    applyTheme(this, this._hass);
    const hass = this._hass;
    const scoreId = this._scoreId;
    const rangeKey = this._range;
    const range = RANGES[rangeKey];
    const status = el("p", { className: "status", role: "status", "aria-live": "polite", text: state ? `Loading ${range.label} of history\u2026` : "" });
    const chartBox = el("div", { className: "chart" }, el("div", { className: "skeleton", "aria-hidden": "true" }));
    const tableSlot = el("div");
    const stats = el("div");
    const ranges = el(
      "div",
      { className: "ranges", role: "group", "aria-label": "History range" },
      Object.entries(RANGES).map(([key, r]) =>
        button(
          {
            className: "range",
            "data-range": key,
            "aria-pressed": String(key === rangeKey),
            onClick: () => {
              this._range = key;
              this._sync();
              this.shadowRoot.querySelector(`.range[data-range="${key}"]`)?.focus();
            },
          },
          r.label,
        ),
      ),
    );
    const header = el("div", { className: "head" }, [el("h2", { className: "title", text: this._config.name || "Score history" }), ranges]);
    this._chart?.destroy();
    this._chart = null;

    if (!state) {
      status.textContent = `Sensor not found: ${this._config.entity}`;
      this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, [header, status]));
      return;
    }
    this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, [header, chartBox, stats, status, tableSlot]));

    let data;
    try {
      data = await this._fetch(scoreId, rangeKey, state.last_updated);
    } catch {
      if (gen !== this._gen) return;
      chartBox.replaceChildren();
      status.textContent = "Could not load history. Retrying in a minute; check that the recorder is enabled.";
      this._retry = setTimeout(() => {
        this._shown = null;
        if (this._hass) this._sync();
      }, 60000);
      return;
    }
    if (gen !== this._gen || !this.isConnected) return; // A newer render owns the card.

    chartBox.replaceChildren();
    if (!data.length) {
      status.textContent = `No history for the last ${range.label} yet.`;
      return;
    }
    const s = computeStats(data, (d) => dayKey(hass, d), (d) => weekday(hass, d));
    status.textContent = `${range.label}: average ${s.avg}, best ${s.best}, ${s.goDays} Go days.`;
    if (this._config.show_stats) stats.replaceChildren(this._stats(s));
    const label = range.period === "hour" ? (d) => formatDateTime(hass, d) : (d) => formatDay(hass, d);
    tableSlot.replaceChildren(
      dataTable(`Paddle score, ${range.label}`, ["Time", "Score"], data.map((d) => [label(new Date(d.timestamp)), String(d.value)])),
    );

    const canvas = el("canvas", { "aria-hidden": "true" });
    chartBox.append(canvas);
    ensureChartReady();
    const text = resolveHAColor(this, "--secondary-text-color", "#757575");
    const color = seriesColors(hass).score;
    this._chart = new Chart(canvas, {
      type: "line",
      data: {
        labels: data.map((d) => d.timestamp),
        datasets: [{ label: "Score", data: data.map((d) => d.value), borderColor: color, backgroundColor: "rgba(67,160,71,.12)", fill: true, tension: 0.3, pointRadius: 0 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: prefersReducedMotion() ? false : { duration: 300 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { title: (items) => formatDateTime(hass, new Date(items[0].parsed.x)) } } },
        scales: {
          x: { type: "time", time: { unit: range.period === "hour" ? "day" : "week" }, grid: { display: false }, ticks: { color: text, maxTicksLimit: 7, callback: (v) => formatDay(hass, new Date(v)) } },
          y: { min: 0, max: 100, grid: { color: (ctx) => getThresholdGridColor(ctx.tick.value) }, ticks: { color: text } },
        },
      },
    });
  }

  _stats(s) {
    const item = (label, value, color) => el("div", { className: "stat" }, [el("dt", { text: label }), el("dd", { style: color ? { color } : null, text: value })]);
    return el("dl", { className: "stats" }, [
      item("Average", String(s.avg), ratingVar(ratingForScore(s.avg))),
      item("Best", String(s.best), ratingVar(ratingForScore(s.best))),
      item("Go days", String(s.goDays)),
      item("Best weekday", s.bestDay),
    ]);
  }
}

const STYLES = `
  ${SR_ONLY_CSS}
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  ha-card { display: flex; flex-direction: column; height: 100%; }
  .head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px; padding: 16px 16px 8px; }
  .title { margin: 0; font-size: 16px; font-weight: 500; }
  .ranges { display: flex; gap: 6px; }
  .range { min-height: 32px; padding: 4px 12px; border-radius: 16px; border: 1px solid var(--divider-color); background: none; color: var(--primary-text-color); font: inherit; font-size: 13px; cursor: pointer; }
  /* Selected: heavier border and weight in the text colour, so it doesn't depend on the theme's primary colour for contrast. */
  .range[aria-pressed="true"] { border: 2px solid var(--primary-color); font-weight: 700; }
  .range:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .chart { position: relative; flex: 1; min-height: 160px; padding: 0 12px; }
  .skeleton { height: 160px; border-radius: 8px; background: var(--secondary-background-color, rgba(127,127,127,.15)); animation: pulse 1.5s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: .5; } }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 8px 12px 0; }
  .stat { text-align: center; }
  .stat dt { font-size: 12px; color: var(--secondary-text-color); }
  .stat dd { margin: 0; font-size: 18px; font-weight: 700; }
  .status { margin: 8px 16px 16px; font-size: 13px; color: var(--secondary-text-color); }
  @media (prefers-reduced-motion: reduce) { .skeleton { animation: none; } }
`;

if (!customElements.get("paddle-history-card")) customElements.define("paddle-history-card", PaddleHistoryCard);
export { PaddleHistoryCard };
