// Feature: public-reader-rework, Property 20: Next-page control visibility matches the pagination arithmetic
// **Validates: Requirements 3.6**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { hasNextPage } from "@/lib/public-format";

describe("Property 20: Next-page control visibility matches the pagination arithmetic", () => {
  it("returns true when page * page_size < total", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10000 }),
        fc.integer({ min: 1, max: 10000 }),
        fc.integer({ min: 1, max: 1000 }),
        (total, page, page_size) => {
          fc.pre(page * page_size < total);
          expect(hasNextPage(total, page, page_size)).toBe(true);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("returns false when page * page_size >= total", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 10000 }),
        fc.integer({ min: 1, max: 10000 }),
        fc.integer({ min: 1, max: 1000 }),
        (total, page, page_size) => {
          fc.pre(page * page_size >= total);
          expect(hasNextPage(total, page, page_size)).toBe(false);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("result is equivalent to page * page_size < total for any non-negative integers", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 100000 }),
        fc.integer({ min: 0, max: 100000 }),
        fc.integer({ min: 0, max: 10000 }),
        (total, page, page_size) => {
          const expected = page * page_size < total;
          expect(hasNextPage(total, page, page_size)).toBe(expected);
        }
      ),
      { numRuns: 100 }
    );
  });
});
