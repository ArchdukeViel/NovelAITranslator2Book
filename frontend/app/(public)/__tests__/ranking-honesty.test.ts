/**
 * Ranking page visual honesty.
 *
 * Confirms the ranking page source text uses honest copy and does not
 * contain "Metrics pending", "Trending Now", or fake stat labels.
 *
 * The ranking page is a server component, so we verify the source
 * directly rather than rendering it through jsdom.
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

  it('contains "Ranking is not live yet" badge text', () => {
    expect(rankingPageSrc).toContain("Ranking is not live yet");
  });

  it('contains honest "Not available yet" aside', () => {
    expect(rankingPageSrc).toContain("Not available yet");
  });

  it('does not contain "Data contract pending" jargon', () => {
    expect(rankingPageSrc).not.toContain("Data contract pending");
  });

  it('contains honest disclaimer about what is not shown', () => {
    // The page should honestly state that specific metrics are absent
    expect(rankingPageSrc).toMatch(/no\s+views/i);
  });

  it('contains "Rankings are not live" subheading', () => {
    expect(rankingPageSrc).toContain("Rankings are not live");
  });
});
