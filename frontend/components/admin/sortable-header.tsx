import * as React from "react";

import { cn } from "@/lib/utils";

export function SortableHeader<TKey extends string>({
  label,
  sortKey,
  activeKey,
  direction,
  onSort,
  className
}: {
  label: string;
  sortKey: TKey;
  activeKey: TKey;
  direction: "asc" | "desc";
  onSort: (key: TKey) => void;
  className?: string;
}) {
  const marker = activeKey === sortKey ? (direction === "asc" ? " ^" : " v") : "";

  return (
    <th className={cn("px-4 py-3", className)}>
      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => onSort(sortKey)}>
        {label}
        {marker}
      </button>
    </th>
  );
}
