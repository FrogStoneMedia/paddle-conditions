import { colorForRating, colorForScore, formatScore } from "../utils.js";
import { CARD_STYLES } from "../styles/theme.js";

const STYLES = `
  ${CARD_STYLES}
  .best-window {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    margin-bottom: 12px;
    border-radius: 8px;
    background: var(--accent-color, #03a9f4);
    color: white;
    font-weight: 500;
    font-size: 0.95em;
  }
  .best-window ha-icon {
    --mdc-icon-size: 20px;
    color: white;
    flex-shrink: 0;
  }
  .forecast-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9em;
  }
  .forecast-table th {
    text-align: left;
    font-weight: 600;
    font-size: 0.8em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--secondary-text-color, #757575);
    padding: 4px 8px 8px;
    border-bottom: 1px solid var(--divider-color, #e0e0e0);
  }
  .forecast-table td {
    padding: 6px 8px;
    vertical-align: middle;
  }
  .forecast-table tr.best-row {
    background: var(--accent-color, #03a9f4);
    background: color-mix(in srgb, var(--accent-color, #03a9f4) 15%, transparent);
  }
  .score-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.85em;
    color: white;
  }
  .rating-text {
    font-weight: 500;
    font-size: 0.85em;
    text-transform: capitalize;
  }
`;

function formatTime(isoString) {
  if (!isoString) return "--";
  const match = isoString.match(/(\d{2}:\d{2})/);
  return match ? match[1] : "--";
}

class PaddleForecastCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = { max_blocks: 8, ...config };
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
    return 4;
  }

  static getStubConfig() {
    return { entity: "" };
  }

  static getConfigElement() {
    return document.createElement("paddle-forecast-editor");
  }

  _render() {
    const entity = this._hass.states[this._config.entity];
    const root = this.shadowRoot;
    root.textContent = "";

    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    if (!entity) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = `Entity not found: ${this._config.entity}`;
      card.appendChild(empty);
      root.append(style, card);
      return;
    }

    const attrs = entity.attributes;
    const blocks = attrs.blocks;

    if (!blocks || !blocks.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No forecast blocks available";
      card.appendChild(empty);
      root.append(style, card);
      return;
    }

    // Best window banner
    if (attrs.best_block != null && attrs.best_score != null) {
      const banner = document.createElement("div");
      banner.className = "best-window";

      const starIcon = document.createElement("ha-icon");
      starIcon.setAttribute("icon", "mdi:star");
      banner.appendChild(starIcon);

      const bannerText = document.createElement("span");
      bannerText.textContent = `Best Window: ${formatTime(attrs.best_block)} \u2014 ${formatScore(attrs.best_score)}`;
      banner.appendChild(bannerText);

      card.appendChild(banner);
    }

    // Forecast table
    const table = document.createElement("table");
    table.className = "forecast-table";
    table.setAttribute("aria-label", "Paddle conditions forecast");

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const headers = ["Time", "Score", "Rating", "Wind", "Temp", "UV"];
    for (const h of headers) {
      const th = document.createElement("th");
      th.setAttribute("scope", "col");
      th.textContent = h;
      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    const maxBlocks = this._config.max_blocks;
    const displayBlocks = blocks.slice(0, maxBlocks);

    for (const block of displayBlocks) {
      const tr = document.createElement("tr");

      // Highlight best window row
      const isBest = attrs.best_block && block.start === attrs.best_block;
      if (isBest) {
        tr.className = "best-row";
        tr.setAttribute("aria-label", "Best time window");
      }

      // Time
      const tdTime = document.createElement("td");
      tdTime.textContent = formatTime(block.start);
      tr.appendChild(tdTime);

      // Score pill
      const tdScore = document.createElement("td");
      const pill = document.createElement("span");
      pill.className = "score-pill";
      pill.style.background = colorForScore(block.score);
      pill.textContent = formatScore(block.score != null ? block.score : null);
      tdScore.appendChild(pill);
      tr.appendChild(tdScore);

      // Rating
      const tdRating = document.createElement("td");
      const ratingSpan = document.createElement("span");
      ratingSpan.className = "rating-text";
      const rating = block.rating || "UNKNOWN";
      ratingSpan.style.color = colorForRating(rating);
      ratingSpan.textContent = rating.replace("_", " ").toLowerCase();
      tdRating.appendChild(ratingSpan);
      tr.appendChild(tdRating);

      // Wind
      const tdWind = document.createElement("td");
      tdWind.textContent = block.wind_mph != null ? `${block.wind_mph} mph` : "--";
      tr.appendChild(tdWind);

      // Temp
      const tdTemp = document.createElement("td");
      tdTemp.textContent = block.temp_f != null ? `${block.temp_f}\u00B0F` : "--";
      tr.appendChild(tdTemp);

      // UV
      const tdUV = document.createElement("td");
      tdUV.textContent = block.uv != null ? String(block.uv) : "--";
      tr.appendChild(tdUV);

      tbody.appendChild(tr);
    }

    table.appendChild(tbody);
    card.appendChild(table);
    root.append(style, card);
  }
}

customElements.define("paddle-forecast-card", PaddleForecastCard);

export { PaddleForecastCard };
