import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";

class PaddleForecastEditor extends HTMLElement {
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

    // Max blocks number input row
    const blocksRow = document.createElement("div");
    blocksRow.className = "editor-row";
    const blocksLabel = document.createElement("label");
    blocksLabel.textContent = "Max Blocks";
    blocksRow.appendChild(blocksLabel);
    const blocksInput = document.createElement("input");
    blocksInput.type = "number";
    blocksInput.min = "1";
    blocksInput.max = "24";
    blocksInput.value = this._config.max_blocks ?? 8;
    blocksInput.addEventListener("input", (ev) => {
      const val = parseInt(ev.target.value, 10);
      if (!isNaN(val) && val >= 1 && val <= 24) {
        this._config = { ...this._config, max_blocks: val };
        fireConfigChanged(this, this._config);
      }
    });
    blocksRow.appendChild(blocksInput);
    container.appendChild(blocksRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-forecast-editor", PaddleForecastEditor);
