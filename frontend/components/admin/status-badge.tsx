import { Badge } from "@/components/ui/badge";

export function StatusBadge({ status }: { status?: string | null }) {
  const normalized = (status || "unknown").toLowerCase();
  const tone =
    normalized === "completed" || normalized === "approved" || normalized === "published"
      ? "green"
      : normalized === "running"
        ? "blue"
        : normalized === "failed" || normalized === "rejected"
          ? "red"
          : normalized === "pending" || normalized === "needs_review" || normalized.startsWith("paused")
            ? "amber"
            : "neutral";

  return <Badge tone={tone}>{normalized}</Badge>;
}
