import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ratingForScore,
  formatTimestamp,
  computeStats,
  CHART_METRICS,
  getThresholdGridColor,
  getZoneBackgrounds,
} from "../src/charts/chart-utils.js";

describe("ratingForScore", () => {
  it("returns GO for score >= 70", () => {
    assert.equal(ratingForScore(70), "GO");
    assert.equal(ratingForScore(100), "GO");
  });

  it("returns CAUTION for score >= 40 and < 70", () => {
    assert.equal(ratingForScore(40), "CAUTION");
    assert.equal(ratingForScore(69), "CAUTION");
  });

  it("returns NO_GO for score < 40", () => {
    assert.equal(ratingForScore(0), "NO_GO");
    assert.equal(ratingForScore(39), "NO_GO");
  });

  it("returns null for null/undefined", () => {
    assert.equal(ratingForScore(null), null);
    assert.equal(ratingForScore(undefined), null);
  });
});

describe("formatTimestamp", () => {
  it("formats hourly timestamps for 7d range", () => {
    const ts = "2026-03-10T14:00:00";
    const result = formatTimestamp(ts, "7d");
    assert.equal(result, "Mar 10 2PM");
  });

  it("formats daily timestamps for 30d range", () => {
    const ts = "2026-03-10T00:00:00";
    const result = formatTimestamp(ts, "30d");
    assert.equal(result, "Mar 10");
  });

  it("formats daily timestamps for 90d range", () => {
    const ts = "2026-03-10T00:00:00";
    const result = formatTimestamp(ts, "90d");
    assert.equal(result, "Mar 10");
  });

  it("formats forecast time as HH:MM AM/PM", () => {
    const ts = "2026-03-10T14:00:00";
    const result = formatTimestamp(ts, "forecast");
    // Use regex to handle potential non-breaking space before AM/PM
    assert.match(result, /2:00\s?PM/);
  });

  it("returns '--' for null input", () => {
    assert.equal(formatTimestamp(null, "7d"), "--");
  });
});

describe("computeStats", () => {
  it("computes average, best, go days, best day of week", () => {
    // 3 data points: Mon score 80 (GO), Tue score 50 (CAUTION), Wed score 90 (GO)
    const data = [
      { timestamp: "2026-03-09T12:00:00", value: 80 }, // Monday
      { timestamp: "2026-03-10T12:00:00", value: 50 }, // Tuesday
      { timestamp: "2026-03-11T12:00:00", value: 90 }, // Wednesday
    ];
    const stats = computeStats(data);
    assert.equal(stats.avg, 73);
    assert.equal(stats.best, 90);
    assert.equal(stats.goDays, 2);
    assert.equal(stats.bestDay, "Wed");
  });

  it("returns zeroed stats for empty data", () => {
    const stats = computeStats([]);
    assert.equal(stats.avg, 0);
    assert.equal(stats.best, 0);
    assert.equal(stats.goDays, 0);
    assert.equal(stats.bestDay, "--");
  });

  it("groups by day for go days count", () => {
    // Two hourly points on same day, both GO
    const data = [
      { timestamp: "2026-03-10T10:00:00", value: 80 },
      { timestamp: "2026-03-10T13:00:00", value: 75 },
    ];
    const stats = computeStats(data);
    assert.equal(stats.goDays, 1); // same day counts once
  });
});

describe("CHART_METRICS", () => {
  it("has score metric on y axis", () => {
    assert.ok(CHART_METRICS.score);
    assert.equal(CHART_METRICS.score.axis, "y");
    assert.ok(CHART_METRICS.score.label);
    assert.ok(CHART_METRICS.score.color);
  });

  it("has wind, temp, uv metrics on y1 axis", () => {
    for (const key of ["wind", "temp", "uv"]) {
      assert.ok(CHART_METRICS[key], `Missing metric ${key}`);
      assert.equal(CHART_METRICS[key].axis, "y1");
    }
  });
});

describe("getThresholdGridColor", () => {
  it("returns green-tinted color for value 70", () => {
    const color = getThresholdGridColor(70);
    assert.ok(color.includes("76,175,80"));
  });

  it("returns amber-tinted color for value 40", () => {
    const color = getThresholdGridColor(40);
    assert.ok(color.includes("255,152,0"));
  });

  it("returns subtle color for other values", () => {
    const color = getThresholdGridColor(50);
    assert.ok(color.includes("0,0,0"));
  });
});

describe("getZoneBackgrounds", () => {
  it("returns 3 zones covering 0-100", () => {
    const zones = getZoneBackgrounds();
    assert.equal(zones.length, 3);
    assert.equal(zones[0].from, 70);
    assert.equal(zones[0].to, 100);
    assert.equal(zones[1].from, 40);
    assert.equal(zones[1].to, 70);
    assert.equal(zones[2].from, 0);
    assert.equal(zones[2].to, 40);
  });
});
