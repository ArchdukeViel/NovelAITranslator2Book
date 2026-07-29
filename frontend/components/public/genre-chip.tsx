import { cn } from "@/lib/utils";

interface ChipProps {
  label: string;
  labelJa?: string | null;
  className?: string;
}

export function GenreChip({ className, label, labelJa }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground",
        className
      )}
      title={labelJa && labelJa !== label ? labelJa : undefined}
    >
      {label}
      {labelJa && labelJa !== label && (
        <span className="ml-1.5 text-secondary-foreground/60">{labelJa}</span>
      )}
    </span>
  );
}

export function TagChip({ className, label, labelJa }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border border-border/70 px-2.5 py-1 text-xs font-medium text-muted-foreground",
        className
      )}
      title={labelJa && labelJa !== label ? labelJa : undefined}
    >
      {label}
      {labelJa && labelJa !== label && (
        <span className="ml-1.5 text-muted-foreground/60">{labelJa}</span>
      )}
    </span>
  );
}
