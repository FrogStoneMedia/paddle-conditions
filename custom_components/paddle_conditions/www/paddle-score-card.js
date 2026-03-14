class PaddleScoreCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = null;
    this._expandedBlock = null;
    this._expandedFactor = null;
    this._overlayOpen = false;
    this._boundEscHandler = (e) => { if (e.key === "Escape") this._closeOverlay(); };
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
      // Sun is up: next_setting = today's sunset, next_rising = tomorrow's sunrise
      sunset = setting;
      sunrise = new Date(rising.getTime() - 24 * 60 * 60 * 1000);
    } else {
      // Sun is down: next_rising = tomorrow's sunrise, next_setting = tomorrow's sunset
      // For displaying today's remaining data, use approximate today values
      sunrise = new Date(rising.getTime() - 24 * 60 * 60 * 1000);
      sunset = new Date(setting.getTime() - 24 * 60 * 60 * 1000);
      // Also provide tomorrow's window
      if (sunset < new Date()) {
        // Past today's sunset entirely — use tomorrow
        sunrise = rising;
        sunset = setting;
      }
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

    if (this._overlayOpen) {
      this.shadowRoot.appendChild(this._buildOverlay(name, score, rating, blocks));
    }
  }

  _dayLabel(date) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diff = (target - today) / 86400000;
    if (diff === 0) return "Today";
    if (diff === 1) return "Tomorrow";
    return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  }

  _buildHero(name, score, rating, blocks) {
    const hero = this._el("div", { className: "hero", style: { background: this._ratingGradient(rating) } });
    hero.appendChild(this._el("div", { className: "hero-name", textContent: name }));

    const dateStr = this._dayLabel(new Date());
    hero.appendChild(this._el("div", { className: "hero-date", textContent: dateStr }));
    hero.appendChild(this._el("div", { className: "hero-score", textContent: isNaN(score) ? "\u2014" : String(score) }));
    hero.appendChild(this._el("div", { className: "hero-rating", textContent: this._ratingLabel(rating) }));

    hero.style.cursor = "pointer";
    hero.addEventListener("click", () => this._openOverlay());

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

  _getHourlyData() {
    const forecastEntity = this._entity("3_hour_forecast");
    if (!forecastEntity) return null;
    const attrs = forecastEntity.attributes || {};
    const times = attrs.hourly_times;
    if (!times || !times.length) return null;
    return {
      times,
      wind: attrs.hourly_wind || [],
      temp: attrs.hourly_temp || [],
      uv: attrs.hourly_uv || [],
      precip: attrs.hourly_precip || [],
    };
  }

  _buildFactorGrid(factors, blocks) {
    const hourly = this._getHourlyData();

    // Maps factor keys to hourly data arrays for drill-down
    const hourlyFieldMap = {
      wind_speed: { arr: hourly?.wind, unit: "mph", label: "Wind" },
      temperature: { arr: hourly?.temp, unit: "\u00B0F", label: "Temp" },
      uv_index: { arr: hourly?.uv, unit: "", label: "UV" },
      precipitation: { arr: hourly?.precip, unit: "%", label: "Precip" },
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
      const hfm = hourlyFieldMap[f.key];
      const hasForecast = hfm && hfm.arr && hfm.arr.length > 0;

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

      // Hourly drill-down when expanded
      if (isExpanded && hasForecast) {
        tile.appendChild(this._buildHourlyForecast(hourly.times, hfm));
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

  _buildHourlyForecast(times, hfm) {
    const container = this._el("div", { className: "factor-forecast" });
    const now = new Date();
    const win = this._getSunWindow();

    // Filter to sunrise-1h through sunset+1h
    const from = win ? new Date(win.sunrise.getTime() - 60 * 60 * 1000) : null;
    const to = win ? new Date(win.sunset.getTime() + 60 * 60 * 1000) : null;

    let lastDay = null;
    for (let i = 0; i < times.length && i < hfm.arr.length; i++) {
      const t = new Date(times[i]);
      if (from && (t < from || t > to)) continue;

      const val = hfm.arr[i];
      if (val == null) continue;

      // Insert day divider when date changes
      const dayKey = t.toDateString();
      if (lastDay !== null && dayKey !== lastDay) {
        const divider = this._el("div", { className: "ff-day-divider", textContent: this._dayLabel(t) });
        container.appendChild(divider);
      }
      lastDay = dayKey;

      const isCurrent = now >= t && now < new Date(t.getTime() + 60 * 60 * 1000);
      const displayVal = hfm.unit === "\u00B0F" ? `${Math.round(val)}${hfm.unit}` :
                         hfm.unit ? `${Math.round(val)} ${hfm.unit}` :
                         String(Math.round(val * 10) / 10);
      const timeLabel = t.toLocaleTimeString([], { hour: "numeric" });

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
    const forecastDay = displayBlocks.length > 0 ? this._dayLabel(new Date(displayBlocks[0].start)) : "";
    section.appendChild(this._el("div", { className: "forecast-title", textContent: `Forecast \u2014 ${forecastDay}` }));

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

  // ── Overlay ───────────────────────────────────────────────

  _openOverlay() {
    this._overlayOpen = true;
    document.addEventListener("keydown", this._boundEscHandler);
    this._render();
    requestAnimationFrame(() => {
      const el = this.shadowRoot.querySelector(".overlay");
      if (el) el.classList.add("overlay-visible");
    });
  }

  _closeOverlay() {
    const el = this.shadowRoot.querySelector(".overlay");
    if (el) {
      el.classList.remove("overlay-visible");
      el.addEventListener("transitionend", () => {
        this._overlayOpen = false;
        document.removeEventListener("keydown", this._boundEscHandler);
        this._render();
      }, { once: true });
    } else {
      this._overlayOpen = false;
      document.removeEventListener("keydown", this._boundEscHandler);
    }
  }

  _svgEl(tag, attrs) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }

  _getOverlayHourlyData() {
    const hourly = this._getHourlyData();
    if (!hourly) return null;

    const win = this._getSunWindow();
    const from = win ? new Date(win.sunrise.getTime() - 60 * 60 * 1000) : null;
    const to = win ? new Date(win.sunset.getTime() + 60 * 60 * 1000) : null;

    const indices = [];
    for (let i = 0; i < hourly.times.length; i++) {
      const t = new Date(hourly.times[i]);
      if (from && (t < from || t > to)) continue;
      indices.push(i);
    }
    if (indices.length < 2) return null;

    return {
      indices,
      times: indices.map(i => new Date(hourly.times[i])),
      wind: indices.map(i => hourly.wind[i] ?? 0),
      temp: indices.map(i => hourly.temp[i] ?? 0),
      uv: indices.map(i => hourly.uv[i] ?? 0),
      precip: indices.map(i => hourly.precip[i] ?? 0),
      sunrise: win?.sunrise,
      sunset: win?.sunset,
    };
  }

  _getHourlyScores(blocks, times) {
    if (!blocks.length || !times.length) return times.map(() => null);
    return times.map(t => {
      for (const b of blocks) {
        const bs = new Date(b.start);
        const be = new Date(b.end);
        if (t >= bs && t < be) return b.score;
      }
      return null;
    });
  }

  _buildOverlayChartSvg({ values, values2, color, color2, dash2, fillColor, yMin, yMax, times, zones }) {
    const W = 200, H = 70;
    const svg = this._svgEl("svg", { width: "100%", height: String(H), viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
    svg.style.cssText = "position:absolute;top:0;left:0";

    if (zones) {
      for (const z of zones) {
        const y1 = H - ((z.from - yMin) / (yMax - yMin)) * H;
        const y2 = H - ((z.to - yMin) / (yMax - yMin)) * H;
        svg.appendChild(this._svgEl("rect", { x: "0", y: String(Math.min(y1, y2)), width: String(W), height: String(Math.abs(y2 - y1)), fill: z.color }));
      }
    }

    const toPoints = (vals) => {
      return vals.map((v, i) => {
        if (v == null) return null;
        const x = (i / (vals.length - 1)) * W;
        const y = H - ((v - yMin) / (yMax - yMin)) * H;
        return `${x.toFixed(1)},${Math.max(0, Math.min(H, y)).toFixed(1)}`;
      }).filter(Boolean).join(" ");
    };

    if (fillColor && values.length > 1) {
      const pts = values.map((v, i) => {
        if (v == null) return null;
        const x = (i / (values.length - 1)) * W;
        const y = H - ((v - yMin) / (yMax - yMin)) * H;
        return { x: x.toFixed(1), y: Math.max(0, Math.min(H, y)).toFixed(1) };
      }).filter(Boolean);
      if (pts.length > 1) {
        const d = `M${pts[0].x},${pts[0].y} ${pts.slice(1).map(p => `L${p.x},${p.y}`).join(" ")} L${pts[pts.length - 1].x},${H} L${pts[0].x},${H} Z`;
        svg.appendChild(this._svgEl("path", { d, fill: fillColor }));
      }
    }

    const pts1 = toPoints(values);
    if (pts1) {
      svg.appendChild(this._svgEl("polyline", {
        points: pts1, fill: "none", stroke: color, "stroke-width": "2",
        "stroke-linecap": "round", "stroke-linejoin": "round",
      }));
    }

    if (values2) {
      const pts2 = toPoints(values2);
      if (pts2) {
        const attrs = {
          points: pts2, fill: "none", stroke: color2, "stroke-width": "1.5",
          "stroke-linecap": "round", "stroke-linejoin": "round",
        };
        if (dash2) attrs["stroke-dasharray"] = dash2;
        svg.appendChild(this._svgEl("polyline", attrs));
      }
    }

    const now = new Date();
    if (times.length > 1 && now >= times[0] && now <= times[times.length - 1]) {
      const span = times[times.length - 1] - times[0];
      const nx = ((now - times[0]) / span) * W;
      svg.appendChild(this._svgEl("line", {
        x1: nx.toFixed(1), y1: "0", x2: nx.toFixed(1), y2: String(H),
        stroke: "rgba(255,255,255,0.4)", "stroke-width": "1.5",
      }));
    }

    return svg;
  }

  _summaryEl(template) {
    const el = this._el("div", { className: "ov-summary" });
    const parts = template.split(/(<strong>.*?<\/strong>)/);
    for (const part of parts) {
      const m = part.match(/^<strong>(.*)<\/strong>$/);
      if (m) {
        el.appendChild(this._el("strong", { textContent: m[1] }));
      } else {
        el.appendChild(document.createTextNode(part));
      }
    }
    return el;
  }

  _buildOverlayChartCard({ title, unitLabel, legend, yLabels, values, values2, color, color2, dash2, fillColor, yMin, yMax, times, zones, summary, sunTimes, windArrows }) {
    const card = this._el("div", { className: "ov-chart" });
    const header = this._el("div", { className: "ov-chart-header" });
    header.appendChild(this._el("div", { className: "ov-chart-title", textContent: title }));

    if (legend) {
      const leg = this._el("div", { className: "ov-chart-legend" });
      for (const l of legend) {
        leg.appendChild(this._el("span", { style: { color: l.color }, textContent: l.text }));
      }
      header.appendChild(leg);
    } else if (unitLabel) {
      header.appendChild(this._el("div", { className: "ov-chart-unit", textContent: unitLabel }));
    }
    card.appendChild(header);

    const marginLeft = Math.max(...yLabels.map(l => l.text.length)) * 7 + 6;
    const area = this._el("div", { className: "ov-chart-area", style: { marginLeft: `${marginLeft}px` } });

    for (const l of yLabels) {
      const pct = ((l.value - yMin) / (yMax - yMin)) * 100;
      const topPct = 100 - pct;
      area.appendChild(this._el("div", {
        className: "ov-ylabel",
        style: { top: `${topPct}%`, left: `-${marginLeft}px` },
        textContent: l.text,
      }));
    }

    area.appendChild(this._el("div", { className: "ov-gridline", style: { top: "0" } }));
    area.appendChild(this._el("div", { className: "ov-gridline ov-gridline-dash", style: { top: "50%" } }));
    area.appendChild(this._el("div", { className: "ov-gridline", style: { bottom: "0" } }));

    const now = new Date();
    if (times.length > 1 && now >= times[0] && now <= times[times.length - 1]) {
      const span = times[times.length - 1] - times[0];
      const pct = ((now - times[0]) / span) * 100;
      area.appendChild(this._el("div", { className: "ov-now-label", style: { left: `${pct}%` }, textContent: "now" }));
    }

    if (zones) {
      for (const z of zones) {
        if (!z.label) continue;
        const pct = 100 - ((z.to - yMin) / (yMax - yMin)) * 100;
        area.appendChild(this._el("div", {
          className: "ov-zone-label",
          style: { top: `${Math.max(2, pct + 2)}%`, color: z.labelColor || "#666" },
          textContent: z.label,
        }));
      }
    }

    area.appendChild(this._buildOverlayChartSvg({ values, values2, color, color2, dash2, fillColor, yMin, yMax, times, zones }));
    card.appendChild(area);

    const timeAxis = this._el("div", { className: "ov-time-axis", style: { marginLeft: `${marginLeft}px` } });
    const step = Math.max(1, Math.floor(times.length / 5));
    for (let i = 0; i < times.length; i += step) {
      timeAxis.appendChild(this._el("span", { textContent: times[i].toLocaleTimeString([], { hour: "numeric" }) }));
    }
    if (times.length % step !== 1) {
      timeAxis.appendChild(this._el("span", { textContent: times[times.length - 1].toLocaleTimeString([], { hour: "numeric" }) }));
    }
    card.appendChild(timeAxis);

    if (sunTimes) {
      const sunRow = this._el("div", { className: "ov-sun-row", style: { marginLeft: `${marginLeft}px` } });
      const fmtTime = (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      sunRow.appendChild(this._el("span", { style: { color: "#FFA726" }, textContent: `\u2600\uFE0E ${fmtTime(sunTimes.sunrise)}` }));
      sunRow.appendChild(this._el("span", {}));
      sunRow.appendChild(this._el("span", { style: { color: "#FF7043" }, textContent: `\u263E ${fmtTime(sunTimes.sunset)}` }));
      card.appendChild(sunRow);
    }

    if (windArrows && windArrows.length) {
      const arrowRow = this._el("div", { className: "ov-arrow-row", style: { marginLeft: `${marginLeft}px` } });
      const arrowStep = Math.max(1, Math.floor(windArrows.length / 8));
      for (let i = 0; i < windArrows.length; i += arrowStep) {
        arrowRow.appendChild(this._el("span", { textContent: windArrows[i] }));
      }
      card.appendChild(arrowRow);
    }

    if (summary) {
      card.appendChild(this._summaryEl(summary));
    }

    return card;
  }

  _windDirArrow(deg) {
    if (deg == null) return "";
    const arrows = ["\u2191", "\u2197", "\u2192", "\u2198", "\u2193", "\u2199", "\u2190", "\u2196"];
    return arrows[Math.round(((deg + 180) % 360) / 45) % 8];
  }

  _buildOverlay(name, score, rating, blocks) {
    const overlay = this._el("div", { className: "overlay" });
    const backdrop = this._el("div", { className: "overlay-backdrop" });
    backdrop.addEventListener("click", () => this._closeOverlay());
    overlay.appendChild(backdrop);

    const content = this._el("div", { className: "overlay-content" });

    // Top bar with name and close button
    const topBar = this._el("div", { className: "ov-topbar" });
    topBar.appendChild(this._el("div", { className: "ov-name", textContent: name }));
    const closeBtn = this._el("div", { className: "ov-close", textContent: "\u2715" });
    closeBtn.addEventListener("click", () => this._closeOverlay());
    topBar.appendChild(closeBtn);
    content.appendChild(topBar);

    // Centered score header
    const header = this._el("div", { className: "ov-header" });
    header.appendChild(this._el("div", { className: "ov-date", style: { color: this._scoreColor(score) }, textContent: this._dayLabel(new Date()) }));
    header.appendChild(this._el("div", { className: "ov-score", style: { color: this._scoreColor(score) }, textContent: isNaN(score) ? "\u2014" : String(score) }));

    const safeBlocks = blocks.length ? this._filterDaylightBlocks(blocks) : [];
    const bestBlock = safeBlocks.length ? safeBlocks.reduce((a, b) => b.score > a.score ? b : a, safeBlocks[0]) : null;
    let bestText = this._ratingLabel(rating);
    if (bestBlock) {
      const t = new Date(bestBlock.start);
      const now = new Date();
      const inBlock = now >= t && now < new Date(bestBlock.end);
      bestText += inBlock ? " \u2014 Best now" : ` \u2014 Best at ${t.toLocaleTimeString([], { hour: "numeric" })}`;
    }
    header.appendChild(this._el("div", { className: "ov-best", style: { color: this._scoreColor(score) }, textContent: bestText }));
    content.appendChild(header);

    const data = this._getOverlayHourlyData();
    if (data) {
      const { times, wind, temp, uv, precip, sunrise, sunset } = data;
      const scores = this._getHourlyScores(blocks, times);

      const validScores = scores.filter(s => s != null);
      if (validScores.length > 0) {
        content.appendChild(this._buildOverlayChartCard({
          title: "PADDLE SCORE", unitLabel: "0\u2013100",
          yLabels: [{ value: 0, text: "0" }, { value: 50, text: "50" }, { value: 100, text: "100" }],
          values: scores, color: "#4CAF50",
          fillColor: "rgba(76,175,80,0.15)",
          yMin: 0, yMax: 100, times,
          zones: [
            { from: 70, to: 100, color: "rgba(76,175,80,0.04)", label: "GO", labelColor: "rgba(76,175,80,0.5)" },
            { from: 40, to: 70, color: "rgba(255,193,7,0.03)", label: "CAUTION", labelColor: "rgba(255,193,7,0.4)" },
            { from: 0, to: 40, color: "rgba(244,67,54,0.03)", label: "NO GO", labelColor: "rgba(244,67,54,0.4)" },
          ],
          sunTimes: sunrise && sunset ? { sunrise, sunset } : null,
        }));
      }

      const windMax = Math.max(25, ...wind) + 5;
      const gustEntity = this._entity("wind_gusts");
      const dirEntity = this._entity("wind_direction");
      const currentWind = this._entity("wind_speed");
      let windSummary = "";
      if (currentWind) {
        windSummary = `Now: <strong>${currentWind.state} mph</strong>`;
        if (gustEntity?.state) windSummary += ` gusting <strong>${gustEntity.state} mph</strong>`;
        if (dirEntity?.state) windSummary += ` \u00B7 ${this._degToCompass(parseFloat(dirEntity.state))}`;
      }
      const windArrows = times.map(() => "");
      if (dirEntity?.state) {
        const deg = parseFloat(dirEntity.state);
        for (let i = 0; i < windArrows.length; i++) windArrows[i] = this._windDirArrow(deg);
      }

      content.appendChild(this._buildOverlayChartCard({
        title: "WIND",
        legend: [{ color: "#2196F3", text: "\u2014 Speed" }, { color: "#FF9800", text: "\u2504 Gusts" }],
        yLabels: [
          { value: 0, text: "0" },
          { value: Math.round(windMax / 2), text: `${Math.round(windMax / 2)} mph` },
          { value: windMax, text: `${windMax} mph` },
        ],
        values: wind, color: "#2196F3",
        values2: wind.map(w => w * 1.4), color2: "#FF9800", dash2: "6,4",
        yMin: 0, yMax: windMax, times,
        summary: windSummary,
        windArrows,
      }));

      const allTemps = [...temp];
      const waterEntity = this._entity("water_temperature");
      const waterVal = waterEntity?.state !== "unavailable" ? parseFloat(waterEntity?.state) : null;
      const waterLine = waterVal != null && !isNaN(waterVal) ? times.map(() => waterVal) : null;
      if (waterVal != null && !isNaN(waterVal)) allTemps.push(waterVal);
      const tMin = Math.floor((Math.min(...allTemps) - 5) / 5) * 5;
      const tMax = Math.ceil((Math.max(...allTemps) + 5) / 5) * 5;
      let tempSummary = "";
      const airEntity = this._entity("air_temperature");
      if (airEntity) {
        tempSummary = `Air: <strong>${airEntity.state}\u00B0F</strong>`;
        if (waterVal != null && !isNaN(waterVal)) tempSummary += ` \u00B7 Water: <strong>${waterVal}\u00B0F</strong>`;
      }

      content.appendChild(this._buildOverlayChartCard({
        title: "TEMPERATURE",
        legend: [{ color: "#FF5722", text: "\u2014 Air" }, ...(waterLine ? [{ color: "#00BCD4", text: "\u2504 Water" }] : [])],
        yLabels: [
          { value: tMin, text: `${tMin}\u00B0F` },
          { value: Math.round((tMin + tMax) / 2), text: `${Math.round((tMin + tMax) / 2)}\u00B0F` },
          { value: tMax, text: `${tMax}\u00B0F` },
        ],
        values: temp, color: "#FF5722", fillColor: "rgba(255,87,34,0.1)",
        values2: waterLine, color2: "#00BCD4", dash2: "6,4",
        yMin: tMin, yMax: tMax, times,
        summary: tempSummary,
      }));

      const uvMax = Math.max(11, ...uv);
      const uvEntity = this._entity("uv_index");
      const peakUV = Math.max(...uv);
      const peakIdx = uv.indexOf(peakUV);
      const peakTime = times[peakIdx]?.toLocaleTimeString([], { hour: "numeric" });
      let uvSummary = "";
      if (uvEntity) {
        const val = parseFloat(uvEntity.state);
        const label = val >= 11 ? "Extreme" : val >= 8 ? "Very High" : val >= 6 ? "High" : val >= 3 ? "Moderate" : "Low";
        uvSummary = `Now: <strong>${uvEntity.state}</strong> (${label})`;
        if (peakTime) uvSummary += ` \u00B7 Peak: <strong>${peakUV.toFixed(1)}</strong> at ${peakTime}`;
      }

      content.appendChild(this._buildOverlayChartCard({
        title: "UV INDEX", unitLabel: "0\u201311+",
        yLabels: [{ value: 0, text: "0" }, { value: 6, text: "6" }, { value: 11, text: "11" }],
        values: uv, color: "#FFC107", fillColor: "rgba(255,193,7,0.1)",
        yMin: 0, yMax: uvMax, times,
        zones: [
          { from: 8, to: uvMax, color: "rgba(244,67,54,0.08)", label: "Very High", labelColor: "rgba(244,67,54,0.5)" },
          { from: 6, to: 8, color: "rgba(255,193,7,0.06)", label: "High", labelColor: "rgba(255,193,7,0.4)" },
        ],
        summary: uvSummary,
      }));

      const precipEntity = this._entity("precipitation_chance");
      const maxPrecip = Math.max(...precip);
      let precipSummary = "";
      if (precipEntity) {
        precipSummary = `Now: <strong>${precipEntity.state}%</strong>`;
        if (maxPrecip > 20) {
          const maxIdx = precip.indexOf(maxPrecip);
          const maxTime = times[maxIdx]?.toLocaleTimeString([], { hour: "numeric" });
          precipSummary += ` \u00B7 Peak: <strong>${maxPrecip}%</strong> at ${maxTime}`;
        }
      }

      content.appendChild(this._buildOverlayChartCard({
        title: "PRECIPITATION", unitLabel: "Probability %",
        yLabels: [{ value: 0, text: "0%" }, { value: 50, text: "50%" }, { value: 100, text: "100%" }],
        values: precip, color: "#9C27B0", fillColor: "rgba(156,39,176,0.1)",
        yMin: 0, yMax: 100, times,
        summary: precipSummary,
      }));
    }

    content.appendChild(this._el("div", { className: "ov-footer", textContent: "Tap anywhere outside or swipe down to close" }));

    let touchStartY = 0;
    content.addEventListener("touchstart", (e) => { touchStartY = e.touches[0].clientY; }, { passive: true });
    content.addEventListener("touchend", (e) => {
      const dy = e.changedTouches[0].clientY - touchStartY;
      if (dy > 80) this._closeOverlay();
    }, { passive: true });

    overlay.appendChild(content);
    return overlay;
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
      .hero-date {
        font-size: 12px;
        opacity: 0.75;
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
      .ff-day-divider {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        font-size: 10px;
        font-weight: 600;
        color: var(--primary-color, #4fc3f7);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 0 4px;
        writing-mode: vertical-rl;
        text-orientation: mixed;
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

      /* ── Overlay ──────────────────────────────── */
      .overlay {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.3s ease;
      }
      .overlay-visible { opacity: 1; }
      .overlay-backdrop {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.7);
      }
      .overlay-content {
        position: absolute;
        top: 0; bottom: 0;
        left: 50%;
        transform: translateX(-50%) translateY(40px);
        width: 100%;
        max-width: 500px;
        overflow-y: auto;
        background: #1e1e2e;
        padding: 16px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        color: #ccc;
        transition: transform 0.3s ease;
      }
      .overlay-visible .overlay-content { transform: translateX(-50%) translateY(0); }
      .ov-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }
      .ov-close {
        font-size: 18px;
        color: #aaa;
        cursor: pointer;
        padding: 6px 10px;
        border-radius: 6px;
        background: rgba(255,255,255,0.08);
        line-height: 1;
      }
      .ov-close:hover { color: #fff; background: rgba(255,255,255,0.15); }
      .ov-header {
        text-align: center;
        margin-bottom: 16px;
      }
      .ov-name {
        font-size: 11px;
        text-transform: uppercase;
        color: #888;
        letter-spacing: 1px;
      }
      .ov-date {
        font-size: 13px;
        margin-bottom: 2px;
      }
      .ov-score {
        font-size: 48px;
        font-weight: bold;
        line-height: 1;
      }
      .ov-best {
        font-size: 12px;
        margin-top: 4px;
      }
      .ov-chart {
        background: #2a2a3e;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
      }
      .ov-chart-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        margin-bottom: 8px;
      }
      .ov-chart-title {
        color: #aaa;
        font-size: 11px;
        font-weight: 600;
      }
      .ov-chart-unit {
        color: #666;
        font-size: 10px;
      }
      .ov-chart-legend {
        display: flex;
        gap: 12px;
        font-size: 10px;
      }
      .ov-chart-area {
        position: relative;
        height: 70px;
      }
      .ov-ylabel {
        position: absolute;
        font-size: 9px;
        color: #666;
        transform: translateY(-50%);
        white-space: nowrap;
      }
      .ov-gridline {
        position: absolute;
        left: 0; right: 0;
        height: 1px;
        background: #333;
      }
      .ov-gridline-dash {
        border-top: 1px dashed #444;
        background: none;
      }
      .ov-now-label {
        position: absolute;
        top: -12px;
        font-size: 7px;
        color: rgba(255,255,255,0.5);
        transform: translateX(-50%);
      }
      .ov-zone-label {
        position: absolute;
        right: 4px;
        font-size: 8px;
      }
      .ov-time-axis {
        display: flex;
        justify-content: space-between;
        font-size: 9px;
        color: #888;
        margin-top: 6px;
      }
      .ov-sun-row {
        display: flex;
        justify-content: space-between;
        font-size: 8px;
        color: #555;
        margin-top: 2px;
      }
      .ov-arrow-row {
        display: flex;
        justify-content: space-around;
        margin-top: 4px;
        font-size: 10px;
        color: #555;
      }
      .ov-summary {
        text-align: center;
        font-size: 10px;
        color: #ccc;
        margin-top: 6px;
      }
      .ov-summary strong {
        font-weight: 600;
      }
      .ov-footer {
        text-align: center;
        padding: 12px;
        color: #666;
        font-size: 11px;
      }
    `;
    return style;
  }
}

if (!customElements.get("paddle-score-card")) {
  customElements.define("paddle-score-card", PaddleScoreCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "paddle-score-card",
  name: "Paddle Score Card",
  description: "Paddling conditions score with factor breakdown and forecast",
});
