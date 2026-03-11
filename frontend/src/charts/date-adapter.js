// Custom minimal date adapter for Chart.js TimeScale
// Uses native Date + Intl.DateTimeFormat — avoids Luxon/date-fns (~70KB)
import { _adapters } from "chart.js";

const MILLISECOND = 1;
const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;

const FORMAT_KEYS = {
  millisecond: { hour: "numeric", minute: "numeric", second: "numeric", fractionalSecondDigits: 3 },
  second: { hour: "numeric", minute: "numeric", second: "numeric" },
  minute: { hour: "numeric", minute: "numeric" },
  hour: { hour: "numeric" },
  day: { month: "short", day: "numeric" },
  week: { month: "short", day: "numeric" },
  month: { month: "short", year: "numeric" },
  quarter: { month: "short", year: "numeric" },
  year: { year: "numeric" },
};

export const adapterOverride = {
  init() {},

  formats() {
    return { ...FORMAT_KEYS };
  },

  parse(value) {
    if (value == null) return null;
    if (typeof value === "number") return value;
    return new Date(value).getTime();
  },

  format(ts, fmt) {
    const d = new Date(ts);
    if (typeof fmt === "string") {
      // Fallback for raw string formats
      return d.toLocaleString();
    }
    return new Intl.DateTimeFormat("en-US", fmt).format(d);
  },

  add(ts, amount, unit) {
    const d = new Date(ts);
    switch (unit) {
      case "millisecond":
        return ts + amount * MILLISECOND;
      case "second":
        return ts + amount * SECOND;
      case "minute":
        return ts + amount * MINUTE;
      case "hour":
        return ts + amount * HOUR;
      case "day":
        return ts + amount * DAY;
      case "week":
        return ts + amount * WEEK;
      case "month": {
        const dayOfMonth = d.getUTCDate();
        d.setUTCDate(1);
        d.setUTCMonth(d.getUTCMonth() + amount);
        const maxDay = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
        d.setUTCDate(Math.min(dayOfMonth, maxDay));
        return d.getTime();
      }
      case "quarter": {
        const dayOfMonth2 = d.getUTCDate();
        d.setUTCDate(1);
        d.setUTCMonth(d.getUTCMonth() + amount * 3);
        const maxDay2 = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
        d.setUTCDate(Math.min(dayOfMonth2, maxDay2));
        return d.getTime();
      }
      case "year": {
        const dayOfMonth3 = d.getUTCDate();
        d.setUTCDate(1);
        d.setUTCFullYear(d.getUTCFullYear() + amount);
        const maxDay3 = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
        d.setUTCDate(Math.min(dayOfMonth3, maxDay3));
        return d.getTime();
      }
      default:
        return ts;
    }
  },

  diff(max, min, unit) {
    switch (unit) {
      case "millisecond":
        return max - min;
      case "second":
        return (max - min) / SECOND;
      case "minute":
        return (max - min) / MINUTE;
      case "hour":
        return (max - min) / HOUR;
      case "day":
        return (max - min) / DAY;
      case "week":
        return (max - min) / WEEK;
      case "month": {
        const a = new Date(min);
        const b = new Date(max);
        return (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + (b.getUTCMonth() - a.getUTCMonth());
      }
      case "quarter": {
        const a = new Date(min);
        const b = new Date(max);
        const months = (b.getUTCFullYear() - a.getUTCFullYear()) * 12 + (b.getUTCMonth() - a.getUTCMonth());
        return Math.floor(months / 3);
      }
      case "year": {
        const a = new Date(min);
        const b = new Date(max);
        return b.getUTCFullYear() - a.getUTCFullYear();
      }
      default:
        return 0;
    }
  },

  startOf(ts, unit) {
    const d = new Date(ts);
    switch (unit) {
      case "second":
        d.setUTCMilliseconds(0);
        return d.getTime();
      case "minute":
        d.setUTCSeconds(0, 0);
        return d.getTime();
      case "hour":
        d.setUTCMinutes(0, 0, 0);
        return d.getTime();
      case "day":
        d.setUTCHours(0, 0, 0, 0);
        return d.getTime();
      case "week": {
        d.setUTCHours(0, 0, 0, 0);
        const day = d.getUTCDay(); // 0=Sunday
        d.setUTCDate(d.getUTCDate() - day);
        return d.getTime();
      }
      case "isoWeek": {
        d.setUTCHours(0, 0, 0, 0);
        const day = d.getUTCDay(); // 0=Sunday
        const diff = (day === 0 ? -6 : 1) - day;
        d.setUTCDate(d.getUTCDate() + diff);
        return d.getTime();
      }
      case "month":
        d.setUTCHours(0, 0, 0, 0);
        d.setUTCDate(1);
        return d.getTime();
      case "quarter": {
        d.setUTCHours(0, 0, 0, 0);
        d.setUTCDate(1);
        const qMonth = d.getUTCMonth() - (d.getUTCMonth() % 3);
        d.setUTCMonth(qMonth);
        return d.getTime();
      }
      case "year":
        d.setUTCHours(0, 0, 0, 0);
        d.setUTCMonth(0, 1);
        return d.getTime();
      default:
        return ts;
    }
  },

  endOf(ts, unit) {
    const d = new Date(ts);
    switch (unit) {
      case "second":
        d.setUTCMilliseconds(999);
        return d.getTime();
      case "minute":
        d.setUTCSeconds(59, 999);
        return d.getTime();
      case "hour":
        d.setUTCMinutes(59, 59, 999);
        return d.getTime();
      case "day":
        d.setUTCHours(23, 59, 59, 999);
        return d.getTime();
      case "week": {
        d.setUTCHours(23, 59, 59, 999);
        const day = d.getUTCDay();
        d.setUTCDate(d.getUTCDate() + (6 - day));
        return d.getTime();
      }
      case "isoWeek": {
        d.setUTCHours(23, 59, 59, 999);
        const day = d.getUTCDay();
        // End of isoWeek = Sunday (day 0 means already Sunday, otherwise advance)
        const daysToSunday = day === 0 ? 0 : 7 - day;
        d.setUTCDate(d.getUTCDate() + daysToSunday);
        return d.getTime();
      }
      case "month":
        d.setUTCMonth(d.getUTCMonth() + 1, 0);
        d.setUTCHours(23, 59, 59, 999);
        return d.getTime();
      case "quarter": {
        const qEnd = d.getUTCMonth() - (d.getUTCMonth() % 3) + 3;
        d.setUTCMonth(qEnd, 0);
        d.setUTCHours(23, 59, 59, 999);
        return d.getTime();
      }
      case "year":
        d.setUTCMonth(11, 31);
        d.setUTCHours(23, 59, 59, 999);
        return d.getTime();
      default:
        return ts;
    }
  },
};

// Register the adapter as a side effect
_adapters._date.override(adapterOverride);
