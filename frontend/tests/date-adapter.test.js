import { describe, it } from "node:test";
import assert from "node:assert/strict";

// The adapter is a side-effect import that calls _adapters._date.override()
// We test the adapter functions directly by importing the override object
import { adapterOverride } from "../src/charts/date-adapter.js";

describe("date-adapter formats()", () => {
  it("returns format strings for all 9 time units", () => {
    const formats = adapterOverride.formats();
    const units = [
      "millisecond",
      "second",
      "minute",
      "hour",
      "day",
      "week",
      "month",
      "quarter",
      "year",
    ];
    for (const unit of units) {
      assert.ok(formats[unit], `Missing format for ${unit}`);
    }
  });
});

describe("date-adapter init()", () => {
  it("is a no-op that does not throw", () => {
    assert.doesNotThrow(() => adapterOverride.init({}));
  });
});

describe("date-adapter parse()", () => {
  it("parses ISO string to timestamp", () => {
    const ts = adapterOverride.parse("2026-03-10T14:00:00Z");
    assert.equal(typeof ts, "number");
    assert.equal(ts, new Date("2026-03-10T14:00:00Z").getTime());
  });

  it("passes through numeric timestamps", () => {
    const now = Date.now();
    assert.equal(adapterOverride.parse(now), now);
  });

  it("returns null for null/undefined", () => {
    assert.equal(adapterOverride.parse(null), null);
    assert.equal(adapterOverride.parse(undefined), null);
  });
});

describe("date-adapter format()", () => {
  const ts = new Date("2026-03-10T14:30:00Z").getTime();

  it("formats with hour format", () => {
    const formats = adapterOverride.formats();
    const result = adapterOverride.format(ts, formats.hour);
    // Should produce something like "2 PM" or "2:30 PM" depending on locale
    assert.ok(typeof result === "string" && result.length > 0);
  });

  it("formats with day format", () => {
    const formats = adapterOverride.formats();
    const result = adapterOverride.format(ts, formats.day);
    // Should produce something like "Mar 10"
    assert.ok(typeof result === "string" && result.length > 0);
  });

  it("formats with month format", () => {
    const formats = adapterOverride.formats();
    const result = adapterOverride.format(ts, formats.month);
    assert.ok(typeof result === "string" && result.length > 0);
  });

  it("formats with year format", () => {
    const formats = adapterOverride.formats();
    const result = adapterOverride.format(ts, formats.year);
    assert.ok(typeof result === "string" && result.includes("2026"));
  });
});

describe("date-adapter add()", () => {
  it("adds hours", () => {
    const base = new Date("2026-03-10T10:00:00Z").getTime();
    const result = adapterOverride.add(base, 3, "hour");
    assert.equal(result, new Date("2026-03-10T13:00:00Z").getTime());
  });

  it("adds days", () => {
    const base = new Date("2026-03-10T10:00:00Z").getTime();
    const result = adapterOverride.add(base, 2, "day");
    assert.equal(result, new Date("2026-03-12T10:00:00Z").getTime());
  });

  it("adds months (calendar-aware)", () => {
    // Jan 31 + 1 month = Feb 28 (2026 is not a leap year)
    const base = new Date("2026-01-31T00:00:00Z").getTime();
    const result = adapterOverride.add(base, 1, "month");
    const d = new Date(result);
    assert.equal(d.getUTCMonth(), 1); // February
    assert.equal(d.getUTCDate(), 28);
  });

  it("adds quarters", () => {
    const base = new Date("2026-01-15T00:00:00Z").getTime();
    const result = adapterOverride.add(base, 1, "quarter");
    const d = new Date(result);
    assert.equal(d.getUTCMonth(), 3); // April
    assert.equal(d.getUTCDate(), 15);
  });

  it("adds years", () => {
    const base = new Date("2026-03-10T00:00:00Z").getTime();
    const result = adapterOverride.add(base, 1, "year");
    const d = new Date(result);
    assert.equal(d.getUTCFullYear(), 2027);
  });

  it("adds weeks", () => {
    const base = new Date("2026-03-10T00:00:00Z").getTime();
    const result = adapterOverride.add(base, 2, "week");
    assert.equal(result, new Date("2026-03-24T00:00:00Z").getTime());
  });

  it("adds minutes", () => {
    const base = new Date("2026-03-10T10:00:00Z").getTime();
    const result = adapterOverride.add(base, 30, "minute");
    assert.equal(result, new Date("2026-03-10T10:30:00Z").getTime());
  });

  it("adds seconds", () => {
    const base = new Date("2026-03-10T10:00:00Z").getTime();
    const result = adapterOverride.add(base, 45, "second");
    assert.equal(result, new Date("2026-03-10T10:00:45Z").getTime());
  });

  it("adds milliseconds", () => {
    const base = new Date("2026-03-10T10:00:00Z").getTime();
    const result = adapterOverride.add(base, 500, "millisecond");
    assert.equal(result, base + 500);
  });
});

describe("date-adapter diff()", () => {
  it("diffs hours", () => {
    const a = new Date("2026-03-10T10:00:00Z").getTime();
    const b = new Date("2026-03-10T13:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "hour"), 3);
  });

  it("diffs days", () => {
    const a = new Date("2026-03-10T00:00:00Z").getTime();
    const b = new Date("2026-03-15T00:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "day"), 5);
  });

  it("diffs months (calendar-aware)", () => {
    const a = new Date("2026-01-15T00:00:00Z").getTime();
    const b = new Date("2026-04-15T00:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "month"), 3);
  });

  it("diffs years", () => {
    const a = new Date("2024-03-10T00:00:00Z").getTime();
    const b = new Date("2026-03-10T00:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "year"), 2);
  });

  it("diffs weeks", () => {
    const a = new Date("2026-03-10T00:00:00Z").getTime();
    const b = new Date("2026-03-24T00:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "week"), 2);
  });

  it("diffs quarters", () => {
    const a = new Date("2026-01-01T00:00:00Z").getTime();
    const b = new Date("2026-10-01T00:00:00Z").getTime();
    assert.equal(adapterOverride.diff(b, a, "quarter"), 3);
  });
});

describe("date-adapter startOf()", () => {
  const ts = new Date("2026-03-11T14:35:22.500Z").getTime();

  it("start of second", () => {
    const result = adapterOverride.startOf(ts, "second");
    assert.equal(result, new Date("2026-03-11T14:35:22.000Z").getTime());
  });

  it("start of minute", () => {
    const result = adapterOverride.startOf(ts, "minute");
    assert.equal(result, new Date("2026-03-11T14:35:00.000Z").getTime());
  });

  it("start of hour", () => {
    const result = adapterOverride.startOf(ts, "hour");
    assert.equal(result, new Date("2026-03-11T14:00:00.000Z").getTime());
  });

  it("start of day", () => {
    const result = adapterOverride.startOf(ts, "day");
    assert.equal(result, new Date("2026-03-11T00:00:00.000Z").getTime());
  });

  it("start of week (Sunday)", () => {
    // 2026-03-11 is Wednesday. Start of week (Sunday) = 2026-03-08
    const result = adapterOverride.startOf(ts, "week");
    assert.equal(result, new Date("2026-03-08T00:00:00.000Z").getTime());
  });

  it("start of isoWeek (Monday)", () => {
    // 2026-03-11 is Wednesday. Start of isoWeek (Monday) = 2026-03-09
    const result = adapterOverride.startOf(ts, "isoWeek");
    assert.equal(result, new Date("2026-03-09T00:00:00.000Z").getTime());
  });

  it("start of month", () => {
    const result = adapterOverride.startOf(ts, "month");
    assert.equal(result, new Date("2026-03-01T00:00:00.000Z").getTime());
  });

  it("start of quarter", () => {
    // March is Q1, starts Jan 1
    const result = adapterOverride.startOf(ts, "quarter");
    assert.equal(result, new Date("2026-01-01T00:00:00.000Z").getTime());
  });

  it("start of year", () => {
    const result = adapterOverride.startOf(ts, "year");
    assert.equal(result, new Date("2026-01-01T00:00:00.000Z").getTime());
  });
});

describe("date-adapter endOf()", () => {
  it("end of day", () => {
    const ts = new Date("2026-03-11T14:35:22.500Z").getTime();
    const result = adapterOverride.endOf(ts, "day");
    assert.equal(result, new Date("2026-03-11T23:59:59.999Z").getTime());
  });

  it("end of month", () => {
    const ts = new Date("2026-02-15T00:00:00Z").getTime();
    const result = adapterOverride.endOf(ts, "month");
    assert.equal(result, new Date("2026-02-28T23:59:59.999Z").getTime());
  });

  it("end of year", () => {
    const ts = new Date("2026-06-15T00:00:00Z").getTime();
    const result = adapterOverride.endOf(ts, "year");
    assert.equal(result, new Date("2026-12-31T23:59:59.999Z").getTime());
  });

  it("end of isoWeek (Sunday)", () => {
    // 2026-03-11 is Wednesday. End of isoWeek (Sunday) = 2026-03-15 23:59:59.999
    const ts = new Date("2026-03-11T14:00:00Z").getTime();
    const result = adapterOverride.endOf(ts, "isoWeek");
    assert.equal(result, new Date("2026-03-15T23:59:59.999Z").getTime());
  });
});
