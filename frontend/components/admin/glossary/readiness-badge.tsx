"use client";

import { BookMarked } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { GlossaryReadinessStatus } from "@/lib/api-types";
import { cn } from "@/lib/utils";

type Props = {
  novelId: string;
  glossaryStatus?: GlossaryReadinessStatus | string | null;
  glossaryRevision?: number | null;
  glossaryPendingCount?: number | null;
  compact?: boolean;
};

export function ReadinessBadge({
  novelId,
  glossaryStatus,
  glossaryRevision = 0,
  glossaryPendingCount = 0,
  compact = false
}: Props) {
  const status = glossaryStatus || "glossary_pending";
  if (status === "glossary_ready") {
    return <Badge tone="green">Glossary r{glossaryRevision ?? 0}</Badge>;
  }
  if (status === "glossary_skipped") {
    return <Badge tone="neutral">Glossary skipped</Badge>;
  }
  const label = compact
    ? `Glossary pending${glossaryPendingCount ? ` (${glossaryPendingCount})` : ""}`
    : `Glossary pending${glossaryPendingCount ? `: ${glossaryPendingCount} to review` : ""}`;
  return (
    <Link
      className={cn("inline-flex items-center gap-1.5 rounded-md text-xs font-medium")}
      href={`/admin/novels/${encodeURIComponent(novelId)}/glossary`}
    >
      <Badge tone="amber">
        <BookMarked className="h-3.5 w-3.5" />
        {label}
      </Badge>
    </Link>
  );
}
