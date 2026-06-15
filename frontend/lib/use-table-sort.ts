import { useReducer, useCallback, useMemo } from "react";

/**
 * Sort state holding the active sort column and direction.
 * @property activeKey - The currently active sort column key (or null if no sort)
 * @property direction - Current sort direction
 * @property defaultDirection - Default direction to apply when switching to a new column
 */
export type SortState = {
  activeKey: string | null;
  direction: "asc" | "desc";
  defaultDirection: "asc" | "desc";
};

/**
 * Column configuration with a default direction.
 */
export type SortableColumn = {
  key: string;
  defaultDirection?: "asc" | "desc";
};

/**
 * Sort action for the reducer.
 */
export type SortAction = {
  type: "setSortKey";
  key: string;
  columns: SortableColumn[];
};

/**
 * Pure reducer for sort state.
 * - Activating the same column inverts direction
 * - Activating a different column switches the active key and applies that column's default direction
 */
export function sortReducer(state: SortState, action: SortAction): SortState {
  if (action.type !== "setSortKey") {
    return state;
  }

  const { key, columns } = action;
  const column = columns.find((c) => c.key === key);
  const columnDefault = column?.defaultDirection ?? state.defaultDirection;

  // If same key, invert direction
  if (key === state.activeKey) {
    return {
      ...state,
      direction: state.direction === "asc" ? "desc" : "asc",
    };
  }

  // Different key: switch to that column with its default direction
  return {
    activeKey: key,
    direction: columnDefault,
    defaultDirection: columnDefault,
  };
}

/**
 * Initial sort state.
 */
export const initialSortState: SortState = {
  activeKey: null,
  direction: "asc",
  defaultDirection: "asc",
};

/**
 * Compare two rows by the active column.
 * Returns negative if a < b, positive if a > b, 0 if equal.
 * Handles null, undefined, numbers, and strings.
 * Preserves original relative order for equal keys (stable).
 */
export function compareRows<T extends Record<string, unknown>>(
  rows: T[],
  activeKey: string | null,
  direction: "asc" | "desc"
): (a: T, b: T) => number {
  if (!activeKey) {
    // No active sort key, preserve original order
    return () => 0;
  }

  return (a: T, b: T): number => {
    const aVal = a[activeKey];
    const bVal = b[activeKey];

    // Handle null/undefined values - push them to the end
    if (aVal == null && bVal == null) return 0;
    if (aVal == null) return 1;
    if (bVal == null) return -1;

    let comparison = 0;

    // String comparison
    if (typeof aVal === "string" && typeof bVal === "string") {
      comparison = aVal.localeCompare(bVal);
    }
    // Number comparison
    else if (typeof aVal === "number" && typeof bVal === "number") {
      comparison = aVal - bVal;
    }
    // Fallback: convert to string
    else {
      comparison = String(aVal).localeCompare(String(bVal));
    }

    // Apply direction
    return direction === "asc" ? comparison : -comparison;
  };
}

/**
 * Sort rows by the active column using a stable sort.
 * Returns a new sorted array without mutating the original.
 */
export function sortRows<T extends Record<string, unknown>>(
  rows: T[],
  activeKey: string | null,
  direction: "asc" | "desc"
): T[] {
  if (!activeKey) {
    return [...rows];
  }

  const comparator = compareRows(rows, activeKey, direction);

  // Create a stable sort by adding original index to compare
  const indexedRows = rows.map((row, index) => ({ row, index }));
  const sorted = [...indexedRows].sort((a, b) => {
    const cmp = comparator(a.row, b.row);
    // If values are equal, preserve original order (stable sort)
    if (cmp === 0) {
      return a.index - b.index;
    }
    return cmp;
  });

  return sorted.map((item) => item.row);
}

/**
 * Hook for table sorting.
 * Provides sort state, setSortKey action, and row sorting utilities.
 */
export function useTableSort<T extends Record<string, unknown>>(
  initialColumns: SortableColumn[] = []
) {
  const [sortState, dispatch] = useReducer(sortReducer, initialSortState);

  const setSortKey = useCallback(
    (key: string) => {
      dispatch({ type: "setSortKey", key, columns: initialColumns });
    },
    [initialColumns]
  );

  const sortedRows = useCallback(
    (rows: T[]) => sortRows(rows, sortState.activeKey, sortState.direction),
    [sortState.activeKey, sortState.direction]
  );

  // Memoized comparator for external use
  const compareRowsFn = useMemo(
    () => compareRows<T>,
    [sortState.activeKey, sortState.direction]
  );

  return {
    sortState,
    setSortKey,
    sortedRows,
    compareRows: compareRowsFn,
  };
}