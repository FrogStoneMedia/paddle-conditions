class PaddleSpotsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
  }

  setConfig(config) {
    if (!config.entities || !config.entities.length) {
      throw new Error("entities array is required");
    }
    this._config = config;
  }

  set hass(hass) {
    const prev = this._hass;
    this._hass = hass;
    if (!prev || this._entitiesChanged(prev)) this._render();
  }

  _entitiesChanged(prev) {
    for (const eid of this._config.entities) {
      if (prev.states[eid] !== this._hass.states[eid]) return true;
    }
    return false;
  }

  getCardSize() { return 2; }

  _scoreColor(score) {
    if (score == null) return "#999";
    if (score >= 70) return "#66BB6A";
    if (score >= 40) return "#FFD600";
    return "#EF5350";
  }

  _ratingGradient(rating) {
    const gradients = {
      GO: "linear-gradient(135deg, #2E7D32, #43A047)",
      CAUTION: "linear-gradient(135deg, #E65100, #F57C00)",
      NO_GO: "linear-gradient(135deg, #C62828, #E53935)",
    };
    return gradients[rating] || "linear-gradient(135deg, #424242, #616161)";
  }

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

  _render() {
    if (!this._hass || !this._config) return;

    this.shadowRoot.textContent = "";
    this.shadowRoot.appendChild(this._styleEl());

    const card = this._el("ha-card");
    const row = this._el("div", { className: "spots-row" });

    for (const eid of this._config.entities) {
      const entity = this._hass.states[eid];
      if (!entity) continue;

      const score = parseInt(entity.state, 10);
      const attrs = entity.attributes || {};
      const rating = attrs.rating || "NO_GO";
      const name = (attrs.friendly_name || "").replace(/ Paddle Score$/i, "");

      const ratingText = { GO: "Good to go", CAUTION: "Caution", NO_GO: "Not recommended" }[rating] || "Unknown";
      const badge = this._el("div", {
        className: "spot-badge",
        style: { background: this._ratingGradient(rating) },
        role: "button",
        tabindex: "0",
        "aria-label": `${name}: ${isNaN(score) ? "unavailable" : score} out of 100, ${ratingText}`,
      });

      badge.appendChild(this._el("div", {
        className: "badge-score",
        style: { color: this._scoreColor(score) },
        textContent: isNaN(score) ? "\u2014" : String(score),
      }));
      badge.appendChild(this._el("div", { className: "badge-name", textContent: name }));

      const clickHandler = () => {
        const cards = document.querySelectorAll("paddle-score-card");
        for (const c of cards) {
          if (c._config && c._config.entity === eid) {
            c.scrollIntoView({ behavior: "smooth", block: "start" });
            break;
          }
        }
      };
      badge.addEventListener("click", clickHandler);
      badge.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); clickHandler(); }
      });

      row.appendChild(badge);
    }

    card.appendChild(row);
    this.shadowRoot.appendChild(card);
  }

  _styleEl() {
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      ha-card {
        background: var(--card-background-color, #1e1e2e);
        border-radius: 12px;
        padding: 12px;
      }
      .spots-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .spot-badge {
        flex: 1;
        min-width: 100px;
        text-align: center;
        padding: 16px 12px;
        border-radius: 10px;
        cursor: pointer;
        transition: transform 0.15s, box-shadow 0.15s;
      }
      .spot-badge:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      }
      .badge-score {
        font-size: 32px;
        font-weight: 700;
        line-height: 1;
        margin-bottom: 4px;
        color: #fff;
      }
      .badge-name {
        font-size: 11px;
        color: rgba(255,255,255,0.85);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .spot-badge:focus-visible {
        outline: 2px solid #03a9f4;
        outline-offset: 2px;
      }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
          animation-duration: 0.01ms !important;
          transition-duration: 0.01ms !important;
        }
      }
    `;
    return style;
  }
}

if (!customElements.get("paddle-spots-card")) {
  customElements.define("paddle-spots-card", PaddleSpotsCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "paddle-spots-card",
  name: "Paddle Spots Card",
  description: "Multi-location paddle score comparison",
});
