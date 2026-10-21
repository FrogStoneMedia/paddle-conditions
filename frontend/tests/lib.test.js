import { test } from "node:test";
import assert from "node:assert/strict";

import { resolveLocation, scoreEntities, PaddleLocation, signatureChanged, isScoreEntity } from "../src/lib/entities.js";
import { convert, convertSeries, displayUnit, formatState } from "../src/lib/units.js";
import { daylightWindow, recommendableBlocks, displayBlocks, bestBlock } from "../src/lib/daylight.js";
import { PALETTE, contrast, ratingForScore, normalizeRating } from "../src/lib/theme.js";
import { dayLabel } from "../src/lib/time.js";

const registry = {
  "sensor.my_home_lake": { entity_id: "sensor.my_home_lake", device_id: "d1", platform: "paddle_conditions", translation_key: "paddle_score" },
  "sensor.lake_wind": { entity_id: "sensor.lake_wind", device_id: "d1", platform: "paddle_conditions", translation_key: "wind_speed" },
  "sensor.other_score": { entity_id: "sensor.other_score", device_id: "d2", platform: "paddle_conditions", translation_key: "paddle_score" },
  "sensor.unrelated": { entity_id: "sensor.unrelated", device_id: "d1", platform: "other", translation_key: "wind_speed" },
};

test("resolveLocation finds renamed siblings by device and translation key", () => {
  const ids = resolveLocation({ entities: registry }, "sensor.my_home_lake");
  assert.deepEqual(ids, { paddle_score: "sensor.my_home_lake", wind_speed: "sensor.lake_wind" });
});

test("resolveLocation falls back to default suffixes without a registry", () => {
  const ids = resolveLocation({ states: {} }, "sensor.lake_natoma_paddle_score");
  assert.equal(ids.air_temp, "sensor.lake_natoma_air_temperature");
  assert.equal(ids.forecast_3hr, "sensor.lake_natoma_3_hour_forecast");
});

test("resolveLocation works from any sibling, not just the score", () => {
  const ids = resolveLocation({}, "sensor.lake_natoma_3_hour_forecast");
  assert.equal(ids.paddle_score, "sensor.lake_natoma_paddle_score");
});

test("scoreEntities lists every location's score", () => {
  assert.deepEqual(scoreEntities({ entities: registry }).sort(), ["sensor.my_home_lake", "sensor.other_score"]);
});

test("PaddleLocation signature changes only when a sibling state object changes", () => {
  const s1 = { state: "80" };
  const hass = { entities: registry, states: { "sensor.my_home_lake": s1, "sensor.lake_wind": { state: "5" } } };
  const loc = new PaddleLocation(hass, "sensor.my_home_lake");
  const before = loc.signature(hass);
  assert.equal(signatureChanged(before, loc.signature(hass)), false);
  const next = { ...hass, states: { ...hass.states, "sensor.lake_wind": { state: "6" } } };
  assert.equal(signatureChanged(before, loc.signature(next)), true);
});

test("units convert native forecast values to the sensor's display unit", () => {
  assert.equal(displayUnit({ attributes: { unit_of_measurement: "°C" } }, "temperature"), "°C");
  assert.equal(displayUnit({ attributes: {} }, "temperature"), "°F");
  assert.ok(Math.abs(convert(68, "temperature", "°C") - 20) < 1e-9);
  assert.ok(Math.abs(convert(10, "speed", "km/h") - 16.09344) < 1e-9);
  assert.ok(Math.abs(convert(1, "distance", "km") - 1.609344) < 1e-9);
  assert.deepEqual(convertSeries([32, null], "temperature", "°C"), [0, null]);
});

test("formatState prefers HA's formatter and hides unavailable", () => {
  assert.equal(formatState({ formatEntityState: () => "16.2 °C" }, { state: "16.2" }), "16.2 °C");
  assert.equal(formatState({}, { state: "unavailable", attributes: {} }), "—");
  assert.equal(formatState({}, { state: "5", attributes: { unit_of_measurement: "mph" } }), "5 mph");
});

const at = (iso) => new Date(iso);

test("daylight uses the spot's own window and rolls to tomorrow after sunset", () => {
  const forecast = {
    attributes: {
      daylight: [
        { sunrise: "2026-10-21T14:16:00+00:00", sunset: "2026-10-22T01:12:00+00:00" },
        { sunrise: "2026-10-22T14:17:00+00:00", sunset: "2026-10-23T01:11:00+00:00" },
      ],
    },
  };
  assert.equal(daylightWindow(forecast, null, at("2026-10-21T20:00:00Z")).sunrise.toISOString(), "2026-10-21T14:16:00.000Z");
  assert.equal(daylightWindow(forecast, null, at("2026-10-22T03:00:00Z")).sunrise.toISOString(), "2026-10-22T14:17:00.000Z");
});

test("daylight falls back to sun.sun", () => {
  const sun = { state: "above_horizon", attributes: { next_rising: "2026-10-22T14:17:00Z", next_setting: "2026-10-22T01:12:00Z" } };
  const w = daylightWindow({ attributes: {} }, sun, at("2026-10-21T20:00:00Z"));
  assert.equal(w.sunset.toISOString(), "2026-10-22T01:12:00.000Z");
});

test("block filters and best block", () => {
  const window = { sunrise: at("2026-10-21T14:00:00Z"), sunset: at("2026-10-22T01:00:00Z") };
  const blocks = [
    { start: "2026-10-21T12:00:00+00:00", end: "2026-10-21T15:00:00+00:00", score: 99 },
    { start: "2026-10-21T15:00:00+00:00", end: "2026-10-21T18:00:00+00:00", score: 80 },
    { start: "2026-10-21T21:00:00+00:00", end: "2026-10-22T00:00:00+00:00", score: 90 },
  ];
  assert.deepEqual(recommendableBlocks(blocks, window).map((b) => b.score), [80]);
  assert.deepEqual(displayBlocks(blocks, window).map((b) => b.score), [80, 90]);
  assert.equal(bestBlock(blocks).score, 99);
});

test("rating colours meet 4.5:1 in both themes, and white text on fills", () => {
  for (const mode of ["light", "dark"]) {
    for (const [rating, color] of Object.entries(PALETTE[mode].text)) {
      for (const bg of PALETTE[mode].backgrounds) {
        assert.ok(contrast(color, bg) >= 4.5, `${mode} ${rating} on ${bg}: ${contrast(color, bg)}`);
      }
    }
  }
  for (const [rating, stops] of Object.entries(PALETTE.fill)) {
    for (const stop of stops) assert.ok(contrast("#FFFFFF", stop) >= 4.5, `fill ${rating} ${stop} ${contrast("#FFFFFF", stop)}`);
  }
});

test("rating helpers", () => {
  assert.equal(ratingForScore(70), "GO");
  assert.equal(ratingForScore(39), "NO_GO");
  assert.equal(ratingForScore(null), "NONE");
  assert.equal(normalizeRating("caution"), "CAUTION");
  assert.equal(normalizeRating(undefined), "NONE");
});

test("dayLabel in a given zone", () => {
  const hass = { locale: { language: "en", time_zone: "server" }, config: { time_zone: "America/Los_Angeles" } };
  const now = at("2026-10-21T20:00:00Z");
  assert.equal(dayLabel(hass, at("2026-10-22T03:00:00Z"), now), "Today"); // 8 PM PDT
  assert.equal(dayLabel(hass, at("2026-10-22T15:00:00Z"), now), "Tomorrow");
});

test("isScoreEntity uses the registry and falls back to the default id", () => {
  assert.equal(isScoreEntity({ entities: registry }, "sensor.my_home_lake"), true);
  assert.equal(isScoreEntity({ entities: registry }, "sensor.lake_wind"), false);
  assert.equal(isScoreEntity({}, "sensor.lake_natoma_paddle_score"), true);
  assert.equal(isScoreEntity({}, "sensor.kitchen_temperature"), false);
});

import { convertBetween } from "../src/lib/units.js";
import { SERIES } from "../src/lib/theme.js";
import { dayKey, weekday } from "../src/lib/time.js";
import { computeStats } from "../src/charts/chart-utils.js";

test("convertBetween converts between display units via native", () => {
  assert.ok(Math.abs(convertBetween(68, "temperature", "°F", "°C") - 20) < 1e-9);
  assert.ok(Math.abs(convertBetween(20, "temperature", "°C", "°F") - 68) < 1e-9);
  assert.ok(Math.abs(convertBetween(16.09344, "speed", "km/h", "mph") - 10) < 1e-6);
  assert.equal(convertBetween(5, "temperature", "furlongs", "°C"), null);
  assert.equal(convertBetween(null, "temperature", "°C", "°F"), null);
});

test("chart series colours reach 3:1 on every plot surface, toggle text 4.5:1", () => {
  for (const mode of ["light", "dark"]) {
    for (const [name, color] of Object.entries(SERIES[mode])) {
      for (const bg of PALETTE[mode].backgrounds) {
        assert.ok(contrast(color, bg) >= 3, `${mode} ${name} ${color} on ${bg}: ${contrast(color, bg)}`);
      }
      assert.ok(contrast(SERIES.onFill[mode], color) >= 4.5, `${mode} toggle text on ${name}: ${contrast(SERIES.onFill[mode], color)}`);
    }
  }
});

test("history stats group days in the user's chosen zone", () => {
  const hass = { locale: { time_zone: "server" }, config: { time_zone: "America/Los_Angeles" } };
  // 06:00Z on the 22nd is still the 21st in Los Angeles.
  const data = [
    { timestamp: "2026-10-21T20:00:00Z", value: 80 },
    { timestamp: "2026-10-22T06:00:00Z", value: 80 },
  ];
  const s = computeStats(data, (d) => dayKey(hass, d), (d) => weekday(hass, d));
  assert.equal(s.goDays, 1);
  assert.equal(s.bestDay, "Wed");
});
