// Feature: public-reader-rework, Property 12: Font size stays within the inclusive range [15, 24]
// **Validates: Requirements 6.1, 6.2**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { clampReaderFontSize } from "@/lib/public-format";

describe("Property 12: Font size stays within the inclusive range [15, 24]", () => {
  it("for any number, the result is always an integer in [15, 24]", () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true }),
        (size) => {
          const result = clampReaderFontSize(size);
          // Result must be an integer
          expect(Number.isInteger(result)).toBe(true);
          // Result must be within [15, 24]
          expect(result).toBeGreaterThanOrEqual(15);
          expect(result).toBeLessThanOrEqual(24);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("clamping an already-clamped value is idempotent", () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true }),
        (size) => {
          const once = clampReaderFontSize(size);
          const twice = clampReaderFontSize(once);
          expect(twice).toBe(once);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("any sequence of increase/decrease from any starting value stays in bounds", () => {
    fc.assert(
      fc.property(
        fc.double({ min: -1e6, max: 1e6, noNaN: true, noDefaultInfinity: true }),
        fc.array(fc.integer({ min: -10, max: 10 }), { minLength: 1, maxLength: 20 }),
        (startSize, deltas) => {
          let current = clampReaderFontSize(startSize);
          for (const delta of deltas) {
            current = clampReaderFontSize(current + delta);
            expect(Number.isInteger(current)).toBe(true);
            expect(current).toBeGreaterThanOrEqual(15);
            expect(current).toBeLessThanOrEqual(24);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
