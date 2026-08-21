/**
 * Ranking page contract checks.
 *
 * Feature: visual-atmosphere-polish
 */

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";

const __root = dirname(fileURLToPath(import.meta.url));
const rankingPageSrc = readFileSync(
  join(__root, "..", "ranking", "page.tsx"),
  "utf-8"
);
const rankingClientSrc = readFileSync(
  join(__root, "..", "ranking", "ranking-client.tsx"),
  "utf-8"
);

describe("Ranking page source honesty", () => {
  it('does not contain "Metrics pending" badge text', () => {
    expect(rankingPageSrc).not.toContain("Metrics pending");
  });

  it('does not contain "Trending Now" copy', () => {
    expect(rankingPageSrc).not.toMatch(/Trending Now/);
  });

  it('does not contain "Library Stats" copy', () => {
    expect(rankingPageSrc).not.toMatch(/Library Stats/);
  });

  it('does not display fake view counts (e.g. "125 views")', () => {
    // Bare "views" is allowed — the page honestly says "No views..."
    // but never shows a fake view count
    expect(rankingPageSrc).not.toMatch(/\d+\s*views/i);
  });

  it('does not display fake like counts', () => {
    expect(rankingPageSrc).not.toMatch(/\d+\s*likes/i);
  });

  it("uses the live ranking API and current periods", () => {
    expect(rankingClientSrc).toContain("usePublicRankings");
    expect(rankingClientSrc).toContain('"daily"');
    expect(rankingClientSrc).toContain('"weekly"');
    expect(rankingClientSrc).toContain('"monthly"');
    expect(rankingClientSrc).not.toContain("All Time");
  });

  it("uses the backend unique-view metric without fabricated counts", () => {
    expect(rankingClientSrc).toContain("unique_views");
    expect(rankingClientSrc).toContain("analytics_disabled");
    expect(rankingClientSrc).not.toContain("125 views");
  });

  it('does not contain "Data contract pending" jargon', () => {
    expect(rankingPageSrc).not.toContain("Data contract pending");
  });

  it("keeps metadata on the route wrapper", () => {
    expect(rankingPageSrc).toContain("Public rankings based on distinct novel-detail views.");
  });
});
