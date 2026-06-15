// Feature: public-reader-rework, Property 14: Content width maps to a fixed maximum-width class
// **Validates: Requirements 6.5, 6.6**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { widthClass } from "@/lib/public-format";

const VALID_WIDTHS = ["compact", "comfortable", "wide"] as const;

describe("Property 14: Content width maps to a fixed maximum-width class", () => {
  it("for any valid width, the function returns exactly one mapped max-width class", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...VALID_WIDTHS),
        (width) => {
          const result = widthClass(width);
          // Result must be a non-empty string
          expect(typeof result).toBe("string");
          expect(result.length).toBeGreaterThan(0);
          // Result must start with "max-w-" (a Tailwind max-width class)
          expect(result).toMatch(/^max-w-.+$/);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("the returned class is always a single string with no spaces", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...VALID_WIDTHS),
        (width) => {
          const result = widthClass(width);
          // Must contain no whitespace (single class token)
          expect(result).not.toMatch(/\s/);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("different width inputs always produce different output classes (bijective mapping)", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...VALID_WIDTHS),
        fc.constantFrom(...VALID_WIDTHS),
        (widthA, widthB) => {
          if (widthA !== widthB) {
            expect(widthClass(widthA)).not.toBe(widthClass(widthB));
          } else {
            expect(widthClass(widthA)).toBe(widthClass(widthB));
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
