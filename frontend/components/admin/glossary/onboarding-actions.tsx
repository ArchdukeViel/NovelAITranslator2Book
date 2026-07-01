"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";

type Props = {
  novelId: string;
  bootstrapCandidateCount: number;
  actionPending?: boolean;
  onReviewGlossary?: () => void;
  onApproveGlossary?: () => void;
  onSkipGlossary?: () => void;
};

export function GlossaryOnboardingActions({
  novelId,
  bootstrapCandidateCount,
  actionPending = false,
  onReviewGlossary,
  onApproveGlossary,
  onSkipGlossary
}: Props) {
  const hasCandidates = bootstrapCandidateCount > 0;

  return (
    <div className="mt-3 rounded-md border bg-background p-3">
      <div className="text-xs uppercase text-muted-foreground">Glossary readiness</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {hasCandidates ? (
          <>
            <Link
              className="inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
              href={`/admin/novels/${encodeURIComponent(novelId)}/glossary`}
            >
              Review glossary before translating
            </Link>
            <Button size="sm" onClick={onApproveGlossary} disabled={actionPending}>
              Approve all and set ready
            </Button>
          </>
        ) : null}
        <Button size="sm" variant="outline" onClick={onSkipGlossary} disabled={actionPending}>
          Skip glossary for now
        </Button>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">
        {hasCandidates ? `${bootstrapCandidateCount} candidate term(s) detected.` : "No candidate terms were detected during onboarding."}
      </div>
    </div>
  );
}