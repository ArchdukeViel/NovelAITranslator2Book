import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { LatestUpdateRow } from "@/components/public/latest-update-row";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("LatestUpdateRow grouped date display", () => {
  it('shows "Today" when updatedAt is today', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-06-17T08:00:00Z"
      />
    );

    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it('shows "Yesterday" when updatedAt is yesterday', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-06-16T00:00:00Z"
      />
    );

    expect(screen.getByText("Yesterday")).toBeInTheDocument();
  });

  it('shows "1 week ago" when updatedAt is 5 days ago', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-06-12T00:00:00Z"
      />
    );

    expect(screen.getByText("1 week ago")).toBeInTheDocument();
  });

  it('shows "Last month" when updatedAt is 30 days ago', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-05-18T00:00:00Z"
      />
    );

    expect(screen.getByText("Last month")).toBeInTheDocument();
  });

  it('shows "Mon YYYY" when updatedAt is more than 2 months ago', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-03-01T00:00:00Z"
      />
    );

    expect(screen.getByText("Mar 2026")).toBeInTheDocument();
  });

  it("renders no time label when updatedAt is missing", () => {
    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        chapterLabel="Chapter 5"
      />
    );

    expect(screen.getByText("Test Novel")).toBeInTheDocument();
    expect(screen.getByText("Chapter 5")).toBeInTheDocument();
    // No grouped date labels present
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
    expect(screen.queryByText("Yesterday")).not.toBeInTheDocument();
    expect(screen.queryByText(/week(s)? ago/)).not.toBeInTheDocument();
    expect(screen.queryByText("Last month")).not.toBeInTheDocument();
  });

  it("renders no time label when updatedAt is null", () => {
    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt={null}
      />
    );

    expect(screen.queryByText(/^(Today|Yesterday)/)).not.toBeInTheDocument();
  });

  it("renders no exact 'hours ago' text", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        // 5 hours ago - should NOT show "5 hours ago"
        updatedAt="2026-06-17T07:00:00Z"
      />
    );

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.queryByText(/hours? ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/minutes? ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ hours? ago/)).not.toBeInTheDocument();
  });

  it("renders chapter label when provided alongside time label", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        chapterLabel="Chapter 15"
        updatedAt="2026-06-17T08:00:00Z"
      />
    );

    expect(screen.getByText("Chapter 15")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("renders time label as secondary-styled element", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novel/test"
        title="Test Novel"
        updatedAt="2026-06-17T08:00:00Z"
      />
    );

    const timeEl = screen.getByText("Today");
    // Should be a span (not a heading/button/link)
    expect(timeEl.tagName).toBe("SPAN");
    // Should not be a clock icon
    expect(timeEl.querySelector("svg")).toBeNull();
  });
});
