import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { sortRows, compareRows, SortableColumn } from "../use-table-sort";

// Feature: admin-ui-rework, Property 9: Sorting reorders rows consistently and stably by the active column

describe("sortRows", () => {
  const columns: SortableColumn[] = [
    { key: "name", defaultDirection: "asc" },
    { key: "count", defaultDirection: "asc" },
    { key: "date", defaultDirection: "desc" },
  ];

  // Helper to generate arbitrary rows with specified keys
  const rowArb = (key: string) =>
    fc.record({
      id: fc.integer(),
      [key]: fc.oneof(fc.string(), fc.integer(), fc.constant(null)),
    });

  // Property 9: Sorting reorders rows consistently and stably by the active column
  it("sorted output is a permutation of input", () => {
    fc.assert(
      fc.property(
        fc.array(rowArb("name").map((r) => ({ ...r, name: r.name as string | number | null })), { minLength: 0, maxLength: 20 }),
        fc.oneof(fc.constant<"name" | "count" | "date">("name"), fc.constant<"name" | "count" | "date">("count"), fc.constant<"name" | "count" | "date">("date")),
        fc.oneof(fc.constant<"asc" | "desc">("asc"), fc.constant<"asc" | "desc">("desc")),
        (rows, key, direction) => {
          const sorted = sortRows(rows, key, direction);

          // Output should have same length as input (permutation)
          expect(sorted.length).toBe(rows.length);

          // All original rows should be present (permutation check)
          const sortedIds = sorted.map((r) => (r as { id?: number }).id);
          const originalIds = rows.map((r) => (r as { id?: number }).id);
          expect(sortedIds.sort()).toEqual(originalIds.sort());
        }
      ),
      { numRuns: 100 }
    );
  });

  it("ascending sort orders by non-decreasing values", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.integer(),
            count: fc.oneof(fc.integer({ min: 0, max: 100 }), fc.constant(null)),
          }),
          { minLength: 1, maxLength: 20 }
        ),
        (rows) => {
          const sorted = sortRows(rows, "count", "asc");

          // Check non-decreasing order
          for (let i = 1; i < sorted.length; i++) {
            const prev = sorted[i - 1].count;
            const curr = sorted[i].count;

            if (prev != null && curr != null) {
              expect(prev).toBeLessThanOrEqual(curr);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("descending sort orders by non-increasing values", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.integer(),
            count: fc.oneof(fc.integer({ min: 0, max: 100 }), fc.constant(null)),
          }),
          { minLength: 1, maxLength: 20 }
        ),
        (rows) => {
          const sorted = sortRows(rows, "count", "desc");

          // Check non-increasing order
          for (let i = 1; i < sorted.length; i++) {
            const prev = sorted[i - 1].count;
            const curr = sorted[i].count;

            if (prev != null && curr != null) {
              expect(prev).toBeGreaterThanOrEqual(curr);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it("stable sort preserves original relative order for equal keys", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            id: fc.integer(),
            name: fc.oneof(fc.constant("A"), fc.constant("B"), fc.constant("C")),
          }),
          { minLength: 1, maxLength: 20 }
        ),
        (rows) => {
          // Add unique IDs to track original positions
          const rowsWithIndex = rows.map((r, i) => ({ ...r, _originalIndex: i }));

          const sorted = sortRows(rowsWithIndex, "name", "asc");

          // Group by name and check that original indices are in ascending order
          const nameGroups = new Map<string, number[]>();
          sorted.forEach((row) => {
            const name = row.name as string;
            if (!nameGroups.has(name)) {
              nameGroups.set(name, []);
            }
            nameGroups.get(name)!.push(row._originalIndex);
          });

          // For each group of equal values, original indices should be in ascending order
          nameGroups.forEach((indices) => {
            for (let i = 1; i < indices.length; i++) {
              expect(indices[i - 1]).toBeLessThanOrEqual(indices[i]);
            }
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  it("returns empty array when input is empty", () => {
    const sorted = sortRows([], "name", "asc");
    expect(sorted).toEqual([]);
  });

  it("returns copy of input when no active key", () => {
    const rows = [{ id: 1, name: "test" }];
    const sorted = sortRows(rows, null, "asc");
    expect(sorted).toEqual(rows);
    expect(sorted).not.toBe(rows); // Should be a copy
  });

  it("handles null and undefined values correctly", () => {
    const rows = [
      { id: 1, name: "banana" },
      { id: 2, name: null },
      { id: 3, name: "apple" },
      { id: 4, name: undefined },
      { id: 5, name: "cherry" },
    ];

    const sortedAsc = sortRows(rows, "name", "asc");
    // Null and undefined should be pushed to the end
    expect(sortedAsc[0].name).toBe("apple");
    expect(sortedAsc[1].name).toBe("banana");
    expect(sortedAsc[2].name).toBe("cherry");
    // null/undefined at the end (order among them may vary)
    expect(sortedAsc[3].name).toBeFalsy();
    expect(sortedAsc[4].name).toBeFalsy();
  });

  it("handles numeric values correctly", () => {
    const rows = [
      { id: 1, count: 5 },
      { id: 2, count: 1 },
      { id: 3, count: 10 },
      { id: 4, count: 3 },
    ];

    const sortedAsc = sortRows(rows, "count", "asc");
    expect(sortedAsc.map((r) => r.count)).toEqual([1, 3, 5, 10]);

    const sortedDesc = sortRows(rows, "count", "desc");
    expect(sortedDesc.map((r) => r.count)).toEqual([10, 5, 3, 1]);
  });
});