// Paddle Spots card: every location's score and rating at a glance.

import { scoreEntities, DOMAIN } from "../lib/entities.js";
import { numericState } from "../lib/units.js";
import { applyTheme, fillVar, normalizeRating, RATING_TEXT } from "../lib/theme.js";
import { el, button } from "../lib/dom.js";

class PaddleSpotsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: "entities",
          selector: { entity: { multiple: true, filter: [{ integration: DOMAIN, domain: "sensor" }] } },
        },
      ],
      computeLabel: (s) => (s.name === "entities" ? "Paddle Score sensors (leave empty for all)" : undefined),
    };
  }

  setConfig(config) {
    this._config = { ...config };
    this._last = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const ids = this._ids();
    const states = ids.map((id) => hass.states[id]);
    if (this._last && this._last.length === states.length && states.every((s, i) => s === this._last[i]) && this._dark === Boolean(hass.themes?.darkMode)) return;
    this._last = states;
    this._dark = Boolean(hass.themes?.darkMode);
    this._render();
  }

  getCardSize() {
    return 2;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 3, rows: "auto" };
  }

  _ids() {
    return this._config?.entities?.length ? this._config.entities : scoreEntities(this._hass);
  }

  _render() {
    if (!this._hass || !this._config) return;
    applyTheme(this, this._hass);
    const list = el("ul", { className: "spots", "aria-label": "Paddle spots" });
    for (const id of this._ids()) {
      const state = this._hass.states[id];
      if (!state) continue;
      const score = numericState(state);
      const rating = score == null ? "NONE" : normalizeRating(state.attributes?.rating);
      const name = (state.attributes?.friendly_name || id).replace(/ Paddle Score$/i, "");
      list.append(
        el(
          "li",
          {},
          button(
            {
              className: "spot",
              style: { background: fillVar(rating) },
              "aria-label": `${name}: ${score == null ? "unavailable" : `${Math.round(score)} out of 100`}, ${RATING_TEXT[rating]}. Show details.`,
              onClick: () => this.dispatchEvent(new CustomEvent("hass-more-info", { bubbles: true, composed: true, detail: { entityId: id } })),
            },
            [
              el("span", { className: "score", text: score == null ? "—" : String(Math.round(score)) }),
              el("span", { className: "rating", text: RATING_TEXT[rating] }),
              el("span", { className: "name", text: name }),
            ],
          ),
        ),
      );
    }
    const content = list.children.length ? list : el("p", { className: "empty", text: "No Paddle Conditions locations yet." });
    this.shadowRoot.replaceChildren(el("style", { text: STYLES }), el("ha-card", {}, content));
  }
}

const STYLES = `
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  .spots { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 12px; list-style: none; }
  .spots > li { flex: 1 1 110px; }
  .spot { display: flex; flex-direction: column; align-items: center; gap: 2px; width: 100%; min-height: 44px; padding: 12px 8px;
    border: 0; border-radius: 10px; color: #fff; font: inherit; text-align: center; cursor: pointer; }
  .spot:focus-visible { outline: 3px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
  .score { font-size: 28px; font-weight: 700; line-height: 1; }
  .rating { font-size: 12px; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; }
  .name { font-size: 13px; }
  .empty { margin: 0; padding: 16px; color: var(--secondary-text-color); }
`;

if (!customElements.get("paddle-spots-card")) customElements.define("paddle-spots-card", PaddleSpotsCard);

export { PaddleSpotsCard };
