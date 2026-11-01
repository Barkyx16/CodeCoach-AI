import { formatArgs, formatValue, percent, timeAgo, titleCase } from "./format";

describe("format", () => {
  it("formats test values like Java literals", () => {
    expect(formatValue([0, 1])).toBe("[0, 1]");
    expect(formatValue("olleh")).toBe('"olleh"');
    expect(formatValue({ throws: "IllegalArgumentException" })).toBe("throws IllegalArgumentException");
    expect(formatValue(true)).toBe("true");
    expect(formatArgs({ nums: [2, 7], target: 9 })).toBe("nums = [2, 7], target = 9");
  });

  it("formats percentages, titles and relative times", () => {
    expect(percent(0.5)).toBe("50%");
    expect(percent(null)).toBe("—");
    expect(titleCase("dynamic-programming")).toBe("Dynamic Programming");
    const now = new Date("2026-11-01T12:00:00Z");
    expect(timeAgo("2026-11-01T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-11-01T11:57:00Z", now)).toBe("3 minutes ago");
    expect(timeAgo("2026-10-31T12:00:00Z", now)).toBe("yesterday");
  });
});
