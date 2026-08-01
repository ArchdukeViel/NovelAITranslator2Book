import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PublicShell } from "@/components/public/public-shell";

const pathnameMock = vi.fn(() => "/home");

vi.mock("next/navigation", () => ({
  usePathname: () => pathnameMock(),
}));

vi.mock("@/components/public/public-header", () => ({ PublicHeader: () => <header /> }));
vi.mock("@/components/public/mobile-tab-bar", () => ({ MobileTabBar: () => <nav /> }));
vi.mock("@/components/public/public-footer", () => ({ PublicFooter: () => <footer /> }));
// SearchOverlay needs its own router/query mocks; it is covered by its own
// test file, so stub it here to keep this suite focused on shell chrome.
vi.mock("@/components/public/search-overlay", () => ({ SearchOverlay: () => <aside aria-label="Search overlay stub" /> }));

afterEach(() => {
  cleanup();
  pathnameMock.mockReset();
  pathnameMock.mockReturnValue("/home");
});

it("provides skip link and focusable content target", () => {
  render(<PublicShell><main>Reader</main></PublicShell>);

  expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
  expect(document.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
  expect(document.querySelectorAll("main")).toHaveLength(1);
});

it("suppresses header, tab bar, and footer on chapter reader routes", () => {
  pathnameMock.mockReturnValue("/novels/some-novel/chapter/42");
  render(<PublicShell><main>Chapter</main></PublicShell>);

  // Skip link stays (still needed to jump to content)
  expect(screen.getByRole("link", { name: "Skip to main content" })).toBeInTheDocument();
  // Header, tab bar, and footer are hidden while reading
  expect(document.querySelector("header")).not.toBeInTheDocument();
  expect(document.querySelector("nav")).not.toBeInTheDocument();
  expect(document.querySelector("footer")).not.toBeInTheDocument();
});

it("shows header, tab bar, and footer on normal browsing routes", () => {
  pathnameMock.mockReturnValue("/browse-novels");
  render(<PublicShell><main>Browse</main></PublicShell>);

  expect(document.querySelector("header")).toBeInTheDocument();
  expect(document.querySelector("nav")).toBeInTheDocument();
  expect(document.querySelector("footer")).toBeInTheDocument();
});

it("suppresses the mobile tab bar on novel detail for the sticky reading action", () => {
  pathnameMock.mockReturnValue("/novels/some-novel");
  render(<PublicShell><main>Detail</main></PublicShell>);

  expect(document.querySelector("header")).toBeInTheDocument();
  expect(document.querySelector("nav")).not.toBeInTheDocument();
  expect(document.querySelector("footer")).toBeInTheDocument();
});
