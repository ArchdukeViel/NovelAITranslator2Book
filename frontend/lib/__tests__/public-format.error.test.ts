// Feature: public-reader-rework, Property 10: Error messages redact secrets and stack traces
// **Validates: Requirements 2.8, 4.8, 5.8, 13.5, 17.14**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { toReaderError } from "@/lib/public-format";
import { ApiError } from "@/lib/api";

/**
 * Helper: create an ApiError with an embedded sensitive value in the message.
 */
function makeApiError(message: string): InstanceType<typeof ApiError> {
  return new ApiError({
    status: 500,
    code: "INTERNAL",
    message,
  });
}

/**
 * Arbitrary: generates a random Bearer token (base64-ish string of 20-80 chars).
 */
const bearerTokenArb = fc
  .stringOf(fc.constantFrom(..."ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~+/"), { minLength: 20, maxLength: 80 })
  .map((token) => `Bearer ${token}`);

/**
 * Arbitrary: generates a random Authorization header value (e.g., "Authorization: <scheme> <value>").
 */
const authHeaderArb = fc
  .tuple(
    fc.constantFrom("Bearer", "Basic", "Token", "ApiKey"),
    fc.stringOf(fc.constantFrom(..."ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~+/="), { minLength: 10, maxLength: 60 })
  )
  .map(([scheme, value]) => `Authorization: ${scheme} ${value}`);

/**
 * Arbitrary: generates a session-like value (session_id=... or session:...).
 */
const sessionValueArb = fc
  .tuple(
    fc.constantFrom("session_id:", "session-id=", "session_id=", "session:", "session ="),
    fc.stringOf(fc.constantFrom(..."ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~+/"), { minLength: 16, maxLength: 50 })
  )
  .map(([prefix, value]) => `${prefix}${value}`);

/**
 * Arbitrary: generates a stack trace line.
 */
const stackTraceArb = fc.constantFrom(
  "at Object.<anonymous> (/app/src/server.ts:42:15)",
  "at processTicksAndRejections (internal/process/task_queues.js:95:5)",
  "at Module._compile (internal/modules/cjs/loader.js:778:30)",
  "    at Router.handle (/node_modules/express/lib/router/index.js:174:12)",
  '    at Layer.handle [as handle_request] (/node_modules/express/lib/router/layer.js:95:5)',
  'File "app/main.py", line 42',
  "Traceback (most recent call last)\n  File \"app.py\", line 10\n    raise ValueError(\"oops\")"
);

/**
 * Arbitrary: generates an API-key-like credential string.
 */
const credentialArb = fc
  .tuple(
    fc.constantFrom("AIza", "sk-", "key-"),
    fc.stringOf(fc.constantFrom(..."ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"), { minLength: 30, maxLength: 60 })
  )
  .map(([prefix, rest]) => `${prefix}${rest}`);

/**
 * Arbitrary: prefix and suffix text to wrap around the sensitive value.
 */
const contextArb = fc.tuple(
  fc.stringOf(fc.constantFrom(..."abcdefghijklmnopqrstuvwxyz "), { minLength: 0, maxLength: 30 }),
  fc.stringOf(fc.constantFrom(..."abcdefghijklmnopqrstuvwxyz "), { minLength: 0, maxLength: 30 })
);

describe("Property 10: Error messages redact secrets and stack traces", () => {
  it("Bearer tokens embedded in ApiError messages are redacted from the output", () => {
    fc.assert(
      fc.property(bearerTokenArb, contextArb, (bearer, [prefix, suffix]) => {
        const message = `${prefix} ${bearer} ${suffix}`;
        const error = makeApiError(message);
        const result = toReaderError(error);

        // The raw Bearer token value (everything after "Bearer ") must not appear
        const tokenValue = bearer.replace(/^Bearer\s+/, "");
        if (tokenValue.length > 5) {
          expect(result).not.toContain(tokenValue);
        }
      }),
      { numRuns: 100 }
    );
  });

  it("Authorization header values embedded in ApiError messages are redacted from the output", () => {
    fc.assert(
      fc.property(authHeaderArb, contextArb, (authHeader, [prefix, suffix]) => {
        const message = `${prefix} ${authHeader} ${suffix}`;
        const error = makeApiError(message);
        const result = toReaderError(error);

        // Extract the full credential portion after "Authorization: "
        const credentialPart = authHeader.replace(/^Authorization:\s*/, "");
        if (credentialPart.length > 5) {
          expect(result).not.toContain(credentialPart);
        }
      }),
      { numRuns: 100 }
    );
  });

  it("session-like values embedded in ApiError messages are redacted from the output", () => {
    fc.assert(
      fc.property(sessionValueArb, contextArb, (sessionVal, [prefix, suffix]) => {
        const message = `${prefix} ${sessionVal} ${suffix}`;
        const error = makeApiError(message);
        const result = toReaderError(error);

        // The full session pattern should be redacted
        expect(result).not.toContain(sessionVal);
      }),
      { numRuns: 100 }
    );
  });

  it("stack traces embedded in errors are redacted from the output", () => {
    fc.assert(
      fc.property(stackTraceArb, contextArb, (trace, [prefix, suffix]) => {
        const message = `${prefix} ${trace} ${suffix}`;
        const error = makeApiError(message);
        const result = toReaderError(error);

        // Stack trace patterns should be redacted
        // Check the identifiable parts of the trace are gone
        expect(result).not.toMatch(/at\s+.+\(.+:\d+:\d+\)/);
        expect(result).not.toMatch(/^\s+at\s+.+$/m);
        expect(result).not.toMatch(/File\s+"[^"]+",\s+line\s+\d+/i);
        expect(result).not.toMatch(/Traceback\s*\(most recent call last\)/i);
      }),
      { numRuns: 100 }
    );
  });

  it("credential-like strings (AIza..., sk-..., key-...) in ApiError messages are redacted", () => {
    fc.assert(
      fc.property(credentialArb, contextArb, (credential, [prefix, suffix]) => {
        const message = `${prefix} ${credential} ${suffix}`;
        const error = makeApiError(message);
        const result = toReaderError(error);

        // The raw credential must not appear in the output
        expect(result).not.toContain(credential);
      }),
      { numRuns: 100 }
    );
  });
});
