import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  colorForRating,
  colorForScore,
  formatScore,
  iconForRating,
  FACTOR_META,
  FACTOR_SENSOR_SUFFIX,
} from "../src/utils.js";

describe("colorForRating", () => {
  it("returns green for GO", () => {
    assert.equal(colorForRating("GO"), "#4CAF50");
  });

  it("returns amber for CAUTION", () => {
    assert.equal(colorForRating("CAUTION"), "#FF9800");
  });

  it("returns red for NO_GO", () => {
    assert.equal(colorForRating("NO_GO"), "#F44336");
  });

  it("returns grey for unknown rating", () => {
    assert.equal(colorForRating("UNKNOWN"), "#9E9E9E");
  });

  it("returns grey for undefined", () => {
    assert.equal(colorForRating(undefined), "#9E9E9E");
  });
});

describe("colorForScore", () => {
  it("returns green for score >= 70", () => {
    assert.equal(colorForScore(70), "#4CAF50");
    assert.equal(colorForScore(100), "#4CAF50");
  });

  it("returns amber for score >= 40 and < 70", () => {
    assert.equal(colorForScore(40), "#FF9800");
    assert.equal(colorForScore(69), "#FF9800");
  });

  it("returns red for score < 40", () => {
    assert.equal(colorForScore(0), "#F44336");
    assert.equal(colorForScore(39), "#F44336");
  });

  it("returns grey for null/undefined", () => {
    assert.equal(colorForScore(null), "#9E9E9E");
    assert.equal(colorForScore(undefined), "#9E9E9E");
  });
});

describe("formatScore", () => {
  it("formats integer scores", () => {
    assert.equal(formatScore(85), "85%");
  });

  it("returns '--' for null/undefined", () => {
    assert.equal(formatScore(null), "--");
    assert.equal(formatScore(undefined), "--");
  });
});

describe("iconForRating", () => {
  it("returns check-circle for GO", () => {
    assert.equal(iconForRating("GO"), "mdi:check-circle");
  });

  it("returns alert for CAUTION", () => {
    assert.equal(iconForRating("CAUTION"), "mdi:alert");
  });

  it("returns close-circle for NO_GO", () => {
    assert.equal(iconForRating("NO_GO"), "mdi:close-circle");
  });

  it("returns help-circle for unknown", () => {
    assert.equal(iconForRating("UNKNOWN"), "mdi:help-circle");
  });
});

describe("FACTOR_META", () => {
  it("has entries for all 7 scoring factors", () => {
    const expectedKeys = [
      "wind_speed",
      "wind_gusts",
      "air_quality",
      "temperature",
      "uv_index",
      "visibility",
      "precipitation",
    ];
    for (const key of expectedKeys) {
      assert.ok(FACTOR_META[key], `Missing FACTOR_META entry for ${key}`);
      assert.ok(FACTOR_META[key].label, `Missing label for ${key}`);
      assert.ok(FACTOR_META[key].icon, `Missing icon for ${key}`);
      assert.ok(FACTOR_META[key].unit !== undefined, `Missing unit for ${key}`);
    }
  });
});

describe("FACTOR_SENSOR_SUFFIX", () => {
  it("maps air_quality to aqi", () => {
    assert.equal(FACTOR_SENSOR_SUFFIX.air_quality, "aqi");
  });

  it("maps temperature to air_temp", () => {
    assert.equal(FACTOR_SENSOR_SUFFIX.temperature, "air_temp");
  });

  it("maps wind_speed to wind_speed (identity)", () => {
    assert.equal(FACTOR_SENSOR_SUFFIX.wind_speed, "wind_speed");
  });

  it("has entries for all 7 factors", () => {
    const expectedKeys = [
      "wind_speed",
      "wind_gusts",
      "air_quality",
      "temperature",
      "uv_index",
      "visibility",
      "precipitation",
    ];
    for (const key of expectedKeys) {
      assert.ok(
        FACTOR_SENSOR_SUFFIX[key] !== undefined,
        `Missing FACTOR_SENSOR_SUFFIX entry for ${key}`
      );
    }
  });
});
