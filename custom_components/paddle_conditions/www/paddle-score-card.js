class PaddleScoreCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._expandedBlock = null;
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
      "air_temp", "water_temp", "uv_index", "aqi", "visibility",
      "precipitation", "condition", "forecast_3hr",
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
    return { GO: "GO", CAUTION: "CAUTION", NO_GO: "NO GO" }[rating] || "—";
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
    const rating = attrs.rating || "—";
    const limitingFactor = attrs.limiting_factor;
    const factors = attrs.factors || {};
    const name = (attrs.friendly_name || "").replace(/ Paddle Score$/i, "");

    const forecastEntity = this._entity("forecast_3hr");
    const blocks = forecastEntity?.attributes?.blocks || [];

    this.shadowRoot.textContent = "";
    this.shadowRoot.appendChild(this._styleEl());

    const card = this._el("ha-card");
    card.appendChild(this._buildHero(name, score, rating, limitingFactor, factors));
    card.appendChild(this._buildFactorGrid(factors));
    const forecast = this._buildForecast(blocks);
    if (forecast) card.appendChild(forecast);

    this.shadowRoot.appendChild(card);
  }

  _buildHero(name, score, rating, limitingFactor, factors) {
    const hero = this._el("div", { className: "hero", style: { background: this._ratingGradient(rating) } });
    hero.appendChild(this._el("div", { className: "hero-name", textContent: name }));
    hero.appendChild(this._el("div", { className: "hero-score", textContent: isNaN(score) ? "—" : String(score) }));
    hero.appendChild(this._el("div", { className: "hero-rating", textContent: this._ratingLabel(rating) }));

    if (limitingFactor) {
      const limitLabel = limitingFactor.replace(/_/g, " ");
      const limitScore = factors[limitingFactor];
      const text = `Limiting: ${limitLabel}${limitScore != null ? ` (${limitScore})` : ""}`;
      hero.appendChild(this._el("div", { className: "hero-limit", textContent: text }));
    }
    return hero;
  }

  _buildFactorGrid(factors) {
    const meta = [
      { key: "wind_speed", icon: "\uD83D\uDCA8", label: "Wind", suffix: "wind_speed", gustSuffix: "wind_gusts", dirSuffix: "wind_direction", unit: "mph" },
      { key: "air_quality", icon: "\uD83C\uDF2C\uFE0F", label: "Air Quality", suffix: "aqi", unit: "AQI" },
      { key: "temperature", icon: "\uD83C\uDF21\uFE0F", label: "Temperature", suffix: "air_temp", waterSuffix: "water_temp", unit: "\u00B0F" },
      { key: "uv_index", icon: "\u2600\uFE0F", label: "UV Index", suffix: "uv_index", unit: "" },
      { key: "visibility", icon: "\uD83D\uDC41\uFE0F", label: "Visibility", suffix: "visibility", unit: "mi" },
      { key: "precipitation", icon: "\uD83C\uDF27\uFE0F", label: "Precipitation", suffix: "precipitation", unit: "%" },
    ];

    const grid = this._el("div", { className: "factor-grid" });

    for (const f of meta) {
      if (factors[f.key] == null) continue;
      const subScore = factors[f.key];
      const entity = this._entity(f.suffix);
      const rawVal = entity ? entity.state : "—";
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

      const tile = this._el("div", { className: "factor-tile" });

      const header = this._el("div", { className: "factor-header" });
      header.appendChild(this._el("span", { className: "factor-icon", textContent: f.icon }));
      header.appendChild(this._el("span", { className: "factor-label", textContent: f.label }));
      tile.appendChild(header);

      tile.appendChild(this._el("div", { className: "factor-value", textContent: detail }));

      const barWrap = this._el("div", { className: "factor-bar-wrap" });
      barWrap.appendChild(this._el("div", { className: "factor-bar", style: { width: `${subScore}%`, background: this._scoreColor(subScore) } }));
      tile.appendChild(barWrap);

      tile.appendChild(this._el("div", { className: "factor-score", style: { color: this._scoreColor(subScore) }, textContent: `${subScore}/100` }));

      grid.appendChild(tile);
    }
    return grid;
  }

  _buildForecast(blocks) {
    if (!blocks.length) return null;

    const section = this._el("div", { className: "forecast-section" });
    section.appendChild(this._el("div", { className: "forecast-title", textContent: "Forecast" }));

    const row = this._el("div", { className: "forecast-row" });
    const now = new Date();

    blocks.forEach((b, i) => {
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

    if (this._expandedBlock != null && this._expandedBlock < blocks.length) {
      const b = blocks[this._expandedBlock];
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
      .hero-limit {
        font-size: 12px;
        opacity: 0.8;
        text-transform: capitalize;
      }

      .factor-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        padding: 12px;
      }
      @media (max-width: 350px) {
        .factor-grid { grid-template-columns: 1fr; }
      }
      .factor-tile {
        background: var(--primary-background-color, #2a2a3e);
        border-radius: 8px;
        padding: 10px;
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
