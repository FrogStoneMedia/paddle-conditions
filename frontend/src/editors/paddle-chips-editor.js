import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";

class PaddleChipsEditor extends HTMLElement {
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
      .entity-list { margin-bottom: 12px; }
      .entity-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
      .entity-row ha-entity-picker { flex: 1; }
      .remove-btn { background: none; border: none; cursor: pointer; font-size: 18px; color: var(--secondary-text-color, #727272); padding: 4px 8px; }
      .remove-btn:hover { color: var(--error-color, #F44336); }
      .add-btn { background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 8px 16px; cursor: pointer; color: var(--primary-color, #03a9f4); font-weight: 500; }
      .add-btn:hover { background: var(--secondary-background-color, #f5f5f5); }
    `;
    root.appendChild(style);

    const container = document.createElement("div");

    // Entity pickers heading
    const heading = document.createElement("div");
    heading.style.cssText = "font-weight: 500; margin-bottom: 8px;";
    heading.textContent = "Entities";
    container.appendChild(heading);

    // Entity list
    const entities = this._config.entities || [];
    const listDiv = document.createElement("div");
    listDiv.className = "entity-list";

    entities.forEach((entityId, index) => {
      const row = document.createElement("div");
      row.className = "entity-row";

      const picker = document.createElement("ha-entity-picker");
      picker.hass = this._hass;
      picker.value = entityId;
      picker.includeDomains = ["sensor"];
      picker.addEventListener("value-changed", (ev) => {
        const updated = [...(this._config.entities || [])];
        updated[index] = ev.detail.value;
        this._config = { ...this._config, entities: updated };
        fireConfigChanged(this, this._config);
      });
      row.appendChild(picker);

      const removeBtn = document.createElement("button");
      removeBtn.className = "remove-btn";
      removeBtn.textContent = "X";
      removeBtn.addEventListener("click", () => {
        const updated = [...(this._config.entities || [])];
        updated.splice(index, 1);
        this._config = { ...this._config, entities: updated };
        fireConfigChanged(this, this._config);
        this._render();
      });
      row.appendChild(removeBtn);

      listDiv.appendChild(row);
    });

    container.appendChild(listDiv);

    // Add entity button
    const addBtn = document.createElement("button");
    addBtn.className = "add-btn";
    addBtn.textContent = "Add Entity";
    addBtn.addEventListener("click", () => {
      const updated = [...(this._config.entities || []), ""];
      this._config = { ...this._config, entities: updated };
      fireConfigChanged(this, this._config);
      this._render();
    });
    container.appendChild(addBtn);

    // Show refresh switch row
    const refreshRow = document.createElement("div");
    refreshRow.className = "editor-row";
    refreshRow.style.marginTop = "16px";
    const refreshLabel = document.createElement("label");
    refreshLabel.textContent = "Show Refresh";
    refreshRow.appendChild(refreshLabel);
    const refreshSwitch = document.createElement("ha-switch");
    if (this._config.show_refresh !== false) {
      refreshSwitch.setAttribute("checked", "");
    }
    refreshSwitch.addEventListener("change", (ev) => {
      this._config = { ...this._config, show_refresh: ev.target.checked };
      fireConfigChanged(this, this._config);
    });
    refreshRow.appendChild(refreshSwitch);
    container.appendChild(refreshRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-chips-editor", PaddleChipsEditor);
