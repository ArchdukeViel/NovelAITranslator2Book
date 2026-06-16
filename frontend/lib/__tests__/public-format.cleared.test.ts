// Feature: public-reader-rework, Property 21: Clearing filters restores the unfiltered baseline
// **Validates: Requirements 3.5**

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { clearedCatalogParams } from "@/lib/public-format";
import type { CatalogParams } from "@/lib/public-types";

describe("Property 21: Clearing filters restores the unfiltered baseline", () => {
  it("for any active CatalogParams, clearedCatalogParams() returns the baseline with page=1, page_size=20, and no filters", () => {
    fc.assert(
      fc.property(
        fc.record({
          q: fc.option(fc.string({ minLength: 0, maxLength: 100 }), { nil: undefined }),
          status: fc.option(fc.string({ minLength: 0, maxLength: 50 }), { nil: undefined }),
          sort_by: fc.option(fc.constantFrom("added_at", "title", "chapter_count"), { nil: undefined }),
          order: fc.option(fc.constantFrom("asc", "desc"), { nil: undefined }),
          min_chapters: fc.option(fc.integer({ min: 0, max: 500 }), { nil: undefined }),
          max_chapters: fc.option(fc.integer({ min: 0, max: 1000 }), { nil: undefined }),
          page: fc.option(fc.integer({ min: 1, max: 1000 }), { nil: undefined }),
          page_size: fc.option(fc.integer({ min: 1, max: 100 }), { nil: undefined }),
        }) as fc.Arbitrary<CatalogParams>,
        (_activeParams: CatalogParams) => {
          const cleared = clearedCatalogParams();

          // Must have page=1 and page_size=20
          expect(cleared.page).toBe(1);
          expect(cleared.page_size).toBe(20);

          // Must not have any filter fields (undefined or absent)
          expect(cleared.q).toBeUndefined();
          expect(cleared.status).toBeUndefined();
          expect(cleared.sort_by).toBeUndefined();
          expect(cleared.order).toBeUndefined();
          expect(cleared.min_chapters).toBeUndefined();
          expect(cleared.max_chapters).toBeUndefined();
        }
      ),
      { numRuns: 100 }
    );
  });

  it("the cleared result has no filter properties set regardless of input", () => {
    fc.assert(
      fc.property(
        fc.record({
          q: fc.option(fc.stringOf(fc.char(), { minLength: 1, maxLength: 80 }), { nil: undefined }),
          status: fc.option(fc.constantFrom("ongoing", "completed", "hiatus"), { nil: undefined }),
          sort_by: fc.option(fc.constantFrom("added_at", "title", "chapter_count"), { nil: undefined }),
          order: fc.option(fc.constantFrom("asc", "desc"), { nil: undefined }),
          page: fc.option(fc.integer({ min: 1, max: 500 }), { nil: undefined }),
          page_size: fc.option(fc.constantFrom(10, 20, 50), { nil: undefined }),
        }) as fc.Arbitrary<CatalogParams>,
        (_activeParams: CatalogParams) => {
          const cleared = clearedCatalogParams();
          const keys = Object.keys(cleared);

          // Only page and page_size should be present
          expect(keys).not.toContain("q");
          expect(keys).not.toContain("status");
          expect(keys).not.toContain("sort_by");
          expect(keys).not.toContain("order");
          expect(keys).not.toContain("min_chapters");
          expect(keys).not.toContain("max_chapters");
        }
      ),
      { numRuns: 100 }
    );
  });

  it("calling clearedCatalogParams() multiple times always returns deep-equal values", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 10 }),
        (callCount: number) => {
          const results = Array.from({ length: callCount }, () => clearedCatalogParams());

          // All results must be deep-equal to the first
          for (let i = 1; i < results.length; i++) {
            expect(results[i]).toEqual(results[0]);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
