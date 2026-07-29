import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { PublicShell } from "@/components/public/public-shell";

vi.mock("@/components/public/public-header", () => ({ PublicHeader: () => <header /> }));
vi.mock("@/components/public/public-sidebar", () => ({ PublicSidebar: () => <aside /> }));
vi.mock("@/components/public/public-footer", () => ({ PublicFooter: () => <footer /> }));

afterEach(cleanup);

it("provides skip link and focusable content target", () => {
  render(<PublicShell><main>Reader</main></PublicShell>);

  expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
  expect(document.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
  expect(document.querySelectorAll("main")).toHaveLength(1);
});
