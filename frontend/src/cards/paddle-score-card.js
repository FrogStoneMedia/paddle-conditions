// Paddle Score card: rating hero, factor tiles with hourly drill-down,
// 3-hour forecast strip, and a details dialog with hourly charts.

import { PaddleLocation, scoreEntities, signatureChanged, DOMAIN } from "../lib/entities.js";
import { convertBetween, convertSeries, displayUnit, formatState, numericState } from "../lib/units.js";
import { daylightWindow, recommendableBlocks, displayBlocks, bestBlock } from "../lib/daylight.js";
import { applyTheme, fillVar, normalizeRating, ratingForScore, ratingVar, RATING_TEXT, seriesColors } from "../lib/theme.js";
import { dayLabel, formatHour, formatTime } from "../lib/time.js";
import { el, button, SR_ONLY_CSS } from "../lib/dom.js";
import { DetailsDialog } from "../lib/dialog.js";
import { miniChart, MINICHART_CSS } from "../lib/minichart.js";

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const compass = (deg) => (deg == null ? "" : COMPASS[Math.round(deg / 45) % 8]);
const round = (v, digits = 0) => (v == null ? null : Number(v.toFixed(digits)));

// Factor tiles, in display order. `kind` drives unit conversion of the hourly series.
const FACTORS = [
  { key: "wind_speed", label: "Wind", sensor: "wind_speed", hourly: "hourly_wind", kind: "speed" },
  { key: "air_quality", label: "Air quality", sensor: "aqi" },
  { key: "temperature", label: "Temperature", sensor: "air_temp", hourly: "hourly_temp", kind: "temperature" },
  { key: "uv_index", label: "UV index", sensor: "uv_index", hourly: "hourly_uv" },
  { key: "visibility", label: "Visibility", sensor: "visibility" },
  { key: "precipitation", label: "Rain chance", sensor: "precipitation", hourly: "hourly_precip", unit: "%" },
  { key: "streamflow", label: "Streamflow", sensor: "streamflow" },
];

class PaddleScoreCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._dialog = new DetailsDialog(this.shadowRoot);
    this._expandedFactor = null;
    this._expandedBlock = null;
  }

  static getStubConfig(hass) {
    return { entity: scoreEntities(hass)[0] || "" };
  }

  static getConfigForm() {
    return {
      schema: [{ name: "entity", required: true, selector: { entity: { filter: [{ integration: DOMAIN, domain: "sensor" }] } } }],
      computeLabel: (s) => (s.name === "entity" ? "Paddle Score sensor" : undefined),
    };
  }

  setConfig(config) {
    if (!config?.entity) throw new Error("Choose a Paddle Score sensor");
    this._config = config;
    this._location = null;
    this._signature = null;
    if (this._hass) this.hass = this._hass; // Rebuild the location and render now.
  }

  disconnectedCallback() {
    this._dialog.close();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    if (!this._location || this._location.hass.entities !== hass.entities) {
      this._location = new PaddleLocation(hass, this._config.entity);
      this._signature = null;
    }
    this._location.hass = hass;
    const signature = this._location.signature(hass);
    if (!signatureChanged(this._signature, signature) && this._themeDark === Boolean(hass.themes?.darkMode)) return;
    this._signature = signature;
    this._themeDark = Boolean(hass.themes?.darkMode);
    this._render();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  // ── Data ──────────────────────────────────────────────

  _model() {
    const hass = this._hass;
    const loc = this._location;
    const scoreState = loc.state("paddle_score");
    const forecast = loc.state("forecast_3hr");
    const attrs = scoreState?.attributes || {};
    const score = numericState(scoreState);
    const rating = score == null ? "NONE" : normalizeRating(attrs.rating);
    const blocks = forecast?.attributes?.blocks || [];
    const window = daylightWindow(forecast, hass.states["sun.sun"]);
    const ratingState = loc.state("rating");
    return {
      hass,
      loc,
      scoreState,
      forecast,
      attrs,
      score,
      rating,
      ratingText: ratingState && ratingState.state !== "unavailable" ? formatState(hass, ratingState) : RATING_TEXT[rating],
      name: this._config.name || scoreState?.attributes?.friendly_name?.replace(/ Paddle Score$/i, "") || "Paddle spot",
      blocks,
      window,
      best: bestBlock(recommendableBlocks(blocks, window)),
    };
  }

  /** Hourly series inside the display window, converted to the sensors' display units. */
  _hourly(m) {
    const a = m.forecast?.attributes;
    if (!a?.hourly_times?.length) return null;
    const from = m.window ? m.window.sunrise.getTime() - 3600000 : -Infinity;
    const to = m.window ? m.window.sunset.getTime() + 3600000 : Infinity;
    const idx = a.hourly_times.map((t, i) => [new Date(t).getTime(), i]).filter(([t]) => t >= from && t <= to).map(([, i]) => i);
    if (idx.length < 2) return null;
    const pick = (arr) => idx.map((i) => (arr || [])[i] ?? null);
    const speedUnit = displayUnit(m.loc.state("wind_speed"), "speed");
    const tempUnit = displayUnit(m.loc.state("air_temp"), "temperature");
    return {
      times: idx.map((i) => new Date(a.hourly_times[i])),
      speedUnit,
      tempUnit,
      hourly_wind: convertSeries(pick(a.hourly_wind), "speed", speedUnit),
      hourly_gusts: convertSeries(pick(a.hourly_gusts), "speed", speedUnit),
      hourly_temp: convertSeries(pick(a.hourly_temp), "temperature", tempUnit),
      hourly_uv: pick(a.hourly_uv),
      hourly_precip: pick(a.hourly_precip),
    };
  }

  // ── Render ────────────────────────────────────────────

  /** The <ha-card> is created once; renders replace only its contents, so an open <dialog> stays attached. */
  _shell() {
    if (!this._card) {
      this._card = el("ha-card");
      this.shadowRoot.replaceChildren(el("style", { text: STYLES }), this._card);
    }
    return this._card;
  }

  _render() {
    if (!this._hass || !this._config || !this._location) return;
    applyTheme(this, this._hass);
    const m = this._model();
    const card = this._shell();
    const focused = this.shadowRoot.activeElement?.dataset?.key;

    if (!m.scoreState) {
      card.replaceChildren(el("p", { className: "empty", text: `Sensor not found: ${this._config.entity}` }));
    } else {
      card.replaceChildren(this._hero(m), this._factorGrid(m), this._forecastStrip(m) || "");
    }
    if (this._dialog.isOpen) this._dialog.update((close) => this._details(m, close));
    if (focused) this.shadowRoot.querySelector(`[data-key="${CSS.escape(focused)}"]`)?.focus();
  }

  _hero(m) {
    const scoreText = m.score == null ? "—" : String(Math.round(m.score));
    let bestText = null;
    if (m.best) {
      const start = new Date(m.best.start);
      const now = new Date();
      bestText = now >= start && now < new Date(m.best.end) ? `Best time: now (${m.best.score})` : `Best time: ${dayLabel(m.hass, start) === "Today" ? "" : `${dayLabel(m.hass, start)} `}${formatTime(m.hass, start)} (${m.best.score})`;
    }
    const hero = button(
      {
        className: "hero",
        "data-key": "hero",
        style: { background: fillVar(m.rating) },
        "aria-haspopup": "dialog",
        "aria-label": `${m.name}: score ${m.score == null ? "unavailable" : scoreText} out of 100, ${m.ratingText}.${bestText ? ` ${bestText}.` : ""} Show details.`,
        onClick: () => this._openDetails(),
      },
      [
        el("span", { className: "hero-name", text: m.name }),
        el("span", { className: "hero-date", text: dayLabel(m.hass, new Date()) }),
        el("span", { className: "hero-score", text: scoreText }),
        el("span", { className: "hero-rating", text: m.ratingText }),
        bestText && el("span", { className: "hero-best", text: bestText }),
      ],
    );
    return hero;
  }

  _factorDetail(m, f) {
    const loc = m.loc;
    let detail = formatState(m.hass, loc.state(f.sensor));
    if (f.key === "wind_speed") {
      const gust = loc.state("wind_gusts");
      if (numericState(gust) != null) detail += `, gusts ${formatState(m.hass, gust)}`;
      const dir = compass(numericState(loc.state("wind_direction")));
      if (dir) detail += ` ${dir}`;
    }
    if (f.key === "temperature") {
      const water = loc.state("water_temp");
      if (numericState(water) != null) detail += ` · water ${formatState(m.hass, water)}`;
    }
    return detail;
  }

  _factorGrid(m) {
    const factors = m.attrs.factors || {};
    const hourly = this._hourly(m);
    const grid = el("div", { className: "factor-grid", role: "list", "aria-label": "Scoring factors" });
    for (const f of FACTORS) {
      const sub = factors[f.key];
      if (sub == null) continue;
      const detail = this._factorDetail(m, f);
      const series = f.hourly && hourly ? hourly[f.hourly] : null;
      const expandable = Boolean(series?.some((v) => v != null));
      const expanded = expandable && this._expandedFactor === f.key;
      const subRating = ratingForScore(sub);
      const panelId = `ff-${f.key}`;

      const head = [
        el("span", { className: "factor-label", text: f.label }),
        el("span", { className: "factor-value", text: detail }),
        el("span", { className: "factor-bar", role: "img", "aria-label": `${f.label} score ${sub} out of 100` }, el("span", { style: { width: `${sub}%`, background: ratingVar(subRating) } })),
        el("span", { className: "factor-score", style: { color: ratingVar(subRating) }, text: `${sub}/100` }),
      ];
      const tile = el("div", { className: `factor-tile${expanded ? " expanded" : ""}`, role: "listitem" });
      if (expandable) {
        tile.append(
          button(
            {
              className: "factor-toggle",
              "data-key": `factor-${f.key}`,
              "aria-expanded": String(expanded),
              "aria-controls": panelId,
              onClick: () => {
                this._expandedFactor = expanded ? null : f.key;
                this._render();
              },
            },
            [...head, el("span", { className: "chevron", "aria-hidden": "true", text: expanded ? "▴" : "▾" })],
          ),
        );
        if (expanded) tile.append(this._hourlyStrip(m, hourly, series, f, panelId));
      } else {
        tile.append(el("div", { className: "factor-static" }, head));
      }
      grid.append(tile);
    }
    return grid;
  }

  _hourlyStrip(m, hourly, series, f, id) {
    const unit = f.kind === "speed" ? ` ${hourly.speedUnit}` : f.kind === "temperature" ? hourly.tempUnit : f.unit || "";
    const list = el("ol", { className: "hourly", id, "aria-label": `${f.label}, hourly forecast` });
    const now = Date.now();
    hourly.times.forEach((t, i) => {
      const v = series[i];
      if (v == null) return;
      const current = now >= t.getTime() && now < t.getTime() + 3600000;
      const value = f.kind ? `${Math.round(v)}${unit}` : f.unit ? `${Math.round(v)}${unit}` : String(round(v, 1));
      list.append(
        el("li", { className: `hourly-item${current ? " current" : ""}`, "aria-current": current ? "time" : null }, [
          el("span", { className: "hourly-time", text: current ? "Now" : formatHour(m.hass, t) }),
          el("span", { className: "hourly-val", text: value }),
        ]),
      );
    });
    return list;
  }

  _forecastStrip(m) {
    const blocks = displayBlocks(m.blocks, m.window);
    if (!blocks.length) return null;
    const speedUnit = displayUnit(m.loc.state("wind_speed"), "speed");
    const tempUnit = displayUnit(m.loc.state("air_temp"), "temperature");
    const now = new Date();
    const section = el("section", { className: "forecast", "aria-label": "3-hour forecast" }, [
      el("h3", { className: "forecast-title", text: `Forecast · ${dayLabel(m.hass, new Date(blocks[0].start))}` }),
    ]);
    const row = el("ol", { className: "forecast-row" });
    blocks.forEach((b, i) => {
      const start = new Date(b.start);
      const current = now >= start && now < new Date(b.end);
      const expanded = this._expandedBlock === b.start;
      const w = convertSeries([b.wind_mph], "speed", speedUnit)[0];
      const t = convertSeries([b.temp_f], "temperature", tempUnit)[0];
      const rating = normalizeRating(b.rating);
      const label = `${current ? "Now" : formatTime(m.hass, start)}: score ${b.score}, ${RATING_TEXT[rating]}${w != null ? `, wind ${Math.round(w)} ${speedUnit}` : ""}${t != null ? `, ${Math.round(t)}${tempUnit}` : ""}`;
      row.append(
        el(
          "li",
          {},
          button(
            {
              className: `block${current ? " current" : ""}${expanded ? " expanded" : ""}`,
              "data-key": `block-${b.start}`,
              "aria-expanded": String(expanded),
              "aria-controls": "block-detail",
              "aria-label": label,
              onClick: () => {
                this._expandedBlock = expanded ? null : b.start;
                this._render();
              },
            },
            [
              current && el("span", { className: "now-label", text: "NOW" }),
              el("span", { className: "block-time", text: formatTime(m.hass, start) }),
              el("span", { className: "block-score", style: { color: ratingVar(rating) }, text: String(b.score) }),
              w != null && el("span", { className: "block-detail", text: `${Math.round(w)} ${speedUnit}` }),
              t != null && el("span", { className: "block-detail", text: `${Math.round(t)}${tempUnit}` }),
            ],
          ),
        ),
      );
    });
    section.append(row);

    const open = blocks.find((b) => b.start === this._expandedBlock);
    if (open) {
      const rating = normalizeRating(open.rating);
      const g = convertSeries([open.gust_mph], "speed", speedUnit)[0];
      const rows = [
        ["Score", `${open.score} · ${RATING_TEXT[rating]}`],
        ["Wind", open.wind_mph == null ? "—" : `${Math.round(convertSeries([open.wind_mph], "speed", speedUnit)[0])} ${speedUnit}${g != null ? `, gusts ${Math.round(g)}` : ""}`],
        ["Temperature", open.temp_f == null ? "—" : `${Math.round(convertSeries([open.temp_f], "temperature", tempUnit)[0])}${tempUnit}`],
        ["UV index", open.uv == null ? "—" : String(open.uv)],
        ["Rain chance", open.precip_pct == null ? "—" : `${open.precip_pct}%`],
        ["Air quality", open.aqi == null ? "—" : `${open.aqi} AQI`],
      ];
      section.append(
        el(
          "dl",
          { className: "block-detail-panel", id: "block-detail" },
          rows.flatMap(([k, v]) => [el("dt", { text: k }), el("dd", { text: v })]),
        ),
      );
    }
    return section;
  }

  // ── Details dialog ────────────────────────────────────

  _openDetails() {
    const m = this._model();
    this._dialog.open({
      label: `${m.name} details`,
      returnFocus: () => this.shadowRoot.querySelector('[data-key="hero"]'),
      buildContent: (close) => this._details(m, close),
    });
  }

  _details(m, close) {
    const panel = el("div", { className: "panel" });
    panel.append(
      el("div", { className: "panel-top" }, [
        el("h2", { className: "panel-name", text: m.name }),
        button({ className: "close", "data-key": "close", "aria-label": "Close details", autofocus: true, onClick: close }, el("span", { "aria-hidden": "true", text: "✕" })),
      ]),
    );
    const bestText = m.best ? ` · best at ${formatTime(m.hass, new Date(m.best.start))}` : "";
    panel.append(
      el("div", { className: "panel-score", style: { color: ratingVar(m.rating) } }, [
        el("span", { className: "panel-day", text: dayLabel(m.hass, new Date()) }),
        el("span", { className: "panel-number", text: m.score == null ? "—" : String(Math.round(m.score)) }),
        el("span", { className: "panel-best", text: `${m.ratingText}${bestText}` }),
      ]),
    );
    if (m.attrs.vetoed && m.attrs.veto_reason) {
      panel.append(el("p", { className: "veto", role: "note", text: `No-go: ${m.attrs.veto_reason}` }));
    } else if (m.attrs.missing_factors?.length) {
      panel.append(el("p", { className: "note", text: `Not scored (no data): ${m.attrs.missing_factors.join(", ").replaceAll("_", " ")}` }));
    }

    const h = this._hourly(m);
    if (h) panel.append(...this._charts(m, h));
    else panel.append(el("p", { className: "note", text: "Hourly forecast isn't available yet." }));
    return panel;
  }

  _charts(m, h) {
    const hass = m.hass;
    const c = seriesColors(hass);
    const times = h.times;
    const charts = [];
    const scoreAt = times.map((t) => m.blocks.find((b) => t >= new Date(b.start) && t < new Date(b.end))?.score ?? null);
    if (scoreAt.some((v) => v != null)) {
      charts.push(
        miniChart(hass, {
          title: "Paddle score",
          times,
          yMin: 0,
          yMax: 100,
          yLabels: [{ value: 0, text: "0" }, { value: 50, text: "50" }, { value: 100, text: "100" }],
          zones: [
            { from: 70, to: 100, color: "rgba(76,175,80,.10)" },
            { from: 40, to: 70, color: "rgba(255,193,7,.08)" },
            { from: 0, to: 40, color: "rgba(244,67,54,.08)" },
          ],
          series: [{ label: "Score", values: scoreAt, color: c.score, fill: "rgba(76,175,80,.15)", format: (v) => String(v) }],
          summary: { text: m.best ? `Best ${m.best.score} at ${formatTime(hass, new Date(m.best.start))}.` : "" },
        }),
      );
    }

    const su = h.speedUnit;
    const windMax = Math.max(10, ...h.hourly_wind.filter((v) => v != null), ...h.hourly_gusts.filter((v) => v != null)) * 1.15;
    const windNow = m.loc.state("wind_speed");
    const gustNow = m.loc.state("wind_gusts");
    charts.push(
      miniChart(hass, {
        title: "Wind",
        times,
        yMin: 0,
        yMax: windMax,
        yLabels: [{ value: 0, text: "0" }, { value: windMax / 2, text: `${Math.round(windMax / 2)} ${su}` }, { value: windMax, text: `${Math.round(windMax)} ${su}` }],
        series: [
          { label: "Speed", values: h.hourly_wind, color: c.wind, format: (v) => `${Math.round(v)} ${su}` },
          { label: "Gusts", values: h.hourly_gusts, color: c.gust, dash: "5,4", format: (v) => `${Math.round(v)} ${su}` },
        ],
        summary: {
          text: `Now ${formatState(hass, windNow)}, gusting ${formatState(hass, gustNow)} ${compass(numericState(m.loc.state("wind_direction")))}.`,
          parts: [{ text: "Now " }, { strong: formatState(hass, windNow) }, { text: " gusting " }, { strong: formatState(hass, gustNow) }, { text: ` ${compass(numericState(m.loc.state("wind_direction")))}` }],
        },
      }),
    );

    const tu = h.tempUnit;
    const waterState = m.loc.state("water_temp");
    // Water may be shown in a different unit than air; plot it in the air sensor's unit.
    const water = convertBetween(numericState(waterState), "temperature", waterState?.attributes?.unit_of_measurement, tu);
    const temps = [...h.hourly_temp.filter((v) => v != null), ...(water != null ? [water] : [])];
    if (temps.length) {
      const tMin = Math.floor((Math.min(...temps) - 3) / 5) * 5;
      const tMax = Math.ceil((Math.max(...temps) + 3) / 5) * 5;
      charts.push(
        miniChart(hass, {
          title: "Temperature",
          times,
          yMin: tMin,
          yMax: tMax,
          yLabels: [{ value: tMin, text: `${tMin}${tu}` }, { value: tMax, text: `${tMax}${tu}` }],
          series: [
            { label: "Air", values: h.hourly_temp, color: c.temp, fill: "rgba(230,74,25,.10)", format: (v) => `${Math.round(v)}${tu}` },
            ...(water != null ? [{ label: "Water", values: times.map(() => water), color: c.water, dash: "5,4", format: (v) => `${Math.round(v)}${tu}` }] : []),
          ],
          summary: {
            text: `Air ${formatState(hass, m.loc.state("air_temp"))}${water != null ? `, water ${formatState(hass, waterState)}` : ""}.`,
            parts: [{ text: "Air " }, { strong: formatState(hass, m.loc.state("air_temp")) }, ...(water != null ? [{ text: " · water " }, { strong: formatState(hass, waterState) }] : [])],
          },
        }),
      );
    }

    const uv = h.hourly_uv;
    const uvValues = uv.filter((v) => v != null);
    if (uvValues.length) {
      const peak = Math.max(...uvValues);
      const peakAt = times[uv.indexOf(peak)];
      charts.push(
        miniChart(hass, {
          title: "UV index",
          times,
          yMin: 0,
          yMax: Math.max(11, peak),
          yLabels: [{ value: 0, text: "0" }, { value: 6, text: "6" }, { value: 11, text: "11" }],
          zones: [{ from: 8, to: Math.max(11, peak), color: "rgba(244,67,54,.10)" }, { from: 6, to: 8, color: "rgba(255,193,7,.10)" }],
          series: [{ label: "UV", values: uv, color: c.uv, fill: "rgba(249,168,37,.12)", format: (v) => String(round(v, 1)) }],
          summary: {
            text: `Now ${formatState(hass, m.loc.state("uv_index"))}, peak ${round(peak, 1)} at ${formatHour(hass, peakAt)}.`,
            parts: [{ text: "Now " }, { strong: formatState(hass, m.loc.state("uv_index")) }, { text: ` · peak ${round(peak, 1)} at ${formatHour(hass, peakAt)}` }],
          },
        }),
      );
    }

    const rain = h.hourly_precip;
    if (rain.some((v) => v != null)) {
      const peak = Math.max(...rain.filter((v) => v != null));
      charts.push(
        miniChart(hass, {
          title: "Rain chance",
          times,
          yMin: 0,
          yMax: 100,
          yLabels: [{ value: 0, text: "0%" }, { value: 100, text: "100%" }],
          series: [{ label: "Rain", values: rain, color: c.rain, fill: "rgba(142,36,170,.12)", format: (v) => `${v}%` }],
          summary: {
            text: `Now ${formatState(hass, m.loc.state("precipitation"))}, peak ${peak}%.`,
            parts: [{ text: "Now " }, { strong: formatState(hass, m.loc.state("precipitation")) }, { text: ` · peak ${peak}%` }],
          },
        }),
      );
    }
    return charts;
  }
}

const STYLES = `
  ${SR_ONLY_CSS}
  ${MINICHART_CSS}
  :host { display: block; }
  *, *::before, *::after { box-sizing: border-box; }
  ha-card { overflow: hidden; }
  button { font: inherit; color: inherit; background: none; border: 0; margin: 0; padding: 0; text-align: inherit; cursor: pointer; }
  :focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; border-radius: 6px; }
  .empty { padding: 16px; margin: 0; }

  .hero { display: flex; flex-direction: column; align-items: center; gap: 4px; width: 100%; padding: 22px 20px; color: #fff; text-align: center; }
  .hero:focus-visible { outline-color: #fff; outline-offset: -4px; }
  .hero-name { font-size: 14px; letter-spacing: 1.5px; text-transform: uppercase; }
  .hero-date { font-size: 13px; }
  .hero-score { font-size: 64px; font-weight: 700; line-height: 1; }
  .hero-rating { font-size: 18px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; }
  .hero-best { font-size: 14px; }

  .factor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; padding: 12px; }
  .factor-tile { border-radius: 8px; background: var(--secondary-background-color, rgba(127,127,127,.12)); border: 1px solid transparent; }
  .factor-tile.expanded { grid-column: 1 / -1; border-color: var(--primary-color); }
  .factor-toggle, .factor-static { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; width: 100%; padding: 10px; }
  .factor-label { font-size: 12px; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; }
  .chevron { grid-row: 1; grid-column: 2; font-size: 12px; color: var(--secondary-text-color); }
  .factor-value { grid-column: 1 / -1; font-size: 13px; color: var(--secondary-text-color); }
  .factor-bar { grid-column: 1; align-self: center; height: 6px; border-radius: 3px; overflow: hidden; background: var(--divider-color, rgba(127,127,127,.3)); }
  .factor-bar > span { display: block; height: 100%; border-radius: 3px; }
  .factor-score { grid-column: 2; font-size: 12px; font-weight: 700; }

  .hourly { display: flex; gap: 6px; overflow-x: auto; margin: 0; padding: 0 10px 10px; list-style: none; }
  .hourly-item { flex: 0 0 auto; min-width: 54px; padding: 6px 4px; border-radius: 6px; text-align: center; border: 1px solid var(--divider-color, transparent); }
  .hourly-item.current { border-color: var(--pc-go); }
  .hourly-time { display: block; font-size: 12px; color: var(--secondary-text-color); }
  .hourly-val { display: block; font-size: 14px; font-weight: 600; }

  .forecast { padding: 0 12px 12px; }
  .forecast-title { margin: 0 0 8px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: var(--secondary-text-color); }
  .forecast-row { display: flex; gap: 8px; overflow-x: auto; margin: 0; padding: 0 0 4px; list-style: none; }
  .block { display: flex; flex-direction: column; align-items: center; min-width: 72px; padding: 10px 8px; border-radius: 8px; border: 2px solid transparent; background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .block.current { border-color: var(--pc-go); }
  .block.expanded { border-color: var(--primary-color); }
  .now-label { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: var(--pc-go); }
  .block-time, .block-detail { font-size: 12px; color: var(--secondary-text-color); }
  .block-score { font-size: 22px; font-weight: 700; line-height: 1.2; }
  .block-detail-panel { display: grid; grid-template-columns: auto 1fr; gap: 6px 16px; margin: 8px 0 0; padding: 12px; border-radius: 8px; background: var(--secondary-background-color, rgba(127,127,127,.12)); font-size: 14px; }
  .block-detail-panel dt { color: var(--secondary-text-color); }
  .block-detail-panel dd { margin: 0; text-align: right; }

  dialog.details { overflow: hidden; width: min(500px, 100vw); max-width: 100vw; max-height: 100dvh; height: 100dvh; margin: 0 auto; padding: 0; border: 0;
    background: var(--card-background-color, var(--primary-background-color)); color: var(--primary-text-color); }
  dialog.details::backdrop { background: rgba(0,0,0,.6); }
  .panel { height: 100%; overflow-y: auto; padding: 16px; box-sizing: border-box; }
  .panel-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .panel-name { margin: 0; font-size: 13px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: var(--secondary-text-color); }
  .close { min-width: 44px; min-height: 44px; border-radius: 8px; font-size: 18px; background: var(--secondary-background-color, rgba(127,127,127,.15)); }
  .panel-score { display: flex; flex-direction: column; align-items: center; margin-bottom: 16px; }
  .panel-day { font-size: 13px; }
  .panel-number { font-size: 48px; font-weight: 700; line-height: 1; }
  .panel-best { font-size: 14px; }
  .veto, .note { margin: 0 0 12px; padding: 10px 12px; border-radius: 8px; font-size: 14px; background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .veto { color: var(--pc-no-go); font-weight: 600; }

  @media (max-width: 400px) {
    .hero-score { font-size: 48px; }
    .factor-grid { grid-template-columns: 1fr 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
  }
`;

if (!customElements.get("paddle-score-card")) customElements.define("paddle-score-card", PaddleScoreCard);

export { PaddleScoreCard };
