import { cn } from "@/lib/utils";

export function Metric({
  label,
  value,
  accent = "primary"
}: {
  label: string;
  value: string | number;
  accent?: "primary" | "amber" | "violet" | "red";
}) {
  const accents = {
    primary: "border-l-primary",
    amber: "border-l-amber-500",
    violet: "border-l-primary/60",
    red: "border-l-destructive"
  };

  return (
    <div className={cn("rounded-xl border border-border/70 border-l-4 bg-card/70 p-4 shadow-card", accents[accent])}>
      <div className="font-metadata text-xs font-medium uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-foreground">{value}</div>
    </div>
  );
}
