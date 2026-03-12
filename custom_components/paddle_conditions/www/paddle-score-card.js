class PaddleScoreCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._expandedBlock = null;
    this._expandedFactor = null;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = config;
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!prev || this._stateChanged(prev)) this._render();
  }

  _stateChanged(prev) {
    const base = this._config.entity.replace(/_paddle_score$/, "");
    const keys = [
      "paddle_score", "wind_speed", "wind_gusts", "wind_direction",
      "air_temperature", "water_temperature", "uv_index",
      "air_quality_index", "visibility", "precipitation_chance",
      "conditions", "3_hour_forecast",
    ];
    for (const k of keys) {
      if (prev.states[`${base}_${k}`] !== this._hass.states[`${base}_${k}`]) return true;
    }
    return false;
  }

  _entity(suffix) {
    const base = this._config.entity.replace(/_paddle_score$/, "");
    return this._hass.states[`${base}_${suffix}`];
  }

  _scoreColor(score) {
    if (score == null) return "#666";
    if (score >= 70) return "#66BB6A";
    if (score >= 40) return "#FDD835";
    return "#F44336";
  }

  _ratingGradient(rating) {
    const gradients = {
      GO: "linear-gradient(135deg, #1B5E20, #2E7D32)",
      CAUTION: "linear-gradient(135deg, #E65100, #F57C00)",
      NO_GO: "linear-gradient(135deg, #B71C1C, #C62828)",
    };
    return gradients[rating] || gradients.NO_GO;
  }

  _ratingLabel(rating) {
    return { GO: "GO", CAUTION: "CAUTION", NO_GO: "NO GO" }[rating] || "\u2014";
  }

  getCardSize() { return 6; }

  _el(tag, attrs, children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "style" && typeof v === "object") {
          Object.assign(el.style, v);
        } else if (k === "className") {
          el.className = v;
        } else if (k === "textContent") {
          el.textContent = v;
        } else {
          el.setAttribute(k, v);
        }
      }
    }
    if (children) {
      for (const child of Array.isArray(children) ? children : [children]) {
        if (typeof child === "string") {
          el.appendChild(document.createTextNode(child));
        } else if (child) {
          el.appendChild(child);
        }
      }
    }
    return el;
  }

  _getSunWindow() {
    const sun = this._hass.states["sun.sun"];
    if (!sun) return null;

    const attrs = sun.attributes || {};
    const rising = attrs.next_rising ? new Date(attrs.next_rising) : null;
    const setting = attrs.next_setting ? new Date(attrs.next_setting) : null;
    if (!rising || !setting) return null;

    const isUp = sun.state === "above_horizon";
    let sunrise, sunset;
    if (isUp) {
      sunset = setting;
      sunrise = new Date(rising.getTime() - 24 * 60 * 60 * 1000);
    } else {
      sunrise = rising;
      sunset = setting;
    }
    return { sunrise, sunset };
  }

  _filterDaylightBlocks(blocks) {
    const win = this._getSunWindow();
    if (!win) return blocks;

    // Best time: after sunrise, ending 2h before sunset
    const cutoff = new Date(win.sunset.getTime() - 2 * 60 * 60 * 1000);
    return blocks.filter((b) => {
      const start = new Date(b.start);
      const end = new Date(b.end);
      return start >= win.sunrise && end <= cutoff;
    });
  }

  _filterDisplayBlocks(blocks) {
    const win = this._getSunWindow();
    if (!win) return blocks;

    // Display range: 1h before sunrise to 1h after sunset
    const from = new Date(win.sunrise.getTime() - 60 * 60 * 1000);
    const to = new Date(win.sunset.getTime() + 60 * 60 * 1000);
    return blocks.filter((b) => {
      const start = new Date(b.start);
      return start >= from && start <= to;
    });
  }

  _degToCompass(deg) {
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(deg / 45) % 8];
  }

  _render() {
    if (!this._hass || !this._config) return;

    const scoreEntity = this._hass.states[this._config.entity];
    if (!scoreEntity) {
      this.shadowRoot.textContent = "";
      const card = this._el("ha-card");
      card.appendChild(this._el("div", { style: { padding: "16px" }, textContent: `Entity not found: ${this._config.entity}` }));
      this.shadowRoot.appendChild(this._styleEl());
      this.shadowRoot.appendChild(card);
      return;
    }

    const score = parseInt(scoreEntity.state, 10);
    const attrs = scoreEntity.attributes || {};
    const rating = attrs.rating || "\u2014";
    const factors = attrs.factors || {};
    const name = (attrs.friendly_name || "").replace(/ Paddle Score$/i, "");

    const forecastEntity = this._entity("3_hour_forecast");
    const blocks = forecastEntity?.attributes?.blocks || [];

    this.shadowRoot.textContent = "";
    this.shadowRoot.appendChild(this._styleEl());

    const card = this._el("ha-card");
    card.appendChild(this._buildHero(name, score, rating, blocks));
    card.appendChild(this._buildFactorGrid(factors, blocks));
    const forecast = this._buildForecast(blocks);
    if (forecast) card.appendChild(forecast);

    this.shadowRoot.appendChild(card);
  }

  _buildHero(name, score, rating, blocks) {
    const hero = this._el("div", { className: "hero", style: { background: this._ratingGradient(rating) } });
    hero.appendChild(this._el("div", { className: "hero-name", textContent: name }));
    hero.appendChild(this._el("div", { className: "hero-score", textContent: isNaN(score) ? "\u2014" : String(score) }));
    hero.appendChild(this._el("div", { className: "hero-rating", textContent: this._ratingLabel(rating) }));

    if (blocks.length > 0) {
      const safeBlocks = this._filterDaylightBlocks(blocks);
      if (safeBlocks.length > 0) {
        const best = safeBlocks.reduce((a, b) => b.score > a.score ? b : a, safeBlocks[0]);
        const now = new Date();
        const bestStart = new Date(best.start);
        const bestEnd = new Date(best.end);
        const isCurrent = now >= bestStart && now < bestEnd;

        let text;
        if (isCurrent) {
          text = `Best time: Now (${best.score})`;
        } else {
          const timeStr = bestStart.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
          text = `Best time: ${timeStr} (${best.score})`;
        }
        hero.appendChild(this._el("div", { className: "hero-best", textContent: text }));
      }
    }
    return hero;
  }

  _buildFactorGrid(factors, blocks) {
    // Maps factor keys to forecast block fields for daily drill-down
    const blockFieldMap = {
      wind_speed: { field: "wind_mph", unit: "mph", label: "Wind" },
      temperature: { field: "temp_f", unit: "\u00B0F", label: "Temp" },
      uv_index: { field: "uv", unit: "", label: "UV" },
      precipitation: { field: "precip_pct", unit: "%", label: "Precip" },
    };

    const meta = [
      { key: "wind_speed", icon: "\uD83D\uDCA8", label: "Wind", suffix: "wind_speed", gustSuffix: "wind_gusts", dirSuffix: "wind_direction", unit: "mph" },
      { key: "air_quality", icon: "\uD83C\uDF2C\uFE0F", label: "Air Quality", suffix: "air_quality_index", unit: "AQI" },
      { key: "temperature", icon: "\uD83C\uDF21\uFE0F", label: "Temperature", suffix: "air_temperature", waterSuffix: "water_temperature", unit: "\u00B0F" },
      { key: "uv_index", icon: "\u2600\uFE0F", label: "UV Index", suffix: "uv_index", unit: "" },
      { key: "visibility", icon: "\uD83D\uDC41\uFE0F", label: "Visibility", suffix: "visibility", unit: "mi", round: 1 },
      { key: "precipitation", icon: "\uD83C\uDF27\uFE0F", label: "Precipitation", suffix: "precipitation_chance", unit: "%" },
    ];

    const grid = this._el("div", { className: "factor-grid" });

    for (const f of meta) {
      if (factors[f.key] == null) continue;
      const subScore = factors[f.key];
      const entity = this._entity(f.suffix);
      let rawVal = entity ? entity.state : "\u2014";
      if (f.round != null && rawVal !== "\u2014" && !isNaN(parseFloat(rawVal))) {
        rawVal = parseFloat(rawVal).toFixed(f.round);
      }
      let detail = `${rawVal}${f.unit ? " " + f.unit : ""}`;

      if (f.gustSuffix) {
        const gustEntity = this._entity(f.gustSuffix);
        if (gustEntity?.state) detail += ` (gusts ${gustEntity.state} ${f.unit})`;
        const dirEntity = this._entity(f.dirSuffix);
        if (dirEntity?.state) detail += ` ${this._degToCompass(parseFloat(dirEntity.state))}`;
      }
      if (f.waterSuffix) {
        const waterEntity = this._entity(f.waterSuffix);
        if (waterEntity?.state && waterEntity.state !== "unavailable")
          detail += ` / Water: ${waterEntity.state}${f.unit}`;
      }

      const isExpanded = this._expandedFactor === f.key;
      const hasForecast = blockFieldMap[f.key] && blocks.length > 0;

      const tile = this._el("div", {
        className: `factor-tile${isExpanded ? " factor-expanded" : ""}${hasForecast ? " factor-clickable" : ""}`,
      });

      const header = this._el("div", { className: "factor-header" });
      header.appendChild(this._el("span", { className: "factor-icon", textContent: f.icon }));
      header.appendChild(this._el("span", { className: "factor-label", textContent: f.label }));
      if (hasForecast) {
        header.appendChild(this._el("span", { className: "factor-chevron", textContent: isExpanded ? "\u25B2" : "\u25BC" }));
      }
      tile.appendChild(header);

      tile.appendChild(this._el("div", { className: "factor-value", textContent: detail }));

      const barWrap = this._el("div", { className: "factor-bar-wrap" });
      barWrap.appendChild(this._el("div", { className: "factor-bar", style: { width: `${subScore}%`, background: this._scoreColor(subScore) } }));
      tile.appendChild(barWrap);

      tile.appendChild(this._el("div", { className: "factor-score", style: { color: this._scoreColor(subScore) }, textContent: `${subScore}/100` }));

      // Forecast drill-down when expanded
      if (isExpanded && hasForecast) {
        const bfm = blockFieldMap[f.key];
        const displayBlocks = this._filterDisplayBlocks(blocks);
        tile.appendChild(this._buildFactorForecast(displayBlocks, bfm));
      }

      if (hasForecast) {
        tile.addEventListener("click", () => {
          this._expandedFactor = this._expandedFactor === f.key ? null : f.key;
          this._render();
        });
      }

      grid.appendChild(tile);
    }
    return grid;
  }

  _buildFactorForecast(blocks, bfm) {
    const container = this._el("div", { className: "factor-forecast" });
    const now = new Date();

    for (const b of blocks) {
      const start = new Date(b.start);
      const end = new Date(b.end);
      const isCurrent = now >= start && now < end;
      const val = b[bfm.field];
      if (val == null) continue;

      const displayVal = bfm.unit === "\u00B0F" ? `${Math.round(val)}${bfm.unit}` :
                         bfm.unit ? `${Math.round(val)} ${bfm.unit}` :
                         String(Math.round(val * 10) / 10);
      const timeLabel = start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

      const item = this._el("div", { className: `ff-item${isCurrent ? " ff-current" : ""}` });
      item.appendChild(this._el("div", { className: "ff-time", textContent: timeLabel }));
      item.appendChild(this._el("div", { className: "ff-val", textContent: displayVal }));

      container.appendChild(item);
    }

    return container;
  }

  _buildForecast(blocks) {
    const displayBlocks = this._filterDisplayBlocks(blocks);
    if (!displayBlocks.length) return null;

    const section = this._el("div", { className: "forecast-section" });
    section.appendChild(this._el("div", { className: "forecast-title", textContent: "Forecast" }));

    const row = this._el("div", { className: "forecast-row" });
    const now = new Date();

    displayBlocks.forEach((b, i) => {
      const start = new Date(b.start);
      const end = new Date(b.end);
      const isCurrent = now >= start && now < end;
      const expanded = this._expandedBlock === i;
      const timeLabel = start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

      const block = this._el("div", {
        className: `forecast-block${isCurrent ? " current" : ""}${expanded ? " expanded" : ""}`,
      });
      block.dataset.idx = i;

      if (isCurrent) block.appendChild(this._el("div", { className: "now-label", textContent: "NOW" }));
      block.appendChild(this._el("div", { className: "block-time", textContent: timeLabel }));
      block.appendChild(this._el("div", { className: "block-score", style: { color: this._scoreColor(b.score) }, textContent: String(b.score) }));
      block.appendChild(this._el("div", { className: "block-detail", textContent: `${Math.round(b.wind_mph)} mph` }));
      block.appendChild(this._el("div", { className: "block-detail", textContent: `${Math.round(b.temp_f)}\u00B0F` }));

      block.addEventListener("click", () => {
        this._expandedBlock = this._expandedBlock === i ? null : i;
        this._render();
      });

      row.appendChild(block);
    });

    section.appendChild(row);

    if (this._expandedBlock != null && this._expandedBlock < displayBlocks.length) {
      const b = displayBlocks[this._expandedBlock];
      const detail = this._el("div", { className: "expanded-detail" });

      const rows = [
        ["Score", `${b.score} \u2014 ${this._ratingLabel(b.rating)}`, this._scoreColor(b.score)],
        ["Wind", `${Math.round(b.wind_mph)} mph`, null],
        ["Temperature", `${Math.round(b.temp_f)}\u00B0F`, null],
        ["UV Index", b.uv != null ? String(b.uv) : "\u2014", null],
      ];

      for (const [label, value, color] of rows) {
        const r = this._el("div", { className: "detail-row" });
        r.appendChild(this._el("span", { textContent: label }));
        const valSpan = this._el("span", { textContent: value });
        if (color) valSpan.style.color = color;
        r.appendChild(valSpan);
        detail.appendChild(r);
      }
      section.appendChild(detail);
    }

    return section;
  }

  _styleEl() {
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      ha-card { overflow: hidden; background: var(--card-background-color, #1e1e2e); border-radius: 12px; }

      .hero {
        padding: 24px 20px;
        text-align: center;
        color: #fff;
      }
      .hero-name {
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        opacity: 0.9;
        margin-bottom: 4px;
      }
      .hero-score {
        font-size: 64px;
        font-weight: 700;
        line-height: 1;
        margin: 4px 0;
      }
      .hero-rating {
        font-size: 18px;
        font-weight: 600;
        letter-spacing: 2px;
        margin-bottom: 4px;
      }
      .hero-best {
        font-size: 13px;
        opacity: 0.9;
        margin-top: 2px;
      }

      .factor-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        padding: 12px;
      }
      @media (max-width: 400px) {
        .factor-grid { gap: 6px; padding: 8px; }
        .factor-tile { padding: 8px; }
        .factor-label { font-size: 11px; }
        .factor-value { font-size: 12px; }
        .hero-score { font-size: 48px; }
        .hero-name { font-size: 12px; }
        .hero-rating { font-size: 16px; }
      }
      @media (max-width: 300px) {
        .factor-grid { grid-template-columns: 1fr; }
      }
      .factor-tile {
        background: var(--primary-background-color, #2a2a3e);
        border-radius: 8px;
        padding: 10px;
        transition: border-color 0.2s;
        border: 1px solid transparent;
      }
      .factor-clickable {
        cursor: pointer;
      }
      .factor-clickable:hover {
        border-color: rgba(255,255,255,0.15);
      }
      .factor-expanded {
        grid-column: 1 / -1;
        border-color: var(--primary-color, #4fc3f7);
      }
      .factor-header {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 4px;
      }
      .factor-icon { font-size: 16px; }
      .factor-label {
        font-size: 12px;
        font-weight: 600;
        color: var(--primary-text-color, #e0e0e0);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        flex: 1;
      }
      .factor-chevron {
        font-size: 10px;
        color: var(--secondary-text-color, #aaa);
      }
      .factor-value {
        font-size: 13px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 6px;
      }
      .factor-bar-wrap {
        height: 4px;
        background: rgba(255,255,255,0.1);
        border-radius: 2px;
        overflow: hidden;
        margin-bottom: 4px;
      }
      .factor-bar {
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
      }
      .factor-score {
        font-size: 11px;
        font-weight: 600;
        text-align: right;
      }

      .factor-forecast {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        margin-top: 10px;
        padding: 8px 0 4px;
        border-top: 1px solid rgba(255,255,255,0.08);
        scrollbar-width: thin;
      }
      .ff-item {
        flex: 0 0 auto;
        text-align: center;
        min-width: 56px;
        padding: 6px 4px;
        background: rgba(255,255,255,0.05);
        border-radius: 6px;
        border: 1px solid transparent;
      }
      .ff-current {
        border-color: #66BB6A;
      }
      .ff-time {
        font-size: 10px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 3px;
      }
      .ff-val {
        font-size: 13px;
        font-weight: 600;
        color: var(--primary-text-color, #e0e0e0);
      }

      .forecast-section { padding: 12px; }
      .forecast-title {
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 8px;
      }
      .forecast-row {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 4px;
        scrollbar-width: thin;
      }
      .forecast-block {
        flex: 0 0 auto;
        min-width: 72px;
        text-align: center;
        padding: 10px 8px;
        background: var(--primary-background-color, #2a2a3e);
        border-radius: 8px;
        cursor: pointer;
        border: 2px solid transparent;
        transition: border-color 0.2s;
      }
      .forecast-block:hover { border-color: rgba(255,255,255,0.2); }
      .forecast-block.current { border-color: #66BB6A; }
      .forecast-block.expanded { border-color: var(--primary-color, #4fc3f7); }
      .now-label {
        font-size: 9px;
        font-weight: 700;
        color: #66BB6A;
        letter-spacing: 1px;
        margin-bottom: 2px;
      }
      .block-time {
        font-size: 11px;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 4px;
      }
      .block-score {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.1;
      }
      .block-detail {
        font-size: 11px;
        color: var(--secondary-text-color, #aaa);
      }

      .expanded-detail {
        margin-top: 8px;
        background: var(--primary-background-color, #2a2a3e);
        border-radius: 8px;
        padding: 12px;
      }
      .detail-row {
        display: flex;
        justify-content: space-between;
        padding: 4px 0;
        font-size: 13px;
        color: var(--primary-text-color, #e0e0e0);
        border-bottom: 1px solid rgba(255,255,255,0.05);
      }
      .detail-row:last-child { border-bottom: none; }
      .detail-row span:first-child {
        color: var(--secondary-text-color, #aaa);
      }
    `;
    return style;
  }
}

customElements.define("paddle-score-card", PaddleScoreCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "paddle-score-card",
  name: "Paddle Score Card",
  description: "Paddling conditions score with factor breakdown and forecast",
});
