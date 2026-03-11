import { colorForScore, FACTOR_META, FACTOR_SENSOR_SUFFIX, fireMoreInfo } from "../utils.js";
import { CARD_STYLES } from "../styles/theme.js";

const ALL_FACTORS = Object.keys(FACTOR_META);

const STYLES = `
  ${CARD_STYLES}
  .factors-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .factor-row {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    padding: 4px 0;
    border-radius: 8px;
    transition: background 0.15s ease;
  }
  .factor-row:hover {
    background: var(--secondary-background-color, rgba(0,0,0,0.04));
  }
  .factor-label {
    width: 90px;
    font-size: 0.85em;
    font-weight: 500;
    flex-shrink: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .factor-value {
    width: 60px;
    font-size: 0.8em;
    color: var(--secondary-text-color, #757575);
    flex-shrink: 0;
    text-align: right;
  }
  .factor-bar {
    flex: 1;
    min-width: 40px;
  }
  .factor-score {
    width: 32px;
    font-size: 0.85em;
    font-weight: 600;
    text-align: right;
    flex-shrink: 0;
  }
`;

class PaddleFactorsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = {
      show_factors: ALL_FACTORS,
      ...config,
    };
  }

  set hass(hass) {
    const entity = hass.states[this._config.entity];
    const newState = entity ? `${entity.state}|${JSON.stringify(entity.attributes)}` : "";
    if (this._lastState === newState) return;
    this._lastState = newState;
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const factors = this._config.show_factors || ALL_FACTORS;
    return 1 + factors.length;
  }

  static getStubConfig() {
    return { entity: "" };
  }

  static getConfigElement() {
    return document.createElement("paddle-factors-editor");
  }

  _getSensorEntityId(factorKey) {
    const scoreEntityId = this._config.entity;
    const suffix = FACTOR_SENSOR_SUFFIX[factorKey];
    if (!suffix) return null;
    const result = scoreEntityId.replace(/_score$/, `_${suffix}`);
    if (result === scoreEntityId) {
      console.warn(`[paddle-factors-card] Entity "${scoreEntityId}" does not end in "_score" — cannot derive sensor for ${factorKey}`);
      return null;
    }
    return result;
  }

  _render() {
    const root = this.shadowRoot;
    const entity = this._hass.states[this._config.entity];

    if (!entity) {
      root.textContent = "";
      const style = document.createElement("style");
      style.textContent = STYLES;
      const card = document.createElement("ha-card");
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = `Entity not found: ${this._config.entity}`;
      card.appendChild(empty);
      root.append(style, card);
      return;
    }

    const factors = entity.attributes.factors || {};
    const visibleFactors = this._config.show_factors;
    const name = this._config.name || "Paddle Factors";

    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    const header = document.createElement("div");
    header.className = "card-header";
    header.textContent = name;
    card.appendChild(header);

    const list = document.createElement("div");
    list.className = "factors-list";

    for (const factorKey of visibleFactors) {
      const meta = FACTOR_META[factorKey];
      if (!meta) continue;

      const score = factors[factorKey];
      const scoreNum = score != null ? Number(score) : null;
      const color = colorForScore(scoreNum);
      const sensorEntityId = this._getSensorEntityId(factorKey);
      const sensorEntity = sensorEntityId ? this._hass.states[sensorEntityId] : null;

      const row = document.createElement("div");
      row.className = "factor-row";
      if (sensorEntityId) {
        row.addEventListener("click", () => fireMoreInfo(this, sensorEntityId));
      }

      // Icon circle
      const iconCircle = document.createElement("div");
      iconCircle.className = "icon-circle";
      iconCircle.style.background = color;
      const haIcon = document.createElement("ha-icon");
      haIcon.setAttribute("icon", meta.icon);
      iconCircle.appendChild(haIcon);

      // Label
      const label = document.createElement("div");
      label.className = "factor-label";
      label.textContent = meta.label;

      // Raw value + unit
      const value = document.createElement("div");
      value.className = "factor-value";
      if (sensorEntity && sensorEntity.state != null && sensorEntity.state !== "unavailable" && sensorEntity.state !== "unknown") {
        const rawVal = sensorEntity.state;
        value.textContent = meta.unit ? `${rawVal} ${meta.unit}` : rawVal;
      } else {
        value.textContent = "--";
      }

      // Progress bar
      const barOuter = document.createElement("div");
      barOuter.className = "progress-bar factor-bar";
      const barFill = document.createElement("div");
      barFill.className = "progress-fill";
      barFill.style.background = color;
      barFill.style.width = scoreNum != null ? `${scoreNum}%` : "0%";
      barOuter.appendChild(barFill);

      // Numeric sub-score
      const scoreEl = document.createElement("div");
      scoreEl.className = "factor-score";
      scoreEl.style.color = color;
      scoreEl.textContent = scoreNum != null ? String(scoreNum) : "--";

      row.append(iconCircle, label, value, barOuter, scoreEl);
      list.appendChild(row);
    }

    card.appendChild(list);
    root.append(style, card);
  }
}

customElements.define("paddle-factors-card", PaddleFactorsCard);

export { PaddleFactorsCard };
