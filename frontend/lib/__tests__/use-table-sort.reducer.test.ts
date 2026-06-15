import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { sortReducer, SortState, SortableColumn } from "../use-table-sort";

// Feature: admin-ui-rework, Property 8: Sort reducer toggles direction or switches column with default direction

describe("sortReducer", () => {
  const defaultColumns: SortableColumn[] = [
    { key: "name", defaultDirection: "asc" },
    { key: "date", defaultDirection: "desc" },
    { key: "count", defaultDirection: "asc" },
  ];

  // Property 8: Sort reducer toggles direction or switches column with default direction
  it("toggles direction when activating the same column", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.constant("name"), fc.constant("date"), fc.constant("count")),
        fc.oneof(fc.constant<"asc" | "desc">("asc"), fc.constant<"asc" | "desc">("desc")),
        fc.oneof(fc.constant<"asc" | "desc">("asc"), fc.constant<"asc" | "desc">("desc")),
        (key, direction, defaultDirection) => {
          const state: SortState = { activeKey: key, direction, defaultDirection };
          const newState = sortReducer(state, { type: "setSortKey", key, columns: defaultColumns });

          // When activating the same column, direction should invert
          expect(newState.activeKey).toBe(key);
          expect(newState.direction).toBe(direction === "asc" ? "desc" : "asc");
        }
      ),
      { numRuns: 100 }
    );
  });

  it("switches column and applies default direction when activating a different column", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.constant("name"), fc.constant("date"), fc.constant("count")),
        fc.oneof(fc.constant<"asc" | "desc">("asc"), fc.constant<"asc" | "desc">("desc")),
        fc.oneof(fc.constant<"asc" | "desc">("asc"), fc.constant<"asc" | "desc">("desc")),
        fc.oneof(fc.constant("name"), fc.constant("date"), fc.constant("count")),
        (currentKey, direction, defaultDirection, newKey) => {
          // Skip if same key (that's the toggle case, tested above)
          if (currentKey === newKey) {
            return true;
          }

          const state: SortState = { activeKey: currentKey, direction, defaultDirection };
          const newState = sortReducer(state, { type: "setSortKey", key: newKey, columns: defaultColumns });

          // When activating a different column, switch to that column with its default direction
          // Find the column's default direction
          const column = defaultColumns.find(c => c.key === newKey);
          const expectedDirection = column?.defaultDirection ?? "asc";

          expect(newState.activeKey).toBe(newKey);
          expect(newState.direction).toBe(expectedDirection);
        }
      ),
      { numRuns: 100 }
    );
  });

  it("preserves state for unknown action type", () => {
    const state: SortState = {
      activeKey: "name",
      direction: "asc",
      defaultDirection: "asc",
    };

    // @ts-expect-error - testing unknown action type
    const newState = sortReducer(state, { type: "unknown", key: "name", columns: defaultColumns });

    expect(newState).toEqual(state);
  });
});