// The paddle spot's own daylight window, from the forecast sensor's
// "daylight" attribute ([{sunrise, sunset}] in UTC). Falls back to sun.sun.

/**
 * The window to plan around: today's if the sun hasn't set yet, otherwise
 * the next day's. Returns {sunrise, sunset} as Dates, or null.
 */
export function daylightWindow(forecastState, sunState, now = new Date()) {
  const days = forecastState?.attributes?.daylight;
  if (Array.isArray(days) && days.length) {
    for (const d of days) {
      const sunrise = new Date(d.sunrise);
      const sunset = new Date(d.sunset);
      if (Number.isNaN(sunrise.getTime()) || Number.isNaN(sunset.getTime())) continue;
      if (now < sunset) return { sunrise, sunset };
    }
  }
  return fromSunEntity(sunState, now);
}

function fromSunEntity(sun, now) {
  const rising = sun?.attributes?.next_rising ? new Date(sun.attributes.next_rising) : null;
  const setting = sun?.attributes?.next_setting ? new Date(sun.attributes.next_setting) : null;
  if (!rising || !setting) return null;
  if (sun.state === "above_horizon") {
    return { sunrise: new Date(rising.getTime() - 86400000), sunset: setting };
  }
  return { sunrise: rising, sunset: setting > rising ? setting : new Date(setting.getTime() + 86400000) };
}

/** Blocks worth recommending: start after sunrise, end at least 2 h before sunset. */
export function recommendableBlocks(blocks, window) {
  if (!window) return blocks;
  const cutoff = window.sunset.getTime() - 2 * 3600000;
  return blocks.filter((b) => new Date(b.start) >= window.sunrise && new Date(b.end).getTime() <= cutoff);
}

/** Blocks to display: from 1 h before sunrise to 1 h after sunset. */
export function displayBlocks(blocks, window) {
  if (!window) return blocks;
  const from = window.sunrise.getTime() - 3600000;
  const to = window.sunset.getTime() + 3600000;
  return blocks.filter((b) => {
    const t = new Date(b.start).getTime();
    return t >= from && t <= to;
  });
}

export function bestBlock(blocks) {
  return blocks.reduce((best, b) => (best == null || b.score > best.score ? b : best), null);
}
