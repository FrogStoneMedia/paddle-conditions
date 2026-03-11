import { CARD_STYLES } from "../styles/theme.js";
import { ensureChartReady, Chart } from "../charts/chart-loader.js";
import {
  CHART_METRICS,
  formatTimestamp,
  getThresholdGridColor,
  createScoreGradient,
  resolveHAColor,
} from "../charts/chart-utils.js";

const STYLES = `
  ${CARD_STYLES}
  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .chart-title {
    font-size: 1.1em;
    font-weight: 600;
  }
  .metric-chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .metric-chip {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 500;
    cursor: pointer;
    user-select: none;
    border: 1px solid;
    transition: background 0.2s, opacity 0.2s;
  }
  .metric-chip.active {
    color: white;
  }
  .metric-chip.inactive {
    background: transparent;
    opacity: 0.5;
  }
  .chart-container {
    position: relative;
    width: 100%;
    height: 200px;
  }
  .chart-container canvas {
    width: 100% !important;
    height: 100% !important;
  }
  .chart-skeleton {
    width: 100%;
    height: 100%;
    background: var(--secondary-background-color, #f0f0f0);
    border-radius: 8px;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 0.3; }
  }
  .chart-legend {
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 8px;
    font-size: 0.8em;
    color: var(--secondary-text-color, #757575);
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }
`;

class PaddleChartCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._chart = null;
    this._activeMetrics = new Set(["score"]);
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = { ...config };
    if (config.default_metrics) {
      this._activeMetrics = new Set(config.default_metrics);
    }
  }

  set hass(hass) {
    const entity = hass.states[this._config.entity];
    const newState = entity
      ? `${entity.state}|${JSON.stringify(entity.attributes)}`
      : "";
    if (this._lastState === newState) return;
    this._lastState = newState;
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { entity: "", default_metrics: ["score"] };
  }

  static getConfigElement() {
    return document.createElement("paddle-chart-editor");
  }

  _toggleMetric(key) {
    if (key === "score") return;
    if (this._activeMetrics.has(key)) {
      this._activeMetrics.delete(key);
    } else {
      this._activeMetrics.add(key);
    }
    this._render();
  }

  _render() {
    const entity = this._hass.states[this._config.entity];
    const root = this.shadowRoot;

    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
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

    const blocks = entity.attributes.blocks;
    if (!blocks || !blocks.length) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No forecast data available";
      card.appendChild(empty);
      root.append(style, card);
      return;
    }

    // Header
    const header = document.createElement("div");
    header.className = "chart-header";
    const title = document.createElement("div");
    title.className = "chart-title";
    title.textContent = this._config.name || "Forecast";
    header.appendChild(title);
    card.appendChild(header);

    // Metric toggle chips
    const chips = document.createElement("div");
    chips.className = "metric-chips";
    for (const [key, meta] of Object.entries(CHART_METRICS)) {
      const chip = document.createElement("span");
      chip.className = `metric-chip ${this._activeMetrics.has(key) ? "active" : "inactive"}`;
      chip.style.borderColor = meta.color;
      if (this._activeMetrics.has(key)) {
        chip.style.background = meta.color;
      }
      chip.textContent = meta.label;
      chip.addEventListener("click", () => this._toggleMetric(key));
      chips.appendChild(chip);
    }
    card.appendChild(chips);

    // Chart canvas
    const container = document.createElement("div");
    container.className = "chart-container";
    const canvas = document.createElement("canvas");
    container.appendChild(canvas);
    card.appendChild(container);

    // Axis legend
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    const leftLabel = document.createElement("span");
    leftLabel.className = "legend-item";
    leftLabel.textContent = "\u2190 Score (0-100)";
    legend.appendChild(leftLabel);

    const activeRight = Object.entries(CHART_METRICS)
      .filter(([k]) => k !== "score" && this._activeMetrics.has(k))
      .map(([, m]) => m.label);
    if (activeRight.length > 0) {
      const rightLabel = document.createElement("span");
      rightLabel.className = "legend-item";
      rightLabel.textContent = `${activeRight.join(", ")} \u2192`;
      legend.appendChild(rightLabel);
    }
    card.appendChild(legend);

    root.append(style, card);

    ensureChartReady();
    this._buildChart(canvas, blocks);
  }

  _buildChart(canvas, blocks) {
    const labels = blocks.map((b) => b.start);
    const datasets = [];

    // Score dataset (always)
    datasets.push({
      label: "Score",
      data: blocks.map((b) => b.score),
      borderColor: "#4CAF50",
      backgroundColor: (ctx) => createScoreGradient(ctx),
      fill: true,
      tension: 0.3,
      pointRadius: 3,
      pointHoverRadius: 5,
      yAxisID: "y",
    });

    if (this._activeMetrics.has("wind")) {
      datasets.push({
        label: "Wind (mph)",
        data: blocks.map((b) => b.wind_mph),
        borderColor: CHART_METRICS.wind.color,
        borderDash: CHART_METRICS.wind.dash,
        fill: false,
        tension: 0.3,
        pointRadius: 2,
        yAxisID: "y1",
      });
    }

    if (this._activeMetrics.has("temp")) {
      datasets.push({
        label: "Temp (\u00B0F)",
        data: blocks.map((b) => b.temp_f),
        borderColor: CHART_METRICS.temp.color,
        borderDash: CHART_METRICS.temp.dash,
        fill: false,
        tension: 0.3,
        pointRadius: 2,
        yAxisID: "y1",
      });
    }

    if (this._activeMetrics.has("uv")) {
      datasets.push({
        label: "UV",
        data: blocks.map((b) => b.uv),
        borderColor: CHART_METRICS.uv.color,
        borderDash: CHART_METRICS.uv.dash,
        fill: false,
        tension: 0.3,
        pointRadius: 2,
        yAxisID: "y1",
      });
    }

    const hasRightAxis = datasets.length > 1;

    this._chart = new Chart(canvas, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => formatTimestamp(items[0].label, "forecast"),
            },
          },
        },
        scales: {
          x: {
            type: "time",
            time: { unit: "hour" },
            grid: { display: false },
            ticks: {
              color: resolveHAColor(this, "--secondary-text-color", "#757575"),
            },
          },
          y: {
            position: "left",
            min: 0,
            max: 100,
            grid: {
              color: (ctx) => getThresholdGridColor(ctx.tick.value),
            },
            ticks: {
              color: resolveHAColor(this, "--secondary-text-color", "#757575"),
            },
          },
          ...(hasRightAxis
            ? {
                y1: {
                  position: "right",
                  grid: { display: false },
                  ticks: {
                    color: resolveHAColor(
                      this,
                      "--secondary-text-color",
                      "#757575"
                    ),
                  },
                },
              }
            : {}),
        },
      },
    });
  }

  disconnectedCallback() {
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }
}

customElements.define("paddle-chart-card", PaddleChartCard);

export { PaddleChartCard };
