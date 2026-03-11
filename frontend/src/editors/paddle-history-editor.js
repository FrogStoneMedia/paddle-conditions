import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";

class PaddleHistoryEditor extends HTMLElement {
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

  _render() {
    const root = this.shadowRoot;
    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = EDITOR_STYLES;
    root.appendChild(style);

    const container = document.createElement("div");

    // Entity picker
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

    // Name input
    const nameRow = document.createElement("div");
    nameRow.className = "editor-row";
    const nameLabel = document.createElement("label");
    nameLabel.textContent = "Name";
    nameRow.appendChild(nameLabel);
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = this._config.name || "";
    nameInput.placeholder = "Score History";
    nameInput.addEventListener("input", (ev) => {
      this._config = { ...this._config, name: ev.target.value };
      fireConfigChanged(this, this._config);
    });
    nameRow.appendChild(nameInput);
    container.appendChild(nameRow);

    // Default range dropdown
    const rangeRow = document.createElement("div");
    rangeRow.className = "editor-row";
    const rangeLabel = document.createElement("label");
    rangeLabel.textContent = "Default Range";
    rangeRow.appendChild(rangeLabel);
    const rangeSelect = document.createElement("select");
    for (const [value, label] of [
      ["7d", "7 Days"],
      ["30d", "30 Days"],
      ["90d", "90 Days"],
    ]) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      opt.selected = (this._config.default_range || "7d") === value;
      rangeSelect.appendChild(opt);
    }
    rangeSelect.addEventListener("change", (ev) => {
      this._config = { ...this._config, default_range: ev.target.value };
      fireConfigChanged(this, this._config);
    });
    rangeRow.appendChild(rangeSelect);
    container.appendChild(rangeRow);

    // Show stats toggle
    const statsRow = document.createElement("div");
    statsRow.className = "editor-row";
    const statsLabel = document.createElement("label");
    statsLabel.textContent = "Show Stats";
    statsRow.appendChild(statsLabel);
    const statsSwitch = document.createElement("ha-switch");
    statsSwitch.checked = this._config.show_stats !== false;
    statsSwitch.addEventListener("change", (ev) => {
      this._config = { ...this._config, show_stats: ev.target.checked };
      fireConfigChanged(this, this._config);
    });
    statsRow.appendChild(statsSwitch);
    container.appendChild(statsRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-history-editor", PaddleHistoryEditor);
