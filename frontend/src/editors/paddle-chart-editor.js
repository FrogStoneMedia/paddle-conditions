import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";
import { CHART_METRICS } from "../charts/chart-utils.js";

class PaddleChartEditor extends HTMLElement {
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
    style.textContent =
      EDITOR_STYLES +
      `
      .metrics-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
      .metrics-group label { display: flex; align-items: center; gap: 4px; font-weight: normal; min-width: auto; }
    `;
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
    nameInput.placeholder = "Forecast";
    nameInput.addEventListener("input", (ev) => {
      this._config = { ...this._config, name: ev.target.value };
      fireConfigChanged(this, this._config);
    });
    nameRow.appendChild(nameInput);
    container.appendChild(nameRow);

    // Default metrics checkboxes
    const metricsRow = document.createElement("div");
    metricsRow.className = "editor-row";
    const metricsLabel = document.createElement("label");
    metricsLabel.textContent = "Default Metrics";
    metricsRow.appendChild(metricsLabel);
    const metricsGroup = document.createElement("div");
    metricsGroup.className = "metrics-group";

    const currentMetrics = this._config.default_metrics || ["score"];

    for (const [key, meta] of Object.entries(CHART_METRICS)) {
      const itemLabel = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = currentMetrics.includes(key);
      checkbox.disabled = key === "score";
      checkbox.addEventListener("change", () => {
        const metrics = [...(this._config.default_metrics || ["score"])];
        if (checkbox.checked && !metrics.includes(key)) {
          metrics.push(key);
        } else if (!checkbox.checked && key !== "score") {
          const idx = metrics.indexOf(key);
          if (idx !== -1) metrics.splice(idx, 1);
        }
        this._config = { ...this._config, default_metrics: metrics };
        fireConfigChanged(this, this._config);
      });
      itemLabel.appendChild(checkbox);
      const text = document.createTextNode(` ${meta.label}`);
      itemLabel.appendChild(text);
      metricsGroup.appendChild(itemLabel);
    }

    metricsRow.appendChild(metricsGroup);
    container.appendChild(metricsRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-chart-editor", PaddleChartEditor);
