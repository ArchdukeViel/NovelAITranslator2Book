import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { errorToProps, safeErrorMessage } from "@/lib/api-error";

describe("safeErrorMessage", () => {
  it("redacts 5xx messages to generic server message", () => {
    const err = new ApiError({
      status: 500,
      code: "HTTP_500",
      message: "Internal server error with sensitive details",
    });
    expect(safeErrorMessage(err)).toBe("Something went wrong. Please try again.");
  });

  it("preserves 4xx messages (safe status codes)", () => {
    const err = new ApiError({ status: 404, code: "HTTP_404", message: "Not found" });
    expect(safeErrorMessage(err)).toBe("Not found");
  });

  it("preserves 4xx message for 400-level errors", () => {
    const err = new ApiError({ status: 422, code: "VALIDATION_ERROR", message: "Invalid input" });
    expect(safeErrorMessage(err)).toBe("Invalid input");
  });

  it("redacts network TypeError", () => {
    const err = new TypeError("Failed to fetch");
    expect(safeErrorMessage(err)).toBe(
      "A network error occurred. Check your connection and try again.",
    );
  });

  it("redacts network-like error messages", () => {
    const err = new Error("fetch failed");
    expect(safeErrorMessage(err)).toBe(
      "A network error occurred. Check your connection and try again.",
    );
  });

  it("handles generic Error", () => {
    const err = new Error("Something broke");
    expect(safeErrorMessage(err)).toBe("Something went wrong.");
  });

  it("handles unknown error values", () => {
    expect(safeErrorMessage("string error")).toBe("Something went wrong.");
    expect(safeErrorMessage(null)).toBe("Something went wrong.");
    expect(safeErrorMessage(undefined)).toBe("Something went wrong.");
    expect(safeErrorMessage(42)).toBe("Something went wrong.");
  });
});

describe("errorToProps", () => {
  it("maps 404 ApiError to NotFoundState props", () => {
    const err = new ApiError({ status: 404, code: "HTTP_404", message: "Not found" });
    const props = errorToProps(err);
    expect(props.title).toBe("Not found");
    expect(props.description).toBe("The resource you requested could not be found.");
  });

  it("maps 401 ApiError to UnauthorizedState props", () => {
    const err = new ApiError({ status: 401, code: "UNAUTHORIZED", message: "Unauthorized" });
    const props = errorToProps(err);
    expect(props.title).toBe("Sign in required");
    expect(props.description).toBe("Please sign in to continue.");
  });

  it("maps 403 ApiError to ForbiddenState props", () => {
    const err = new ApiError({ status: 403, code: "FORBIDDEN", message: "Forbidden" });
    const props = errorToProps(err);
    expect(props.title).toBe("Permission required");
    expect(props.description).toBe("You do not have permission to view this resource.");
  });

  it("maps 503 ApiError to UnavailableState props", () => {
    const err = new ApiError({ status: 503, code: "HTTP_503", message: "Service Unavailable" });
    const props = errorToProps(err);
    expect(props.title).toBe("Temporarily unavailable");
    expect(props.description).toBe("This service is temporarily unavailable. Please try again later.");
  });

  it("maps 500 ApiError to generic error props (fully redacted)", () => {
    const err = new ApiError({ status: 500, code: "HTTP_500", message: "Internal error" });
    const props = errorToProps(err);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).toBe("Something went wrong. Please try again.");
  });

  it("maps other 4xx (400) to generic error with explanation if available", () => {
    const err = new ApiError({
      status: 400,
      code: "BAD_REQUEST",
      message: "Bad request",
      explanation: "The request was malformed.",
    });
    const props = errorToProps(err);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).toBe("The request was malformed.");
  });

  it("maps other 4xx (400) to generic error without explanation", () => {
    const err = new ApiError({ status: 400, code: "BAD_REQUEST", message: "Bad request" });
    const props = errorToProps(err);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).toBe("Something went wrong.");
  });

  it("never exposes raw, details, or trace_id in props", () => {
    const err = new ApiError({
      status: 500,
      code: "HTTP_500",
      message: "Internal error",
      raw: { secret: "leak" },
      details: { query: "SELECT * FROM users" },
      trace_id: "trace-abc-123",
    });
    const props = errorToProps(err);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).not.toContain("leak");
    expect(props.description).not.toContain("SELECT");
    expect(props.description).not.toContain("trace-abc-123");
  });

  it("maps generic Error to safe props", () => {
    const err = new Error("Random failure");
    const props = errorToProps(err);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).toBe("Something went wrong.");
  });

  it("maps unknown error to safe props", () => {
    const props = errorToProps(null);
    expect(props.title).toBe("Something went wrong");
    expect(props.description).toBe("Something went wrong.");
  });

  it("includes backend explanation when available for known HTTP codes", () => {
    const err = new ApiError({
      status: 404,
      code: "NOT_FOUND",
      message: "Not found",
      explanation: "This novel has been removed by the author.",
    });
    const props = errorToProps(err);
    expect(props.title).toBe("Not found");
    expect(props.description).toBe("This novel has been removed by the author.");
  });
});
