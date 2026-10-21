// Paddle Factors card: each scoring factor with its reading and sub-score.

import { PaddleLocation, scoreEntities, signatureChanged, DOMAIN } from "../lib/entities.js";
import { formatState } from "../lib/units.js";
import { applyTheme, ratingForScore, ratingVar } from "../lib/theme.js";
import { el, button } from "../lib/dom.js";

const FACTORS = [
  { key: "wind_speed", label: "Wind", sensor: "wind_speed", icon: "mdi:weather-windy" },
  { key: "wind_gusts", label: "Gusts", sensor: "wind_gusts", icon: "mdi:weather-windy-variant" },
  { key: "air_quality", label: "Air quality", sensor: "aqi", icon: "mdi:air-filter" },
  { key: "temperature", label: "Temperature", sensor: "air_temp", icon: "mdi:thermometer" },
  { key: "uv_index", label: "UV index", sensor: "uv_index", icon: "mdi:white-balance-sunny" },
  { key: "visibility", label: "Visibility", sensor: "visibility", icon: "mdi:eye-outline" },
  { key: "precipitation", label: "Rain chance", sensor: "precipitation", icon: "mdi:weather-rainy" },
  { key: "streamflow", label: "Streamflow", sensor: "streamflow", icon: "mdi:waves" },
];

class PaddleFactorsCard extends HTMLElement {
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
      ],
      computeLabel: (s) => ({ entity: "Paddle Score sensor", name: "Title" })[s.name],
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Choose a Paddle Score sensor");
    this._config = config;
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
    return 1 + FACTORS.length;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }

  _render() {
    if (!this._hass || !this._location) return;
    applyTheme(this, this._hass);
    const score = this._location.state("paddle_score");
    const content = [el("h2", { className: "title", text: this._config.name || "Scoring factors" })];
    if (!score) {
      content.push(el("p", { className: "empty", text: `Sensor not found: ${this._config.entity}` }));
    } else {
      const factors = score.attributes?.factors || {};
      const list = el("ul", { className: "factors" });
      for (const f of FACTORS) {
        const sub = factors[f.key];
        if (sub == null) continue;
        const sensorId = this._location.id(f.sensor);
        const value = formatState(this._hass, this._location.state(f.sensor));
        const color = ratingVar(ratingForScore(sub));
        list.append(
          el(
            "li",
            {},
            button(
              {
                className: "factor",
                "aria-label": `${f.label}: ${value}, score ${sub} out of 100. Show details.`,
                onClick: () => sensorId && this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: sensorId } })),
              },
              [
                el("ha-icon", { icon: f.icon, "aria-hidden": "true", style: { color } }),
                el("span", { className: "label", text: f.label }),
                el("span", { className: "value", text: value }),
                el("span", { className: "bar", "aria-hidden": "true" }, el("span", { style: { width: `${sub}%`, background: color } })),
                el("span", { className: "sub", style: { color }, text: String(sub) }),
              ],
            ),
          ),
        );
      }
      content.push(list.children.length ? list : el("p", { className: "empty", text: "No factors scored yet." }));
    }
    this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, content));
  }
}

const STYLES = `
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  .title { margin: 0; padding: 16px 16px 4px; font-size: 16px; font-weight: 500; }
  .factors { margin: 0; padding: 4px 8px 12px; list-style: none; }
  .factor { display: grid; grid-template-columns: 24px 1fr auto; grid-template-areas: "icon label value" "icon bar sub";
    align-items: center; gap: 2px 10px; width: 100%; min-height: 44px; padding: 8px; border: 0; border-radius: 8px;
    background: none; color: inherit; font: inherit; text-align: left; cursor: pointer; }
  .factor:hover { background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .factor:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 1px; }
  ha-icon { grid-area: icon; --mdc-icon-size: 22px; }
  .label { grid-area: label; font-size: 14px; }
  .value { grid-area: value; font-size: 14px; color: var(--secondary-text-color); }
  .bar { grid-area: bar; height: 6px; border-radius: 3px; overflow: hidden; background: var(--divider-color, rgba(127,127,127,.3)); }
  .bar > span { display: block; height: 100%; }
  .sub { grid-area: sub; font-size: 13px; font-weight: 700; text-align: right; }
  .empty { margin: 0; padding: 8px 16px 16px; color: var(--secondary-text-color); }
`;

if (!customElements.get("paddle-factors-card")) customElements.define("paddle-factors-card", PaddleFactorsCard);
export { PaddleFactorsCard };
