import { describe, expect, it } from "vitest";
import { parseTime, time } from "./companionApi";

describe("time", () => {
  it.each([
    [0, "00:00.0"],
    [-1, "00:00.0"],
    [-0.04, "00:00.0"],
    [0.04, "00:00.0"],
    [0.05, "00:00.1"],
    [1.24, "00:01.2"],
    [9.96, "00:10.0"],
    [59.94, "00:59.9"],
    [59.95, "01:00.0"],
    [59.99, "01:00.0"],
    [60, "01:00.0"],
    [60.04, "01:00.0"],
    [60.06, "01:00.1"],
    [3599.94, "59:59.9"],
    [3599.95, "01:00:00.0"],
    [3599.99, "01:00:00.0"],
    [3600, "01:00:00.0"],
    [3600.04, "01:00:00.0"],
    [3600.06, "01:00:00.1"],
    [7265.67, "02:01:05.7"],
    [360000, "100:00:00.0"],
  ] as const)("formats %s as %s with a parseable tenth-second result", (seconds, expected) => {
    const formatted = time(seconds);
    expect(formatted).toBe(expected);
    expect(Math.abs(parseTime(formatted) - Math.max(0, seconds))).toBeLessThanOrEqual(0.05 + 1e-9);
  });
});

describe("parseTime", () => {
  it.each([
    "", "-1", "00:60.0", "59:60.0", "01:60:00", "00:00:60",
    "1.5:00", "NaN", "Infinity", "1:2:3:4", "1e2", "9".repeat(400),
  ])("rejects invalid input %s", value => {
    expect(() => parseTime(value)).toThrow();
  });
});
