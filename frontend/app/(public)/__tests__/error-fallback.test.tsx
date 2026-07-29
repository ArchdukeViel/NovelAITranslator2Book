import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PublicErrorPage from "@/app/(public)/error";
import { ApiError } from "@/lib/api";

// ---------------------------------------------------------------------------
// not-found test (server component, no mocking needed)
// ---------------------------------------------------------------------------

// Dynamic import so we get the default export
async function renderNotFound() {
  const mod = await import("@/app/(public)/not-found");
  const Component = mod.default;
  return render(<Component />);
}

describe("public not-found boundary", () => {
  afterEach(cleanup);

  it("renders NotFoundState with page not found message", async () => {
    const { container } = await renderNotFound();
    expect(screen.getByRole("heading", { name: /not found/i }));
    // Verify it uses the shared card structure (has border/rounded classes)
    const section = container.querySelector('[role="status"]');
    expect(section).toBeInTheDocument();
  });

  it("provides navigation links", async () => {
    await renderNotFound();
    const homeLink = screen.getByRole("link", { name: /return home/i });
    expect(homeLink).toHaveAttribute("href", "/home");
    const catalogLink = screen.getByRole("link", { name: /browse catalog/i });
    expect(catalogLink).toHaveAttribute("href", "/browse-novels");
  });
});

// ---------------------------------------------------------------------------
// error boundary test (client component with error+reset props)
// ---------------------------------------------------------------------------

describe("public error boundary", () => {
  afterEach(cleanup);

  const baseError = new Error("Something crashed");
  const mockReset = () => {};

  it("renders ErrorState with alert role", () => {
    render(<PublicErrorPage error={baseError} reset={mockReset} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("shows safe generic error message without technical details", () => {
    render(<PublicErrorPage error={baseError} reset={mockReset} />);
    expect(
      screen.getByRole("heading", { name: /something went wrong/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/stack/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/trace/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Something crashed/)).not.toBeInTheDocument();
  });

  it("renders a try-again button calling reset()", () => {
    let resetCalled = false;
    render(
      <PublicErrorPage
        error={baseError}
        reset={() => {
          resetCalled = true;
        }}
      />,
    );
    const button = screen.getByRole("button", { name: /try again/i });
    expect(button).toBeInTheDocument();
    button.click();
    expect(resetCalled).toBe(true);
  });

  it("renders a browse catalog link", () => {
    render(<PublicErrorPage error={baseError} reset={mockReset} />);
    const catalogLink = screen.getByRole("link", { name: /browse catalog/i });
    expect(catalogLink).toHaveAttribute("href", "/browse-novels");
  });

  it("does not leak ApiError.raw or trace_id for 5xx errors", () => {
    const serverError = new ApiError({
      status: 500,
      code: "HTTP_500",
      message: "Internal leak",
      raw: { secret: "sensitive" },
      trace_id: "trace-xyz",
    });
    render(<PublicErrorPage error={serverError} reset={mockReset} />);
    expect(screen.queryByText(/sensitive/)).not.toBeInTheDocument();
    expect(screen.queryByText(/trace-xyz/)).not.toBeInTheDocument();
  });
});
