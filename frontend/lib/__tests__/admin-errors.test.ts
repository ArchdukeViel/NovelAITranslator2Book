import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { formatAdminError, formatAdminErrorString } from "../admin-errors";
import { ApiError } from "../api";

// Feature: admin-ui-rework, Property 6: Error output redacts secrets

// Test helper to generate random secret-like strings
const secretGenerators = {
  bearerToken: fc.string({ minLength: 20, maxLength: 50 }).map(
    (s) => `Bearer ${s.replace(/[^A-Za-z0-9\-._~+/]/g, "x")}`
  ),
  googleApiKey: fc.constantFrom(
    "AIzaSyD1234567890abcdefghijklmnop",
    "AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "AIzaSy" + fc.sample(fc.hexaString({ maxLength: 30 }), 1)[0]
  ).map((s) => s.slice(0, 39)),
  openAiKey: fc.string({ minLength: 25, maxLength: 40 }).map(
    (s) => `sk-${s.replace(/[^A-Za-z0-9]/g, "a")}`.slice(0, 40)
  ),
  cookieString: fc.record({
    name: fc.oneof(
      fc.constant("session_id"),
      fc.constant("auth_token"),
      fc.constant("access_token")
    ),
    value: fc.string({ minLength: 20, maxLength: 40 }),
  }).map((c) => `${c.name}=${c.value}; Path=/`),
  authorizationHeader: fc.record({
    scheme: fc.oneof(fc.constant("Basic"), fc.constant("Bearer"), fc.constant("Digest")),
    credentials: fc.string({ minLength: 20, maxLength: 40 }),
  }).map((h) => `Authorization: ${h.scheme} ${h.credentials}`),
  apiKey: fc.record({
    prefix: fc.oneof(
      fc.constant("api_key"),
      fc.constant("api-key"),
      fc.constant("apikey"),
      fc.constant("x-api-key")
    ),
    value: fc.string({ minLength: 20, maxLength: 40 }),
  }).map((k) => `${k.prefix}=${k.value}`),
  sessionToken: fc.record({
    type: fc.oneof(
      fc.constant("session_token"),
      fc.constant("session-token"),
      fc.constant("X-Session-Token")
    ),
    value: fc.string({ minLength: 20, maxLength: 40 }),
  }).map((s) => `${s.type}=${s.value}`),
};

describe("formatAdminError", () => {
  // Property 6: For any error value embedding keys/headers/cookies/session tokens/stack traces,
  // assert the produced message contains none of those secret substrings and no raw stack trace.
  // Min 100 iterations.
  it("redacts secrets from error messages", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          // Bearer tokens
          secretGenerators.bearerToken.map(
            (token) => ({ type: "string", value: `Request failed: ${token}` })
          ),
          // Google API keys
          secretGenerators.googleApiKey.map(
            (key) => ({ type: "string", value: `Invalid API key: ${key}` })
          ),
          // OpenAI keys
          secretGenerators.openAiKey.map(
            (key) => ({ type: "string", value: `Error: ${key}` })
          ),
          // Cookies
          secretGenerators.cookieString.map(
            (cookie) => ({ type: "string", value: `Cookie error: ${cookie}` })
          ),
          // Authorization headers
          secretGenerators.authorizationHeader.map(
            (auth) => ({ type: "string", value: `Auth error: ${auth}` })
          ),
          // API keys
          secretGenerators.apiKey.map(
            (key) => ({ type: "string", value: `API key issue: ${key}` })
          ),
          // Session tokens
          secretGenerators.sessionToken.map(
            (token) => ({ type: "string", value: `Session error: ${token}` })
          )
        ),
        ({ value }) => {
          const result = formatAdminError(value);
          
          // The result should not contain the raw secret values
          // Check that none of the secret patterns are present in the output
          
          // Bearer tokens should be redacted
          expect(result.message).not.toMatch(/Bearer\s+[A-Za-z0-9\-._~+/]+=/i);
          
          // Google API keys should be redacted
          expect(result.message).not.toMatch(/AIza[A-Za-z0-9\-_]{20,}/);
          
          // OpenAI keys should be redacted
          expect(result.message).not.toMatch(/sk-[A-Za-z0-9]{20,}/);
          
          // Authorization headers should be redacted
          expect(result.message).not.toMatch(/Authorization:\s*.+/i);
          
          // Cookies should be redacted
          expect(result.message).not.toMatch(/cookie[:\s]+[^\r\n;]*/i);
          
          // Session tokens should be redacted
          expect(result.message).not.toMatch(/session[_\-]?token[=\s]+/i);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("removes stack traces from error messages", () => {
    const errorWithStackTrace = `Error: Something went wrong
    at Function.validate (C:\\projects\\app\\src\\lib\\auth.ts:123:45)
    at processTicksAndRejections (node:internal/process/task_queues:95:10)
    at async main (C:\\projects\\app\\src\\index.ts:45:67)`;

    const result = formatAdminError(errorWithStackTrace);

    // Should not contain the stack trace lines
    expect(result.message).not.toMatch(/at\s+.+\(/);
    expect(result.message).not.toMatch(/File\s+"/);
    expect(result.message).not.toMatch(/\^\s*/);
    // But should preserve the main message
    expect(result.message).toContain("Error: Something went wrong");
  });

  it("handles Python/Traceback style stack traces", () => {
    const pythonError = `Error: Database connection failed
Traceback (most recent call last):
  File "app.py", line 45, in <module>
    main()
  File "app.py", line 23, in connect
    raise ConnectionError("Database unavailable")`;

    const result = formatAdminError(pythonError);

    // Should remove the traceback
    expect(result.message).not.toMatch(/Traceback/);
    expect(result.message).not.toMatch(/File\s+"/);
    expect(result.message).not.toMatch(/line\s+\d+/);
    // But preserve the error message
    expect(result.message).toContain("Database connection failed");
  });

  it("handles ApiError objects with trace_id", () => {
    const apiError = new ApiError({
      status: 401,
      message: "Authentication failed",
      code: "AUTH_ERROR",
      explanation: "The Bearer token has expired",
      trace_id: "req_abc123",
    });

    const result = formatAdminError(apiError);

    // Should return message and trace_id
    expect(result.message).toContain("Authentication failed");
    expect(result.trace_id).toBe("req_abc123");
  });

  it("handles plain Error objects", () => {
    const error = new Error("Something went wrong");

    const result = formatAdminError(error);

    expect(result.message).toBe("Something went wrong");
  });

  it("handles string errors", () => {
    const result = formatAdminError("Simple error message");
    expect(result.message).toBe("Simple error message");
  });

  it("handles objects with message field", () => {
    const result = formatAdminError({ message: "Object error", code: 123 });
    expect(result.message).toBe("Object error");
  });

  it("handles unknown error types with fallback", () => {
    const result = formatAdminError(12345, "Custom fallback");
    expect(result.message).toBe("Custom fallback");
  });

  it("extracts trace_id from various object fields", () => {
    const errorWithTraceId = { message: "Error", trace_id: "trace_123" };
    const result = formatAdminError(errorWithTraceId);
    expect(result.trace_id).toBe("trace_123");

    const errorWithRequestId = { message: "Error", request_id: "req_456" };
    const result2 = formatAdminError(errorWithRequestId);
    expect(result2.trace_id).toBe("req_456");
  });

  it("never returns raw details/raw from ApiError", () => {
    const apiError = new ApiError({
      status: 500,
      message: "Internal server error",
      code: "INTERNAL_ERROR",
      details: { secret: "sk-1234567890abcdef", stack: "Error at line 1" },
      raw: "Raw response data with secrets: Bearer token123",
    });

    const result = formatAdminError(apiError);

    // Should only return the message, not details or raw
    expect(result.message).toBe("500 Internal server error");
    // Should NOT contain the secret from details
    expect(result.message).not.toContain("sk-1234567890");
    expect(result.message).not.toContain("secret");
    // Should NOT contain the raw response
    expect(result.message).not.toContain("Raw response");
    expect(result.message).not.toContain("Bearer token");
  });

  it("redacts secrets embedded in error explanation", () => {
    const apiError = new ApiError({
      status: 400,
      message: "Validation failed",
      code: "VALIDATION_ERROR",
      explanation:
        "The API key AIzaSyD1234567890abcdefghijklmnop is invalid. Bearer sk-1234567890abcdefghij was rejected.",
    });

    const result = formatAdminError(apiError);

    // Both secrets should be redacted
    expect(result.message).not.toContain("AIzaSyD1234567890");
    expect(result.message).not.toContain("sk-1234567890abcdef");
    expect(result.message).toContain("Validation failed");
  });
});

describe("formatAdminErrorString", () => {
  it("returns just the message string for backward compatibility", () => {
    const error = new Error("Test error");
    const result = formatAdminErrorString(error);
    expect(typeof result).toBe("string");
    expect(result).toBe("Test error");
  });

  it("handles ApiError with trace_id", () => {
    const apiError = new ApiError({
      status: 404,
      message: "Not found",
      code: "NOT_FOUND",
      trace_id: "req_xyz",
    });
    const result = formatAdminErrorString(apiError);
    expect(result).toContain("404 Not found");
    // trace_id should be separate
    const fullResult = formatAdminError(apiError);
    expect(fullResult.trace_id).toBe("req_xyz");
  });
});