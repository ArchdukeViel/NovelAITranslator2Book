"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody } from "@/components/ui/panel";
import { AuthGate } from "@/components/public/auth-gate";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { authorOrFallback } from "@/lib/public-format";
import type { PublicNovelSummary } from "@/lib/public-types";

interface NovelCardProps {
  novel: PublicNovelSummary;
}

export function NovelCard({ novel }: NovelCardProps) {
  return (
    <Panel className="h-full transition-colors hover:border-primary">
      <PanelBody>
        <Link href={`/novel/${encodeURIComponent(novel.slug)}`}>
          <div className="mb-3 flex items-center justify-between gap-2">
            <Badge tone="blue">
              {novel.translated_count} translated
            </Badge>
          </div>
          <h2 className="text-base font-semibold">
            {novel.title || novel.slug}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {authorOrFallback(novel.author)}
          </p>
        </Link>
        <div
          className="mt-3"
          onClick={(e) => e.preventDefault()}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation(); }}
        >
          <AuthGate fallback={null}>
            <SaveToLibrary slug={novel.slug} />
          </AuthGate>
        </div>
      </PanelBody>
    </Panel>
  );
}
