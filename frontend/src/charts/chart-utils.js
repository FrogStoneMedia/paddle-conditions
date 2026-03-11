const SCORE_GO = 70;
const SCORE_CAUTION = 40;

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function ratingForScore(score) {
  if (score == null) return null;
  if (score >= SCORE_GO) return "GO";
  if (score >= SCORE_CAUTION) return "CAUTION";
  return "NO_GO";
}

export function formatTimestamp(ts, range) {
  if (!ts) return "--";
  const d = new Date(ts);

  if (range === "forecast") {
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  }
  if (range === "7d") {
    const hour = d.getHours();
    const ampm = hour >= 12 ? "PM" : "AM";
    const h = hour % 12 || 12;
    return `${MONTH_NAMES[d.getMonth()]} ${d.getDate()} ${h}${ampm}`;
  }
  // 30d, 90d
  return `${MONTH_NAMES[d.getMonth()]} ${d.getDate()}`;
}

export function computeStats(data) {
  if (!data || data.length === 0) {
    return { avg: 0, best: 0, goDays: 0, bestDay: "--" };
  }

  let sum = 0;
  let best = 0;
  const dayScores = new Map();
  const dayOfWeekTotals = new Array(7).fill(0);
  const dayOfWeekCounts = new Array(7).fill(0);

  for (const point of data) {
    const val = point.value;
    sum += val;
    if (val > best) best = val;

    const d = new Date(point.timestamp);
    const dateKey = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

    if (!dayScores.has(dateKey)) {
      dayScores.set(dateKey, []);
    }
    dayScores.get(dateKey).push(val);

    const dow = d.getDay();
    dayOfWeekTotals[dow] += val;
    dayOfWeekCounts[dow] += 1;
  }

  const avg = Math.round(sum / data.length);

  let goDays = 0;
  for (const scores of dayScores.values()) {
    const dayMean = scores.reduce((a, b) => a + b, 0) / scores.length;
    if (dayMean >= SCORE_GO) goDays++;
  }

  let bestDow = 0;
  let bestDowAvg = -1;
  for (let i = 0; i < 7; i++) {
    if (dayOfWeekCounts[i] > 0) {
      const dowAvg = dayOfWeekTotals[i] / dayOfWeekCounts[i];
      if (dowAvg > bestDowAvg) {
        bestDowAvg = dowAvg;
        bestDow = i;
      }
    }
  }

  return {
    avg,
    best,
    goDays,
    bestDay: dayOfWeekCounts[bestDow] > 0 ? DAY_NAMES[bestDow] : "--",
  };
}

export const CHART_METRICS = {
  score: { label: "Score", color: "#4CAF50", axis: "y", dash: [] },
  wind: { label: "Wind", color: "#42A5F5", axis: "y1", dash: [6, 3], unit: "mph" },
  temp: { label: "Temp", color: "#FF9800", axis: "y1", dash: [6, 3], unit: "\u00B0F" },
  uv: { label: "UV", color: "#AB47BC", axis: "y1", dash: [6, 3], unit: "" },
};

export function getThresholdGridColor(value) {
  if (value === 70) return "rgba(76,175,80,0.3)";
  if (value === 40) return "rgba(255,152,0,0.3)";
  return "rgba(0,0,0,0.05)";
}

export function getZoneBackgrounds() {
  return [
    { from: 70, to: 100, color: "rgba(76,175,80,0.06)" },
    { from: 40, to: 70, color: "rgba(255,152,0,0.06)" },
    { from: 0, to: 40, color: "rgba(244,67,54,0.06)" },
  ];
}

export function createScoreGradient(ctx) {
  if (!ctx.chart.chartArea) return "rgba(76,175,80,0.1)";
  const { top, bottom } = ctx.chart.chartArea;
  const gradient = ctx.chart.ctx.createLinearGradient(0, top, 0, bottom);
  gradient.addColorStop(0, "rgba(76,175,80,0.3)");
  gradient.addColorStop(0.5, "rgba(255,152,0,0.15)");
  gradient.addColorStop(1, "rgba(244,67,54,0.1)");
  return gradient;
}

export function resolveHAColor(el, varName, fallback) {
  return getComputedStyle(el).getPropertyValue(varName).trim() || fallback;
}
