import * as React from "react";

export function LoadingRows({
  colSpan,
  label = "Loading...",
  rows = 3
}: {
  colSpan: number;
  label?: string;
  rows?: number;
}) {
  return (
    <>
      {Array.from({ length: rows }).map((_, index) => (
        <tr className="border-b last:border-0" key={index}>
          <td className="px-4 py-4 text-sm text-muted-foreground" colSpan={colSpan}>
            {index === 0 ? label : <span className="inline-block h-3 w-2/3 max-w-md rounded bg-muted" />}
          </td>
        </tr>
      ))}
    </>
  );
}
