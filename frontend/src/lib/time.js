// Times in the user's chosen zone (browser or server, per their HA profile).

export function timeZone(hass) {
  if (hass?.locale?.time_zone === "server" && hass?.config?.time_zone) return hass.config.time_zone;
  return undefined; // Browser default.
}

function language(hass) {
  return hass?.locale?.language || undefined;
}

function hour12(hass) {
  const f = hass?.locale?.time_format;
  if (f === "12") return true;
  if (f === "24") return false;
  return undefined;
}

export function formatHour(hass, date) {
  return new Intl.DateTimeFormat(language(hass), { hour: "numeric", hour12: hour12(hass), timeZone: timeZone(hass) }).format(date);
}

export function formatTime(hass, date) {
  return new Intl.DateTimeFormat(language(hass), {
    hour: "numeric",
    minute: "2-digit",
    hour12: hour12(hass),
    timeZone: timeZone(hass),
  }).format(date);
}

export function dayKey(hass, date) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: timeZone(hass), year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
}

/** "Today", "Tomorrow", or a short weekday date, judged in the user's zone. */
export function dayLabel(hass, date, now = new Date()) {
  const target = dayKey(hass, date);
  if (target === dayKey(hass, now)) return "Today";
  if (target === dayKey(hass, new Date(now.getTime() + 86400000))) return "Tomorrow";
  return new Intl.DateTimeFormat(language(hass), { weekday: "short", month: "short", day: "numeric", timeZone: timeZone(hass) }).format(date);
}

export function sameDay(hass, a, b) {
  return dayKey(hass, a) === dayKey(hass, b);
}

/** 0 (Sunday) to 6, in the user's zone. */
export function weekday(hass, date) {
  const name = new Intl.DateTimeFormat("en-US", { weekday: "short", timeZone: timeZone(hass) }).format(date);
  return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(name);
}

export function formatDateTime(hass, date) {
  return new Intl.DateTimeFormat(language(hass), {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: hour12(hass),
    timeZone: timeZone(hass),
  }).format(date);
}

export function formatDay(hass, date) {
  return new Intl.DateTimeFormat(language(hass), { month: "short", day: "numeric", timeZone: timeZone(hass) }).format(date);
}
