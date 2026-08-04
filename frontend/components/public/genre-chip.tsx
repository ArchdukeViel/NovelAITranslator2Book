import { cn } from "@/lib/utils";

interface ChipProps {
  label: string;
  labelJa?: string | null;
  className?: string;
  variant?: "primary" | "secondary" | "outline";
}

export function GenreChip({ className, label, labelJa, variant = "primary" }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  const variantStyles =
    variant === "primary"
      ? "bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20"
      : variant === "secondary"
      ? "bg-secondary text-secondary-foreground hover:bg-secondary/80"
      : "border border-border/70 text-muted-foreground hover:bg-muted";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
        variantStyles,
        className
      )}
      title={labelJa && labelJa !== label ? labelJa : undefined}
    >
      {label}
      {labelJa && labelJa !== label && (
        <span className="ml-1.5 opacity-70">{labelJa}</span>
      )}
    </span>
  );
}

export function TagChip({ className, label, labelJa, variant = "outline" }: ChipProps) {
  if (!label.trim()) {
    return null;
  }

  const variantStyles =
    variant === "outline"
      ? "border border-border/70 text-muted-foreground hover:border-foreground/30 hover:text-foreground"
      : variant === "secondary"
      ? "bg-muted text-muted-foreground hover:bg-muted/80"
      : "bg-primary/10 text-primary border border-primary/20";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
        variantStyles,
        className
      )}
      title={labelJa && labelJa !== label ? labelJa : undefined}
    >
      {label}
      {labelJa && labelJa !== label && (
        <span className="ml-1.5 opacity-70">{labelJa}</span>
      )}
    </span>
  );
}
