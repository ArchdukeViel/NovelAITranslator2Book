"use client";

import { BookOpen } from "lucide-react";

import { cn } from "@/lib/utils";

const PALETTES = [
  {
    root: "bg-secondary text-secondary-foreground",
    wash: "from-primary/18 via-accent/10 to-transparent",
    mark: "border-primary/35 bg-primary/12 text-primary",
    rule: "bg-primary",
  },
  {
    root: "bg-card text-card-foreground",
    wash: "from-accent/18 via-secondary/70 to-transparent",
    mark: "border-accent/35 bg-accent/12 text-accent",
    rule: "bg-accent",
  },
  {
    root: "bg-muted text-foreground",
    wash: "from-foreground/10 via-secondary/70 to-transparent",
    mark: "border-border bg-background/40 text-muted-foreground",
    rule: "bg-foreground/30",
  },
] as const;

interface FallbackCoverProps {
  className?: string;
  genres?: string[] | null;
  language?: string | null;
  sourceTitle?: string | null;
  status?: string | null;
  title: string;
}

function hashText(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function initialsFor(value: string): string {
  const words = value
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) {
    return "本";
  }

  return words
    .slice(0, 2)
    .map((word) => Array.from(word)[0])
    .join("")
    .toUpperCase();
}

function cleanText(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed || null;
}

function displayMeta(language: string | null | undefined, status: string | null | undefined): string {
  const items = [
    cleanText(language)?.toUpperCase(),
    cleanText(status),
  ].filter(Boolean);
  return items.join(" / ") || "Dokushodo";
}

export function FallbackCover({
  className,
  genres,
  language,
  sourceTitle,
  status,
  title,
}: FallbackCoverProps) {
  const safeTitle = cleanText(title) ?? "Untitled novel";
  const safeSourceTitle = cleanText(sourceTitle);
  const subtitle = safeSourceTitle && safeSourceTitle !== safeTitle ? safeSourceTitle : null;
  const genreSeed = genres?.filter(Boolean).join("|") ?? "";
  const palette = PALETTES[hashText(`${safeTitle}|${subtitle ?? ""}|${genreSeed}`) % PALETTES.length];

  return (
    <div
      role="img"
      aria-label={`Generated Dokushodo bookplate for ${safeTitle}`}
      className={cn(
        "relative flex aspect-[2/3] h-full w-full overflow-hidden rounded-lg border border-border shadow-sm",
        palette.root,
        className
      )}
    >
      <div
        className={cn("absolute inset-0 bg-gradient-to-br", palette.wash)}
        aria-hidden="true"
      />
      <div
        className="absolute inset-y-0 left-0 w-[12%] border-r border-border/60 bg-background/20"
        aria-hidden="true"
      />
      <div
        className={cn("absolute inset-x-[12%] top-0 h-1", palette.rule)}
        aria-hidden="true"
      />
      <div
        className="absolute inset-x-[18%] top-[15%] h-px bg-border/70"
        aria-hidden="true"
      />
      <div
        className="absolute inset-x-[18%] bottom-[15%] h-px bg-border/70"
        aria-hidden="true"
      />

      <div className="relative z-10 flex h-full w-full flex-col justify-between px-6 py-7 text-center">
        <div className="flex items-center justify-between gap-3 font-metadata text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
          <span>{displayMeta(language, status)}</span>
          <BookOpen className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        </div>

        <div className="mx-auto flex max-w-[11rem] flex-col items-center gap-4">
          <span
            className={cn(
              "flex h-16 w-16 items-center justify-center rounded-md border font-literary text-xl font-medium shadow-sm",
              palette.mark
            )}
            aria-hidden="true"
          >
            {initialsFor(subtitle ?? safeTitle)}
          </span>
          <div>
            <p className="font-metadata text-[0.65rem] uppercase tracking-[0.18em] text-accent">
              Dokushodo
            </p>
            <p className="mt-3 line-clamp-5 font-literary text-base leading-snug text-foreground">
              {safeTitle}
            </p>
            {subtitle && (
              <p className="mt-2 line-clamp-2 font-literary text-xs leading-5 text-muted-foreground">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        <div className="min-h-4 font-metadata text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
          Reading plate
        </div>
      </div>
    </div>
  );
}
