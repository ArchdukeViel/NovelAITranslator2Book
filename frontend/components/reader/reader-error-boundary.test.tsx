import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReaderErrorBoundary } from "@/components/reader/reader-error-boundary";

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function Thrower(): never {
  throw new Error("Boom: ruby parser failed");
}

function renderBoundary(props: { novelSlug?: string; plainText?: string | null } = {}) {
  return render(
    <ReaderErrorBoundary novelSlug="demo-novel" plainText="First line. Second line." {...props}>
      <Thrower />
    </ReaderErrorBoundary>,
  );
}

beforeEach(() => {
  // React logs caught render errors via console.error; silence them so the
  // suite's strict console.error guard does not treat them as failures.
  vi.spyOn(console, "error").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ReaderErrorBoundary recovery (REQ-6, AC-6)", () => {
  it("renders retry, plain-text recovery, and table-of-contents actions on failure", () => {
    renderBoundary();
    expect(screen.getByRole("button", { name: /retry chapter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view plain text/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /novel overview/i })).toHaveAttribute("href", "/novels/demo-novel");
  });

  it("renders raw chapter text without rich formatting in plain-text mode", () => {
    renderBoundary();
    fireEvent.click(screen.getByRole("button", { name: /view plain text/i }));
    expect(screen.getByText("First line. Second line.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try rich view again/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to table of contents/i })).toHaveAttribute(
      "href",
      "/novels/demo-novel",
    );
  });

  it("explains when plain text is unavailable", () => {
    renderBoundary({ plainText: null });
    fireEvent.click(screen.getByRole("button", { name: /view plain text/i }));
    expect(screen.getByText(/unavailable in plain-text mode/i)).toBeInTheDocument();
  });
});
