import { colorForScore } from "../utils.js";
import { CARD_STYLES } from "../styles/theme.js";
import { ensureChartReady, Chart } from "../charts/chart-loader.js";
import {
  computeStats,
  getThresholdGridColor,
  getZoneBackgrounds,
  createScoreGradient,
  resolveHAColor,
} from "../charts/chart-utils.js";

const STYLES = `
  ${CARD_STYLES}
  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .history-title {
    font-size: 1.1em;
    font-weight: 600;
  }
  .range-chips {
    display: flex;
    gap: 4px;
  }
  .range-chip {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 500;
    cursor: pointer;
    user-select: none;
    border: 1px solid var(--divider-color, #ccc);
    background: transparent;
    color: var(--secondary-text-color, #757575);
    transition: all 0.2s;
  }
  .range-chip.active {
    border-color: #4CAF50;
    background: rgba(76,175,80,0.15);
    color: #4CAF50;
  }
  .chart-container {
    position: relative;
    width: 100%;
    height: 180px;
  }
  .chart-container canvas {
    width: 100% !important;
    height: 100% !important;
  }
  .stats-bar {
    display: flex;
    gap: 8px;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 12px;
  }
  .stat-chip {
    background: var(--secondary-background-color, #f5f5f5);
    border-radius: 8px;
    padding: 8px 14px;
    text-align: center;
    min-width: 60px;
  }
  .stat-label {
    font-size: 0.7em;
    text-transform: uppercase;
    color: var(--secondary-text-color, #757575);
    letter-spacing: 0.5px;
  }
  .stat-value {
    font-size: 1.3em;
    font-weight: 600;
    margin-top: 2px;
  }
  .chart-legend {
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 8px;
    font-size: 0.8em;
    color: var(--secondary-text-color, #757575);
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
`;

const RANGE_CONFIG = {
  "7d": { days: 7, period: "hour", label: "7d" },
  "30d": { days: 30, period: "day", label: "30d" },
  "90d": { days: 90, period: "day", label: "90d" },
};

const CACHE_TTL_MS = 15 * 60 * 1000;

class PaddleHistoryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._chart = null;
    this._range = "7d";
    this._cache = new Map();
    this._loading = false;
    this._renderGen = 0;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    this._config = { show_stats: true, ...config };
    this._range = config.default_range || "7d";
  }

  set hass(hass) {
    const entity = hass.states[this._config.entity];
    const lastUpdated = entity ? entity.last_updated : null;
    const newState = entity ? `${entity.state}|${lastUpdated}` : "";

    const needsFetch = this._lastState !== newState;
    this._lastState = newState;
    this._hass = hass;

    if (needsFetch) {
      this._invalidateCacheIfStale(lastUpdated);
    }

    this._render();
  }

  getCardSize() {
    return 4;
  }

  static getStubConfig() {
    return { entity: "", default_range: "7d" };
  }

  static getConfigElement() {
    return document.createElement("paddle-history-editor");
  }

  _invalidateCacheIfStale(lastUpdated) {
    const cacheKey = `${this._config.entity}|${this._range}`;
    const cached = this._cache.get(cacheKey);
    if (cached) {
      const staleByTime = Date.now() - cached.fetchedAt > CACHE_TTL_MS;
      const staleByUpdate =
        lastUpdated && cached.lastUpdated !== lastUpdated;
      if (staleByTime || staleByUpdate) {
        this._cache.delete(cacheKey);
      }
    }
  }

  async _fetchHistory() {
    const cacheKey = `${this._config.entity}|${this._range}`;
    const cached = this._cache.get(cacheKey);
    if (cached) return cached.data;

    if (this._loading) return "loading";
    this._loading = true;

    const rangeCfg = RANGE_CONFIG[this._range];
    const now = new Date();
    const startTime = new Date(
      now.getTime() - rangeCfg.days * 24 * 60 * 60 * 1000
    );

    try {
      const result = await this._hass.callWS({
        type: "recorder/statistics_during_period",
        statistic_ids: [this._config.entity],
        period: rangeCfg.period,
        start_time: startTime.toISOString(),
        end_time: now.toISOString(),
        types: ["mean"],
      });

      const entityStats = result[this._config.entity] || [];
      // Response timestamps are ms since epoch; mean only for MEASUREMENT sensors
      const data = entityStats
        .map((s) => ({
          timestamp: new Date(s.start).toISOString(),
          value: s.mean != null ? Math.round(s.mean) : null,
        }))
        .filter((d) => d.value != null);

      const entity = this._hass.states[this._config.entity];
      this._cache.set(cacheKey, {
        data,
        lastUpdated: entity ? entity.last_updated : null,
        fetchedAt: Date.now(),
      });

      return data;
    } catch (err) {
      console.warn("paddle-history-card: Failed to fetch history", err);
      return null;
    } finally {
      this._loading = false;
    }
  }

  _setRange(range) {
    this._range = range;
    this._render();
  }

  async _render() {
    const gen = ++this._renderGen;

    try {
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

      // Header with range chips
      const header = document.createElement("div");
      header.className = "history-header";
      const title = document.createElement("div");
      title.className = "history-title";
      title.textContent = this._config.name || "Score History";
      header.appendChild(title);

      const rangeChips = document.createElement("div");
      rangeChips.className = "range-chips";
      for (const [key, cfg] of Object.entries(RANGE_CONFIG)) {
        const chip = document.createElement("span");
        chip.className = `range-chip ${this._range === key ? "active" : ""}`;
        chip.textContent = cfg.label;
        chip.addEventListener("click", () => this._setRange(key));
        rangeChips.appendChild(chip);
      }
      header.appendChild(rangeChips);
      card.appendChild(header);

      // Chart container with skeleton placeholder
      const container = document.createElement("div");
      container.className = "chart-container";
      const skeleton = document.createElement("div");
      skeleton.className = "chart-skeleton";
      container.appendChild(skeleton);
      card.appendChild(container);

      // Axis legend
      const legend = document.createElement("div");
      legend.className = "chart-legend";
      const label = document.createElement("span");
      label.textContent = "Score (0-100)";
      legend.appendChild(label);
      card.appendChild(legend);

      root.append(style, card);

      // Fetch data
      const data = await this._fetchHistory();

      // Stale render check
      if (gen !== this._renderGen) return;

      // Keep skeleton visible while loading
      if (data === "loading") return;

      // Replace skeleton
      container.textContent = "";

      if (!data || data.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent =
          data === null
            ? "Could not load history"
            : "No history data available";
        container.appendChild(empty);

        if (this._config.show_stats) {
          this._renderStats(card, {
            avg: 0,
            best: 0,
            goDays: 0,
            bestDay: "--",
          });
        }
        return;
      }

      const canvas = document.createElement("canvas");
      container.appendChild(canvas);

      ensureChartReady();
      this._buildChart(canvas, data);

      if (this._config.show_stats) {
        const stats = computeStats(data);
        this._renderStats(card, stats);
      }
    } catch (err) {
      console.warn("paddle-history-card: Render error", err);
    }
  }

  _renderStats(card, stats) {
    const bar = document.createElement("div");
    bar.className = "stats-bar";

    const items = [
      {
        label: "Avg",
        value: String(stats.avg),
        color: colorForScore(stats.avg),
      },
      {
        label: "Best",
        value: String(stats.best),
        color: colorForScore(stats.best),
      },
      { label: "Go Days", value: String(stats.goDays), color: null },
      { label: "Best Day", value: stats.bestDay, color: null },
    ];

    for (const item of items) {
      const chip = document.createElement("div");
      chip.className = "stat-chip";

      const labelEl = document.createElement("div");
      labelEl.className = "stat-label";
      labelEl.textContent = item.label;
      chip.appendChild(labelEl);

      const valueEl = document.createElement("div");
      valueEl.className = "stat-value";
      valueEl.textContent = item.value;
      if (item.color) valueEl.style.color = item.color;
      chip.appendChild(valueEl);

      bar.appendChild(chip);
    }

    card.appendChild(bar);
  }

  _buildChart(canvas, data) {
    const labels = data.map((d) => d.timestamp);
    const values = data.map((d) => d.value);

    const rangeCfg = RANGE_CONFIG[this._range];
    const timeUnit = rangeCfg.period === "hour" ? "hour" : "day";

    const zonePlugin = {
      id: "scoreZones",
      beforeDraw: (chart) => {
        const { ctx, chartArea, scales } = chart;
        if (!chartArea) return;
        const zones = getZoneBackgrounds();
        for (const zone of zones) {
          const yTop = scales.y.getPixelForValue(zone.to);
          const yBottom = scales.y.getPixelForValue(zone.from);
          ctx.save();
          ctx.fillStyle = zone.color;
          ctx.fillRect(
            chartArea.left,
            yTop,
            chartArea.width,
            yBottom - yTop
          );
          ctx.restore();
        }
      },
    };

    this._chart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Score",
            data: values,
            borderColor: "#4CAF50",
            backgroundColor: (ctx) => createScoreGradient(ctx),
            fill: true,
            tension: 0.3,
            pointRadius: rangeCfg.days <= 7 ? 2 : 0,
            pointHoverRadius: 4,
          },
        ],
      },
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
              label: (item) => `Score: ${item.raw}%`,
            },
          },
        },
        scales: {
          x: {
            type: "time",
            time: { unit: timeUnit },
            grid: { display: false },
            ticks: {
              color: resolveHAColor(
                this,
                "--secondary-text-color",
                "#757575"
              ),
              maxTicksLimit: 8,
            },
          },
          y: {
            min: 0,
            max: 100,
            grid: {
              color: (ctx) => getThresholdGridColor(ctx.tick.value),
            },
            ticks: {
              color: resolveHAColor(
                this,
                "--secondary-text-color",
                "#757575"
              ),
            },
          },
        },
      },
      plugins: [zonePlugin],
    });
  }

  disconnectedCallback() {
    if (this._chart) {
      this._chart.destroy();
      this._chart = null;
    }
  }
}

customElements.define("paddle-history-card", PaddleHistoryCard);

export { PaddleHistoryCard };
