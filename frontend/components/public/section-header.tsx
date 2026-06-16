import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface SectionHeaderProps {
  actionHref?: string;
  actionLabel?: string;
  description?: string;
  eyebrow?: string;
  title: string;
}

export function SectionHeader({
  actionHref,
  actionLabel,
  description,
  eyebrow,
  title,
}: SectionHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && (
          <p className="font-metadata text-xs uppercase tracking-[0.18em] text-accent">
            {eyebrow}
          </p>
        )}
        <h2 className="mt-1 text-xl font-semibold font-literary">{title}</h2>
        {description && (
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actionHref && actionLabel && (
        <Link
          href={actionHref}
          className="inline-flex items-center gap-1 text-sm text-accent transition-colors hover:text-foreground"
        >
          {actionLabel}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}
