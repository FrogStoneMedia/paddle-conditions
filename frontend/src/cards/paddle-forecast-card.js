// Paddle Forecast card: the next 24 hours in 3-hour blocks, as a table.

import { PaddleLocation, scoreEntities, signatureChanged, DOMAIN } from "../lib/entities.js";
import { convert, displayUnit } from "../lib/units.js";
import { applyTheme, normalizeRating, ratingVar, RATING_TEXT } from "../lib/theme.js";
import { bestBlock, daylightWindow, recommendableBlocks } from "../lib/daylight.js";
import { dayLabel, formatTime, sameDay } from "../lib/time.js";
import { el } from "../lib/dom.js";

class PaddleForecastCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  static getStubConfig(hass) {
    return { entity: scoreEntities(hass)[0] || "" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", required: true, selector: { entity: { filter: [{ integration: DOMAIN, domain: "sensor" }] } } },
        { name: "name", selector: { text: {} } },
        { name: "max_blocks", selector: { number: { min: 1, max: 8, mode: "box" } } },
      ],
      computeLabel: (s) => ({ entity: "Paddle Score sensor", name: "Title", max_blocks: "Blocks to show" })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Choose a Paddle Score sensor");
    this._config = { max_blocks: 8, ...config };
    this._location = null;
    this._signature = null;
    if (this._hass) this.hass = this._hass; // Rebuild the location and render now.
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    if (!this._location || this._location.hass.entities !== hass.entities) this._location = new PaddleLocation(hass, this._config.entity);
    this._location.hass = hass;
    const sig = this._location.signature(hass);
    if (!signatureChanged(this._signature, sig) && this._dark === Boolean(hass.themes?.darkMode)) return;
    this._signature = sig;
    this._dark = Boolean(hass.themes?.darkMode);
    this._render();
  }

  getCardSize() {
    return 2 + Math.ceil(this._config.max_blocks / 2);
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _render() {
    if (!this._hass || !this._location) return;
    applyTheme(this, this._hass);
    const hass = this._hass;
    const forecast = this._location.state("forecast_3hr");
    const blocks = (forecast?.attributes?.blocks || []).slice(0, this._config.max_blocks);
    const content = [el("h2", { className: "title", text: this._config.name || "Paddle forecast" })];

    if (!blocks.length) {
      content.push(el("p", { className: "empty", text: forecast ? "No forecast yet." : "Enable the 3-Hour Forecast sensor for this location." }));
    } else {
      const window = daylightWindow(forecast, hass.states["sun.sun"]);
      const best = bestBlock(recommendableBlocks(blocks, window));
      const speedUnit = displayUnit(this._location.state("wind_speed"), "speed");
      const tempUnit = displayUnit(this._location.state("air_temp"), "temperature");
      const when = (iso) => {
        const d = new Date(iso);
        return sameDay(hass, d, new Date()) ? formatTime(hass, d) : `${dayLabel(hass, d)} ${formatTime(hass, d)}`;
      };
      if (best) {
        content.push(el("p", { className: "best" }, [el("ha-icon", { icon: "mdi:star", "aria-hidden": "true" }), `Best window: ${when(best.start)}, score ${best.score}`]));
      }
      const rows = blocks.map((b) => {
        const rating = normalizeRating(b.rating);
        const wind = convert(b.wind_mph, "speed", speedUnit);
        const temp = convert(b.temp_f, "temperature", tempUnit);
        const isBest = best && b.start === best.start;
        return el("tr", { className: isBest ? "best-row" : null }, [
          el("th", { scope: "row" }, [when(b.start), isBest ? el("span", { className: "sr-only", text: " (best window)" }) : null]),
          el("td", {}, el("span", { className: "score", style: { color: ratingVar(rating) }, text: String(b.score) })),
          el("td", { text: RATING_TEXT[rating] }),
          el("td", { text: wind == null ? "—" : `${Math.round(wind)} ${speedUnit}` }),
          el("td", { text: temp == null ? "—" : `${Math.round(temp)}${tempUnit}` }),
          el("td", { text: b.precip_pct == null ? "—" : `${b.precip_pct}%` }),
        ]);
      });
      content.push(
        el("div", { className: "scroll" }, el("table", {}, [
          el("caption", { className: "sr-only", text: "Paddle conditions, 3-hour blocks" }),
          el("thead", {}, el("tr", {}, ["Time", "Score", "Rating", "Wind", "Temp", "Rain"].map((h) => el("th", { scope: "col", text: h })))),
          el("tbody", {}, rows),
        ])),
      );
    }
    this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, content));
  }
}

const STYLES = `
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  .sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .title { margin: 0; padding: 16px 16px 4px; font-size: 16px; font-weight: 500; }
  .best { display: flex; align-items: center; gap: 6px; margin: 4px 16px 8px; font-size: 14px; font-weight: 600; }
  .best ha-icon { --mdc-icon-size: 18px; color: var(--pc-go); }
  .scroll { overflow-x: auto; padding: 0 8px 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 8px; text-align: left; white-space: nowrap; }
  thead th { font-size: 12px; font-weight: 600; color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); }
  tbody th { font-weight: 400; }
  tbody tr + tr { border-top: 1px solid var(--divider-color); }
  .best-row { background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .score { font-weight: 700; }
  .empty { margin: 0; padding: 8px 16px 16px; color: var(--secondary-text-color); }
`;

if (!customElements.get("paddle-forecast-card")) customElements.define("paddle-forecast-card", PaddleForecastCard);
export { PaddleForecastCard };
