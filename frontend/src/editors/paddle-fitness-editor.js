import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";

class PaddleFitnessEditor extends HTMLElement {
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
    style.textContent = EDITOR_STYLES;
    root.appendChild(style);

    const container = document.createElement("div");

    // Entity picker row (optional)
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

    // Monthly goal number input row
    const goalRow = document.createElement("div");
    goalRow.className = "editor-row";
    const goalLabel = document.createElement("label");
    goalLabel.textContent = "Monthly Goal";
    goalRow.appendChild(goalLabel);
    const goalInput = document.createElement("input");
    goalInput.type = "number";
    goalInput.min = "1";
    goalInput.max = "100";
    goalInput.value = this._config.monthly_goal ?? 12;
    goalInput.addEventListener("input", (ev) => {
      const val = parseInt(ev.target.value, 10);
      if (!isNaN(val) && val >= 1 && val <= 100) {
        this._config = { ...this._config, monthly_goal: val };
        fireConfigChanged(this, this._config);
      }
    });
    goalRow.appendChild(goalInput);
    container.appendChild(goalRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-fitness-editor", PaddleFitnessEditor);
