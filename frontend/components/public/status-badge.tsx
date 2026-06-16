import { Badge } from "@/components/ui/badge";

type StatusTone = "neutral" | "green" | "amber" | "red" | "blue";

function statusTone(status: string | null | undefined): StatusTone {
  const normalized = status?.trim().toLowerCase();

  switch (normalized) {
    case "ongoing":
    case "active":
    case "published":
      return "green";
    case "complete":
    case "completed":
      return "blue";
    case "hiatus":
    case "paused":
    case "pending":
      return "amber";
    case "rejected":
    case "failed":
    case "error":
      return "red";
    default:
      return "neutral";
  }
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  if (!status || status.trim() === "") {
    return null;
  }

  return (
    <Badge tone={statusTone(status)} className="font-metadata text-xs">
      {status}
    </Badge>
  );
}
