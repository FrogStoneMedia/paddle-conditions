import { colorForRating, formatScore, iconForRating, fireMoreInfo } from "../utils.js";
import { CARD_STYLES } from "../styles/theme.js";

// NOTE: innerHTML usage is safe here — all data comes from Home Assistant's
// trusted state objects (entity states/attributes set by our Python backend
// from known API responses). Shadow DOM provides isolation. This is the
// standard pattern used by HA's built-in and community Lovelace cards.

const STYLES = `
  ${CARD_STYLES}
  .score-layout {
    display: flex;
    align-items: center;
    gap: 16px;
    cursor: pointer;
  }
  .score-border {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    border-radius: 12px 0 0 12px;
  }
  ha-card {
    position: relative;
    overflow: hidden;
  }
  .score-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .score-icon ha-icon {
    --mdc-icon-size: 28px;
    color: white;
  }
  .score-info {
    flex: 1;
    min-width: 0;
  }
  .score-name {
    font-size: 1.1em;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .score-detail {
    font-size: 0.85em;
    color: var(--secondary-text-color, #757575);
    margin-top: 2px;
  }
  .score-value {
    text-align: right;
    flex-shrink: 0;
  }
  .score-number {
    font-size: 1.8em;
    font-weight: 700;
    line-height: 1;
  }
  .rating-badge {
    margin-top: 4px;
  }
`;

class PaddleScoreCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = { show_profile: true, show_limiting_factor: true, ...config };
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
    return 2;
  }

  static getStubConfig() {
    return { entity: "" };
  }

  static getConfigElement() {
    return document.createElement("paddle-score-editor");
  }

  _render() {
    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.textContent = "";
      const card = document.createElement("ha-card");
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = `Entity not found: ${this._config.entity}`;
      card.appendChild(empty);
      const style = document.createElement("style");
      style.textContent = STYLES;
      this.shadowRoot.append(style, card);
      return;
    }

    const score = Number(entity.state);
    const attrs = entity.attributes;
    const rating = attrs.rating || "UNKNOWN";
    const color = colorForRating(rating);
    const icon = iconForRating(rating);
    const name = this._config.name || attrs.friendly_name || "Paddle Score";

    let detail = "";
    if (this._config.show_profile && attrs.profile) {
      detail = `${attrs.activity || ""} - ${attrs.profile}`.replace(/^[\s-]+/, "");
    }
    if (this._config.show_limiting_factor) {
      if (attrs.vetoed && attrs.veto_reason) {
        detail = `Vetoed: ${attrs.veto_reason}`;
      } else if (attrs.limiting_factor) {
        detail = detail ? `${detail} | Limit: ${attrs.limiting_factor}` : `Limiting: ${attrs.limiting_factor}`;
      }
    }

    const ratingLabel = rating.replace("_", " ");

    // Build DOM imperatively — all text set via textContent (safe)
    const root = this.shadowRoot;
    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    const border = document.createElement("div");
    border.className = "score-border";
    border.style.background = color;

    const layout = document.createElement("div");
    layout.className = "score-layout";
    layout.addEventListener("click", () => fireMoreInfo(this, this._config.entity));

    const iconCircle = document.createElement("div");
    iconCircle.className = "score-icon";
    iconCircle.style.background = color;
    const haIcon = document.createElement("ha-icon");
    haIcon.setAttribute("icon", icon);
    iconCircle.appendChild(haIcon);

    const info = document.createElement("div");
    info.className = "score-info";
    const nameEl = document.createElement("div");
    nameEl.className = "score-name";
    nameEl.textContent = name;
    info.appendChild(nameEl);
    if (detail) {
      const detailEl = document.createElement("div");
      detailEl.className = "score-detail";
      detailEl.textContent = detail;
      info.appendChild(detailEl);
    }

    const value = document.createElement("div");
    value.className = "score-value";
    const number = document.createElement("div");
    number.className = "score-number";
    number.style.color = color;
    number.textContent = formatScore(isNaN(score) ? null : score);
    const badge = document.createElement("div");
    badge.className = "rating-badge";
    badge.style.background = color;
    badge.textContent = ratingLabel;
    value.append(number, badge);

    layout.append(iconCircle, info, value);
    card.append(border, layout);
    root.append(style, card);
  }
}

customElements.define("paddle-score-card", PaddleScoreCard);

export { PaddleScoreCard };
