import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";
import { FACTOR_META } from "../utils.js";

const FACTOR_KEYS = Object.keys(FACTOR_META);

class PaddleFactorsEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
  }

  setConfig(config) {
    this._config = { ...config };
    if (this._hass) {
      this._render();
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _clearShadowRoot() {
    while (this.shadowRoot.firstChild) {
      this.shadowRoot.removeChild(this.shadowRoot.firstChild);
    }
  }

  _render() {
    const root = this.shadowRoot;
    this._clearShadowRoot();

    const style = document.createElement("style");
    style.textContent = EDITOR_STYLES + `
      .checkbox-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
      .checkbox-row label { cursor: pointer; }
    `;
    root.appendChild(style);

    const container = document.createElement("div");

    // Entity picker row
    const entityRow = document.createElement("div");
    entityRow.className = "editor-row";
    const entityLabel = document.createElement("label");
    entityLabel.textContent = "Entity";
    entityRow.appendChild(entityLabel);
    const picker = document.createElement("ha-entity-picker");
    picker.hass = this._hass;
    picker.value = this._config.entity || "";
    picker.includeDomains = ["sensor"];
    picker.addEventListener("value-changed", (ev) => {
      this._config = { ...this._config, entity: ev.detail.value };
      fireConfigChanged(this, this._config);
    });
    entityRow.appendChild(picker);
    container.appendChild(entityRow);

    // Show factors heading
    const heading = document.createElement("div");
    heading.style.cssText = "font-weight: 500; margin-bottom: 8px; margin-top: 8px;";
    heading.textContent = "Show Factors";
    container.appendChild(heading);

    // Default: all factors shown
    const showFactors = this._config.show_factors || FACTOR_KEYS;

    // Checkbox for each factor
    for (const key of FACTOR_KEYS) {
      const row = document.createElement("div");
      row.className = "checkbox-row";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.id = `factor-${key}`;
      checkbox.checked = showFactors.includes(key);
      checkbox.addEventListener("change", () => {
        this._onFactorChange();
      });

      const label = document.createElement("label");
      label.setAttribute("for", `factor-${key}`);
      label.textContent = FACTOR_META[key].label;

      row.appendChild(checkbox);
      row.appendChild(label);
      container.appendChild(row);
    }

    root.appendChild(container);
  }

  _onFactorChange() {
    const checked = [];
    for (const key of FACTOR_KEYS) {
      const cb = this.shadowRoot.querySelector(`#factor-${key}`);
      if (cb && cb.checked) {
        checked.push(key);
      }
    }
    this._config = { ...this._config, show_factors: checked };
    fireConfigChanged(this, this._config);
  }
}

customElements.define("paddle-factors-editor", PaddleFactorsEditor);
