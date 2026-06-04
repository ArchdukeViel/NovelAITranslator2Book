import * as React from "react";

import { cn } from "@/lib/utils";

export function TableCheckbox({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("table-checkbox", className)} type="checkbox" {...props} />;
}
