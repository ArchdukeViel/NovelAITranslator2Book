import { cn } from "@/lib/utils";

interface ChipProps {
  label: string;
  className?: string;
}

export function GenreChip({ className, label }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground",
        className
      )}
    >
      {label}
    </span>
  );
}

export function TagChip({ className, label }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border/70 px-2.5 py-1 text-xs font-medium text-muted-foreground",
        className
      )}
    >
      {label}
    </span>
  );
}
