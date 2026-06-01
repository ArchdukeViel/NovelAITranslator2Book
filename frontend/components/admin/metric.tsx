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
    amber: "border-l-secondary",
    violet: "border-l-accent",
    red: "border-l-destructive"
  };

  return (
    <div className={cn("rounded-lg border border-l-4 bg-card p-4", accents[accent])}>
      <div className="text-xs font-medium uppercase text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value}</div>
    </div>
  );
}
