import { CARD_STYLES } from "../styles/theme.js";

const STYLES = `
  ${CARD_STYLES}
  .fitness-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 24px 16px;
    background: var(--ha-card-background, var(--card-background-color, white));
  }
  .fitness-placeholder .icon-circle {
    width: 56px;
    height: 56px;
    background: rgba(33, 150, 243, 0.12);
    margin-bottom: 12px;
  }
  .fitness-placeholder .icon-circle ha-icon {
    --mdc-icon-size: 28px;
    color: #2196F3;
  }
  .fitness-title {
    font-size: 1.15em;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--primary-text-color, #212121);
  }
  .feature-list {
    list-style: none;
    margin: 0;
    padding: 0;
    width: 100%;
    margin-bottom: 16px;
  }
  .feature-list li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 0.9em;
    color: var(--secondary-text-color, #757575);
  }
  .feature-list li ha-icon {
    --mdc-icon-size: 18px;
    color: var(--pc-go, #4CAF50);
    flex-shrink: 0;
  }
  .coming-soon {
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--pc-grey, #9E9E9E);
    padding: 4px 14px;
    border: 1px solid var(--divider-color, #e0e0e0);
    border-radius: 12px;
  }
`;

const FEATURES = [
  "Track paddle sessions",
  "Monthly goals & streaks",
  "Distance & duration stats",
];

class PaddleFitnessCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    this._config = { monthly_goal: 12, ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    return document.createElement("paddle-fitness-editor");
  }

  _render() {
    const root = this.shadowRoot;
    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    const container = document.createElement("div");
    container.className = "fitness-placeholder";

    // Icon circle
    const iconCircle = document.createElement("div");
    iconCircle.className = "icon-circle";
    const haIcon = document.createElement("ha-icon");
    haIcon.setAttribute("icon", "mdi:rowing");
    iconCircle.appendChild(haIcon);

    // Title
    const title = document.createElement("div");
    title.className = "fitness-title";
    title.textContent = "Session Tracking";

    // Feature list
    const list = document.createElement("ul");
    list.className = "feature-list";
    for (const text of FEATURES) {
      const li = document.createElement("li");
      const checkIcon = document.createElement("ha-icon");
      checkIcon.setAttribute("icon", "mdi:check-circle-outline");
      const span = document.createElement("span");
      span.textContent = text;
      li.append(checkIcon, span);
      list.appendChild(li);
    }

    // Coming soon badge
    const badge = document.createElement("div");
    badge.className = "coming-soon";
    badge.textContent = "Coming Soon";

    container.append(iconCircle, title, list, badge);
    card.appendChild(container);
    root.append(style, card);
  }
}

customElements.define("paddle-fitness-card", PaddleFitnessCard);

export { PaddleFitnessCard };
