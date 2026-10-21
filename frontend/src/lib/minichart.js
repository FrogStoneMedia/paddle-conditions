// Small SVG line charts for the details dialog, each with a text alternative:
// a one-line summary for the image role and a hidden table of the values.

import { el, svg } from "./dom.js";
import { formatHour } from "./time.js";

const W = 200;
const H = 70;

function y(v, yMin, yMax) {
  return Math.max(0, Math.min(H, H - ((v - yMin) / (yMax - yMin)) * H));
}

function points(values, yMin, yMax) {
  const n = values.length;
  return values
    .map((v, i) => (v == null ? null : `${((i / Math.max(1, n - 1)) * W).toFixed(1)},${y(v, yMin, yMax).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
}

/**
 * series: [{ label, values, color, dash?, fill?, format(v) }]
 * zones:  [{ from, to, color, label? }]
 */
export function miniChart(hass, { title, series, times, yMin, yMax, yLabels, zones = [], summary, now = new Date() }) {
  const figure = el("figure", { className: "mc" });

  const legend = el(
    "div",
    { className: "mc-legend", "aria-hidden": "true" },
    // Colour lives in the swatch; the label keeps the theme's text colour for contrast.
    series.map((s) => el("span", {}, [el("span", { className: "mc-swatch", style: { color: s.color }, text: s.dash ? "┄" : "—" }), ` ${s.label}`])),
  );
  figure.append(el("figcaption", { className: "mc-head" }, [el("span", { className: "mc-title", text: title }), legend]));

  const area = el("div", { className: "mc-area", role: "img", "aria-label": `${title}. ${summary?.text || ""}`.trim() });
  for (const l of yLabels) {
    area.append(el("span", { className: "mc-ylabel", "aria-hidden": "true", style: { top: `${(y(l.value, yMin, yMax) / H) * 100}%` }, text: l.text }));
  }
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", class: "mc-svg", "aria-hidden": "true", focusable: "false" });
  for (const z of zones) {
    const top = y(z.to, yMin, yMax);
    chart.append(svg("rect", { x: 0, y: top, width: W, height: Math.abs(y(z.from, yMin, yMax) - top), fill: z.color }));
  }
  for (const s of series) {
    const pts = points(s.values, yMin, yMax);
    if (!pts) continue;
    if (s.fill) {
      const first = pts.split(" ")[0].split(",")[0];
      const last = pts.split(" ").at(-1).split(",")[0];
      chart.append(svg("polygon", { points: `${first},${H} ${pts} ${last},${H}`, fill: s.fill }));
    }
    const line = { points: pts, fill: "none", stroke: s.color, "stroke-width": s.dash ? 1.5 : 2, "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke" };
    if (s.dash) line["stroke-dasharray"] = s.dash;
    chart.append(svg("polyline", line));
  }
  if (times.length > 1 && now >= times[0] && now <= times.at(-1)) {
    const x = ((now - times[0]) / (times.at(-1) - times[0])) * W;
    chart.append(svg("line", { x1: x, x2: x, y1: 0, y2: H, class: "mc-now", "vector-effect": "non-scaling-stroke" }));
  }
  area.append(chart);
  figure.append(area);

  // Labels sit at their sample's x position, endpoints included.
  const axis = el("div", { className: "mc-axis", "aria-hidden": "true" });
  const n = times.length;
  const ticks = n <= 1 ? [0] : [...new Set([0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(f * (n - 1))))];
  for (const i of ticks) {
    const pos = n <= 1 ? 0 : (i / (n - 1)) * 100;
    axis.append(el("span", { style: { left: `${pos}%` }, className: i === 0 ? "first" : i === n - 1 ? "last" : null, text: formatHour(hass, times[i]) }));
  }
  figure.append(axis);

  if (summary?.parts) {
    figure.append(
      el(
        "p",
        { className: "mc-summary" },
        summary.parts.map((p) => (p.strong ? el("strong", { text: p.strong }) : p.text)),
      ),
    );
  }

  // Data table for screen readers.
  const table = el("table", { className: "sr-only" }, [
    el("caption", { text: `${title}, hourly` }),
    el("thead", {}, el("tr", {}, [el("th", { scope: "col", text: "Time" }), ...series.map((s) => el("th", { scope: "col", text: s.label }))])),
    el(
      "tbody",
      {},
      times.map((t, i) =>
        el("tr", {}, [
          el("th", { scope: "row", text: formatHour(hass, t) }),
          ...series.map((s) => el("td", { text: s.values[i] == null ? "—" : s.format(s.values[i]) })),
        ]),
      ),
    ),
  ]);
  figure.append(table);
  return figure;
}

export const MINICHART_CSS = `
  .mc { margin: 0 0 12px; padding: 14px; border-radius: 8px; background: var(--secondary-background-color, rgba(127,127,127,.12)); }
  .mc-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 8px; }
  .mc-title { font-size: 12px; font-weight: 600; letter-spacing: .5px; text-transform: uppercase; color: var(--secondary-text-color); }
  .mc-legend { display: flex; gap: 12px; font-size: 12px; color: var(--primary-text-color); }
  .mc-swatch { font-weight: 700; }
  .mc-area { position: relative; height: 70px; margin-left: 52px; }
  .mc-svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
  .mc-now { stroke: var(--primary-text-color); stroke-opacity: .45; stroke-width: 1.5; }
  .mc-ylabel { position: absolute; left: -52px; width: 46px; text-align: right; transform: translateY(-50%); font-size: 11px; color: var(--secondary-text-color); white-space: nowrap; }
  .mc-axis { position: relative; height: 16px; margin: 6px 0 0 52px; font-size: 11px; color: var(--secondary-text-color); }
  .mc-axis > span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
  .mc-axis > span.first { transform: none; }
  .mc-axis > span.last { transform: translateX(-100%); }
  .mc-summary { margin: 8px 0 0; text-align: center; font-size: 13px; color: var(--primary-text-color); }
`;
