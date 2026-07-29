import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
  NotFoundState,
  PartialErrorState,
  UnauthorizedState,
  UnavailableState,
} from "@/components/ui/page-state";

afterEach(cleanup);

describe("shared page states", () => {
  it("renders accessible loading and empty states", () => {
    const { rerender } = render(<LoadingState label="Loading novels" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading novels");

    rerender(
      <EmptyState
        title="No novels available yet"
        description="Check back later."
        action={<button type="button">Browse help</button>}
      />,
    );

    expect(screen.getByRole("heading", { name: "No novels available yet" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Browse help" })).toBeInTheDocument();
  });

  it("announces errors without rendering technical details", () => {
    render(<ErrorState title="Something went wrong" description="Please try again." />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).not.toHaveTextContent("stack");
  });

  it.each([
    [UnavailableState, "Temporarily unavailable"],
    [NotFoundState, "Not found"],
    [UnauthorizedState, "Sign in required"],
    [ForbiddenState, "Permission required"],
    [PartialErrorState, "Part of this page is unavailable"],
  ])("renders %s with safe defaults", (Component, title) => {
    render(<Component />);

    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  });
});
