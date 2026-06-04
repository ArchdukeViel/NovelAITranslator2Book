"use client";

import * as React from "react";

export type SortDirection = "asc" | "desc";

export function compareSortableValues(leftValue: unknown, rightValue: unknown, direction: SortDirection): number {
  const multiplier = direction === "asc" ? 1 : -1;
  if (typeof leftValue === "number" && typeof rightValue === "number") {
    return (leftValue - rightValue) * multiplier;
  }
  return String(leftValue ?? "").localeCompare(String(rightValue ?? "")) * multiplier;
}

export function useSortableTable<TKey extends string>(initialKey: TKey, initialDirection: SortDirection = "asc") {
  const [sortKey, setSortKey] = React.useState<TKey>(initialKey);
  const [sortDirection, setSortDirection] = React.useState<SortDirection>(initialDirection);

  const handleSort = React.useCallback((key: TKey, nextDirection: SortDirection = "asc") => {
    setSortKey((currentKey) => {
      if (currentKey === key) {
        setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
        return currentKey;
      }
      setSortDirection(nextDirection);
      return key;
    });
  }, []);

  const sortIndicator = React.useCallback(
    (key: TKey) => {
      if (key !== sortKey) {
        return "";
      }
      return sortDirection === "asc" ? " ^" : " v";
    },
    [sortDirection, sortKey]
  );

  return { sortKey, sortDirection, setSortKey, setSortDirection, handleSort, sortIndicator };
}
