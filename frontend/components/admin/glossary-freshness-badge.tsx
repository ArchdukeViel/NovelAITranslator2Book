import { Badge } from "@/components/ui/badge";

export function GlossaryFreshnessBadge({
  freshness,
  staleReason,
  currentRevision,
  versionRevision,
}: {
  freshness?: string | null;
  staleReason?: string | null;
  currentRevision?: number | null;
  versionRevision?: number | null;
}) {
  if (!freshness || freshness === "unknown") {
    return null;
  }

  if (freshness === "fresh") {
    return <Badge tone="green">Fresh</Badge>;
  }

  if (freshness === "stale") {
    const reasonLabel =
      staleReason === "revision_mismatch"
        ? `v${versionRevision} → v${currentRevision}`
        : staleReason === "hash_mismatch"
          ? "hash changed"
          : staleReason || "stale";

    return <Badge tone="amber" title={`Stale reason: ${staleReason || "unknown"}`}>Stale ({reasonLabel})</Badge>;
  }

  if (freshness === "legacy_unknown") {
    return <Badge tone="neutral" title="No glossary revision metadata on this version">Legacy</Badge>;
  }

  return null;
}
