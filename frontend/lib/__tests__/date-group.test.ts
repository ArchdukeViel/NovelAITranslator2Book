import { describe, it, expect, afterEach, vi } from "vitest";
import { groupDateLabel, todayTimeLabel } from "@/lib/date-group";

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

  it('returns "1 month ago" for 22–30 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-05-26T00:00:00Z")).toBe("1 month ago"); // 22 days
    expect(groupDateLabel("2026-05-18T00:00:00Z")).toBe("1 month ago"); // 30 days
  });

  it('returns "2 months ago" for 31–60 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-05-18T00:00:00Z")).toBe("1 month ago"); // 30 days
    expect(groupDateLabel("2026-04-18T00:00:00Z")).toBe("2 months ago"); // 60 days
  });

  it('returns "3 months ago" for 61–90 days ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-04-17T00:00:00Z")).toBe("3 months ago"); // 61 days
    expect(groupDateLabel("2026-03-19T00:00:00Z")).toBe("3 months ago"); // 90 days
  });

  it('returns "Mon YYYY" for dates more than 3 months ago', () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    // 91+ days ago
    expect(groupDateLabel("2026-03-17T00:00:00Z")).toBe("Mar 2026");
    expect(groupDateLabel("2025-12-01T00:00:00Z")).toBe("Dec 2025");
  });

  it("returns null for future dates", () => {
    vi.useFakeTimers();
    const now = new Date("2026-06-17T12:00:00Z");
    vi.setSystemTime(now);

    expect(groupDateLabel("2026-06-18T00:00:00Z")).toBeNull();
  });
});

describe("todayTimeLabel", () => {
  it("returns null for null input", () => {
    expect(todayTimeLabel(null)).toBeNull();
  });

  it("returns null for undefined input", () => {
    expect(todayTimeLabel(undefined)).toBeNull();
  });

  it("returns null for invalid date", () => {
    expect(todayTimeLabel("not-a-date")).toBeNull();
  });

  it("returns a time string for a date from today", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    // Today at 8:30 AM
    const label = todayTimeLabel("2026-06-17T08:30:00Z");
    expect(label).toBeTruthy();
    // Should look like a time (digits + separator + digits, optionally followed by AM/PM)
    expect(label).toMatch(/^\d{1,2}[:.]\d{2}(\s?(AM|PM))?$/i);
  });

  it("returns null for yesterday dates", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    expect(todayTimeLabel("2026-06-16T08:00:00Z")).toBeNull();
  });

  it("returns null for dates older than a week", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    expect(todayTimeLabel("2026-06-10T00:00:00Z")).toBeNull();
  });
});
