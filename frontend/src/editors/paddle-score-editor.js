import { fireConfigChanged, EDITOR_STYLES } from "./base-editor.js";

class PaddleScoreEditor extends HTMLElement {
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

    // Name input row
    const nameRow = document.createElement("div");
    nameRow.className = "editor-row";
    const nameLabel = document.createElement("label");
    nameLabel.textContent = "Name";
    nameRow.appendChild(nameLabel);
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = this._config.name || "";
    nameInput.placeholder = "Card name";
    nameInput.addEventListener("input", (ev) => {
      this._config = { ...this._config, name: ev.target.value };
      fireConfigChanged(this, this._config);
    });
    nameRow.appendChild(nameInput);
    container.appendChild(nameRow);

    // Show profile switch row
    const profileRow = document.createElement("div");
    profileRow.className = "editor-row";
    const profileLabel = document.createElement("label");
    profileLabel.textContent = "Show Profile";
    profileRow.appendChild(profileLabel);
    const profileSwitch = document.createElement("ha-switch");
    if (this._config.show_profile !== false) {
      profileSwitch.setAttribute("checked", "");
    }
    profileSwitch.addEventListener("change", (ev) => {
      this._config = { ...this._config, show_profile: ev.target.checked };
      fireConfigChanged(this, this._config);
    });
    profileRow.appendChild(profileSwitch);
    container.appendChild(profileRow);

    // Show limiting factor switch row
    const factorRow = document.createElement("div");
    factorRow.className = "editor-row";
    const factorLabel = document.createElement("label");
    factorLabel.textContent = "Show Limiting Factor";
    factorRow.appendChild(factorLabel);
    const factorSwitch = document.createElement("ha-switch");
    if (this._config.show_limiting_factor !== false) {
      factorSwitch.setAttribute("checked", "");
    }
    factorSwitch.addEventListener("change", (ev) => {
      this._config = { ...this._config, show_limiting_factor: ev.target.checked };
      fireConfigChanged(this, this._config);
    });
    factorRow.appendChild(factorSwitch);
    container.appendChild(factorRow);

    root.appendChild(container);
  }
}

customElements.define("paddle-score-editor", PaddleScoreEditor);
