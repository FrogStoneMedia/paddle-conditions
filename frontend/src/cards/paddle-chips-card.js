import { colorForRating, formatScore, fireMoreInfo, labelForRating, makeInteractive } from "../utils.js";
import { CARD_STYLES } from "../styles/theme.js";

const STYLES = `
  ${CARD_STYLES}
  ha-card {
    padding: 10px 12px;
  }
  .chips-row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .chips-row::-webkit-scrollbar {
    display: none;
  }
  .chip {
    display: flex;
    align-items: center;
    gap: 6px;
    border-radius: 20px;
    padding: 6px 14px;
    background: var(--ha-card-background, var(--card-background-color, white));
    border: 1.5px solid var(--divider-color, #e0e0e0);
    cursor: pointer;
    flex-shrink: 0;
    font-size: 0.9em;
    font-family: var(--ha-card-header-font-family, inherit);
    color: var(--primary-text-color, #212121);
    white-space: nowrap;
    transition: border-color 0.2s ease;
  }
  .chip:hover {
    background: var(--secondary-background-color, #f5f5f5);
  }
  .chip.active {
    font-weight: 600;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .chip-name {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .chip-score {
    font-weight: 600;
  }
  .refresh-chip {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 20px;
    padding: 6px 10px;
    background: var(--ha-card-background, var(--card-background-color, white));
    border: 1.5px solid var(--divider-color, #e0e0e0);
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.2s ease;
  }
  .refresh-chip:hover {
    background: var(--secondary-background-color, #f5f5f5);
  }
  .refresh-chip ha-icon {
    --mdc-icon-size: 18px;
    color: var(--secondary-text-color, #757575);
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .refresh-chip.spinning ha-icon {
    animation: spin 1s linear infinite;
  }
`;

class PaddleChipsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    if (!config.entities || !Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error("Please define at least one entity in 'entities'");
    }
    this._config = { show_refresh: true, ...config };
  }

  set hass(hass) {
    const states = this._config.entities.map(id => {
      const e = hass.states[id];
      return e ? `${id}:${e.state}` : `${id}:?`;
    }).join("|");
    if (this._lastStates === states && !this._refreshPending) return;
    this._lastStates = states;
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 1;
  }

  static getStubConfig() {
    return { entities: [] };
  }

  static getConfigElement() {
    return document.createElement("paddle-chips-editor");
  }

  _render() {
    const root = this.shadowRoot;
    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    const row = document.createElement("div");
    row.className = "chips-row";
    row.setAttribute("role", "list");
    row.setAttribute("aria-label", "Paddle spots");

    const entities = this._config.entities;

    entities.forEach((entityId, index) => {
      const entity = this._hass.states[entityId];
      if (!entity) return;

      const score = Number(entity.state);
      const attrs = entity.attributes;
      const rating = attrs.rating || "UNKNOWN";
      const color = colorForRating(rating);
      const name = (attrs.friendly_name || entityId).trim();
      const isActive = index === 0;
      const ratingText = labelForRating(rating);

      const chip = document.createElement("div");
      chip.className = isActive ? "chip active" : "chip";
      chip.setAttribute("role", "listitem");
      if (isActive) {
        chip.style.borderColor = color;
      }
      makeInteractive(chip, () => fireMoreInfo(this, entityId), `${name}: ${formatScore(isNaN(score) ? null : score)}, ${ratingText}`);

      const dot = document.createElement("div");
      dot.className = "status-dot";
      dot.style.background = color;
      dot.setAttribute("aria-hidden", "true");

      const nameEl = document.createElement("span");
      nameEl.className = "chip-name";
      nameEl.textContent = name;

      const scoreEl = document.createElement("span");
      scoreEl.className = "chip-score";
      scoreEl.textContent = formatScore(isNaN(score) ? null : score);

      chip.append(dot, nameEl, scoreEl);
      row.appendChild(chip);
    });

    if (this._config.show_refresh) {
      const refreshChip = document.createElement("div");
      refreshChip.className = this._refreshPending ? "refresh-chip spinning" : "refresh-chip";
      const refreshIcon = document.createElement("ha-icon");
      refreshIcon.setAttribute("icon", "mdi:refresh");
      refreshChip.appendChild(refreshIcon);

      const refreshHandler = () => {
        if (this._refreshPending) return;
        this._refreshPending = true;
        this._lastStates = null; // force re-render
        this._render();
        this._hass.callService("homeassistant", "update_entity", {
          entity_id: entities,
        }).finally(() => {
          this._refreshPending = false;
          this._lastStates = null; // force re-render
          this._render();
        });
      };
      makeInteractive(refreshChip, refreshHandler, this._refreshPending ? "Refreshing data" : "Refresh data");
      if (this._refreshPending) refreshChip.setAttribute("aria-busy", "true");

      row.appendChild(refreshChip);
    }

    card.appendChild(row);
    root.append(style, card);
  }
}

customElements.define("paddle-chips-card", PaddleChipsCard);

export { PaddleChipsCard };
