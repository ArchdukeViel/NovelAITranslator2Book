import { describe, it, expect, afterEach, vi } from "vitest";
import { groupDateLabel } from "@/lib/date-group";

afterEach(() => {
  vi.useRealTimers();
});

describe("groupDateLabel", () => {
  it("returns null for null input", () => {
    expect(groupDateLabel(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(groupDateLabel(undefined)).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(groupDateLabel("")).toBeNull();
  });

  it("returns null for invalid date string", () => {
    expect(groupDateLabel("not-a-date")).toBeNull();
  });

  it('returns "Today" for the same calendar day', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:30:00Z");
    vi.setSystemTime(now);

    const sameDay = "2026-06-17T08:00:00Z";
    expect(groupDateLabel(sameDay)).toBe("Today");
  });

  it('returns "Yesterday" for the previous calendar day', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    const yesterday = "2026-06-16T00:00:00Z";
    expect(groupDateLabel(yesterday)).toBe("Yesterday");
  });

  it('returns "Yesterday" from midnight yesterday', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T00:01:00+09:00");
    vi.setSystemTime(now);

    const yesterday = "2026-06-16T00:00:00+09:00";
    expect(groupDateLabel(yesterday)).toBe("Yesterday");
  });

  it('returns "1 week ago" for 2–7 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-06-15T00:00:00Z")).toBe("1 week ago"); // 2 days
    expect(groupDateLabel("2026-06-10T00:00:00Z")).toBe("1 week ago"); // 7 days
  });

  it('returns "2 weeks ago" for 8–14 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-06-09T00:00:00Z")).toBe("2 weeks ago"); // 8 days
    expect(groupDateLabel("2026-06-03T00:00:00Z")).toBe("2 weeks ago"); // 14 days
  });

  it('returns "3 weeks ago" for 15–21 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-06-02T00:00:00Z")).toBe("3 weeks ago"); // 15 days
    expect(groupDateLabel("2026-05-27T00:00:00Z")).toBe("3 weeks ago"); // 21 days
  });

  it('returns "Last month" for 22–60 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-05-26T00:00:00Z")).toBe("Last month"); // 22 days
    expect(groupDateLabel("2026-04-18T00:00:00Z")).toBe("Last month"); // 60 days
  });

  it('returns "Mon YYYY" for dates more than 60 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    // 61+ days ago
    expect(groupDateLabel("2026-04-16T00:00:00Z")).toBe("Apr 2026");
    expect(groupDateLabel("2025-12-01T00:00:00Z")).toBe("Dec 2025");
  });

  it("returns null for future dates", () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-06-18T00:00:00Z")).toBeNull();
  });
});
