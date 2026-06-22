import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { LatestUpdateRow } from "@/components/public/latest-update-row";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("LatestUpdateRow grouped date display", () => {
  it("shows actual time when updatedAt is today (not 'Today' text)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-06-17T14:30:00Z"
      />
    );

    // Should NOT show "Today" as a time label (that's now the group header)
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
    // Old-style relative time text should not appear
    expect(screen.queryByText(/hours? ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/minutes? ago/i)).not.toBeInTheDocument();
  });

  it("shows no time text for yesterday items (group header is sufficient)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-06-16T00:00:00Z"
      />
    );

    expect(screen.getByText("Test Novel")).toBeInTheDocument();
    // No exact hour for older-than-24h items
    expect(screen.queryByText("Yesterday")).not.toBeInTheDocument();
    expect(screen.queryByText(/hours? ago/i)).not.toBeInTheDocument();
  });

  it("shows no time text for 1-week-ago items", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-06-12T00:00:00Z"
      />
    );

    expect(screen.getByText("Test Novel")).toBeInTheDocument();
    // No group label rendered in row — that's the group header's job
    expect(screen.queryByText("1 week ago")).not.toBeInTheDocument();
  });

  it("shows no time text for month-ago items", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-05-18T00:00:00Z"
      />
    );

    expect(screen.getByText("Test Novel")).toBeInTheDocument();
    expect(screen.queryByText(/month(s)? ago/i)).not.toBeInTheDocument();
  });

  it("renders no time label when updatedAt is missing", () => {
    render(
      <LatestUpdateRow
        href="/novels/test"
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
    expect(screen.queryByText(/month(s)? ago/i)).not.toBeInTheDocument();
  });

  it("renders no time label when updatedAt is null", () => {
    render(
      <LatestUpdateRow
        href="/novels/test"
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
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-06-17T07:00:00Z"
      />
    );

    // Should not show "5 hours ago" or similar
    expect(screen.queryByText(/hours? ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/minutes? ago/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ hours? ago/)).not.toBeInTheDocument();
  });

  it("renders chapter label when provided alongside time detail", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        chapterLabel="Chapter 15"
        updatedAt="2026-06-17T08:00:00Z"
      />
    );

    expect(screen.getByText("Chapter 15")).toBeInTheDocument();
  });

  it("prefers latest chapter number and title when available", () => {
    render(
      <LatestUpdateRow
        href="/novels/test/chapter/ch015"
        title="Test Novel"
        chapterLabel="Chapter 15 translated"
        latestChapterNumber={15}
        latestChapterTitle="The Quiet Return"
      />
    );

    expect(screen.getByText("Chapter 15: The Quiet Return")).toBeInTheDocument();
    expect(screen.queryByText("Chapter 15 translated")).not.toBeInTheDocument();
  });

  it("renders latest chapter number without title when title is missing", () => {
    render(
      <LatestUpdateRow
        href="/novels/test/chapter/ch015"
        title="Test Novel"
        latestChapterNumber={15}
      />
    );

    expect(screen.getByText("Chapter 15")).toBeInTheDocument();
  });

  it("keeps the provided href for latest chapter links", () => {
    render(
      <LatestUpdateRow
        href="/novels/test/chapter/ch015"
        title="Test Novel"
        latestChapterNumber={15}
        latestChapterTitle="The Quiet Return"
      />
    );

    expect(screen.getByRole("link", { name: /test novel/i })).toHaveAttribute(
      "href",
      "/novels/test/chapter/ch015"
    );
  });

  it("renders time detail as secondary-styled span without clock icon", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    render(
      <LatestUpdateRow
        href="/novels/test"
        title="Test Novel"
        updatedAt="2026-06-17T14:30:00Z"
      />
    );

    // No clock icon (svg) alongside time text
    const timeElements = document.querySelectorAll("span.font-metadata");
    timeElements.forEach((el) => {
      expect(el.querySelector("svg")).toBeNull();
    });
  });
});
