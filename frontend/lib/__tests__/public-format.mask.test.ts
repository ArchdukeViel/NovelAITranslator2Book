// Feature: public-reader-rework, Property 9: Masked credential never reveals the full value
// **Validates: Requirements 17.7**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { maskCredential } from "@/lib/public-format";

describe("Property 9: Masked credential never reveals the full value", () => {
  it("for any non-empty string, the masked result is never equal to the raw input", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 200 }),
        fc.integer({ min: 1, max: 10 }),
        fc.integer({ min: 1, max: 10 }),
        (raw, prefix, suffix) => {
          const masked = maskCredential(raw, prefix, suffix);
          expect(masked).not.toBe(raw);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("the masked result exposes at most the configured prefix and suffix characters", () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 200 }),
        fc.integer({ min: 1, max: 10 }),
        fc.integer({ min: 1, max: 10 }),
        (raw, prefix, suffix) => {
          const masked = maskCredential(raw, prefix, suffix);

          // The masked result must contain the ellipsis marker
          expect(masked).toContain("…");

          if (raw.length > prefix + suffix) {
            // For long strings: result is prefix chars + "…" + suffix chars
            const expectedPrefix = raw.slice(0, prefix);
            const expectedSuffix = raw.slice(-suffix);
            expect(masked.startsWith(expectedPrefix)).toBe(true);
            expect(masked.endsWith(expectedSuffix)).toBe(true);

            // Total exposed characters must not exceed prefix + suffix
            const exposedLength = masked.replace("…", "").length;
            expect(exposedLength).toBeLessThanOrEqual(prefix + suffix);
          } else {
            // For short strings: exposed portion is at most floor(length/2)
            const exposedPart = masked.replace("…", "");
            expect(exposedPart.length).toBeLessThanOrEqual(
              Math.max(1, Math.floor(raw.length / 2))
            );
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("for values longer than prefix+suffix, the middle is masked with ellipsis", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10 }),
        fc.integer({ min: 1, max: 10 }),
        fc.string({ minLength: 1, maxLength: 200 }).filter(
          (s) => s.length > 0
        ),
        (prefix, suffix, base) => {
          // Ensure the raw string is longer than prefix + suffix
          const minLen = prefix + suffix + 1;
          const raw = base.padEnd(minLen, "x").slice(0, Math.max(base.length, minLen));
          fc.pre(raw.length > prefix + suffix);

          const masked = maskCredential(raw, prefix, suffix);

          // Must contain the ellipsis in the middle (not just at start or end)
          expect(masked).toContain("…");

          // Structure: prefix portion + "…" + suffix portion
          const parts = masked.split("…");
          expect(parts.length).toBe(2);
          expect(parts[0]).toBe(raw.slice(0, prefix));
          expect(parts[1]).toBe(raw.slice(-suffix));
        }
      ),
      { numRuns: 100 }
    );
  });
});
