import { describe, expect, it } from "vitest";
import { todayInBusinessTimezone } from "./date";

const BA = "America/Argentina/Buenos_Aires";

describe("todayInBusinessTimezone", () => {
  it("returns the business-zone calendar date, zero-padded, regardless of the browser zone", () => {
    expect(todayInBusinessTimezone(new Date("2026-01-05T15:00:00Z"), BA)).toBe("2026-01-05");
  });

  it("keeps the previous day until Argentine midnight (UTC-3)", () => {
    // 02:59:59Z del 14/10 = 23:59:59 del 13/10 en Argentina
    expect(todayInBusinessTimezone(new Date("2026-10-14T02:59:59Z"), BA)).toBe("2026-10-13");
    // 03:00:00Z = 00:00:00 del 14/10 en Argentina
    expect(todayInBusinessTimezone(new Date("2026-10-14T03:00:00Z"), BA)).toBe("2026-10-14");
  });

  it("is not moved by UTC midnight", () => {
    expect(todayInBusinessTimezone(new Date("2026-10-14T00:30:00Z"), BA)).toBe("2026-10-13");
  });

  it("handles year boundaries", () => {
    expect(todayInBusinessTimezone(new Date("2027-01-01T02:00:00Z"), BA)).toBe("2026-12-31");
  });
});
