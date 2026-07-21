import { BookOpen } from "lucide-react";
import Image from "next/image";

import { cn } from "@/lib/utils";

const COVER_ASSETS = {
  archive: "/assets/dokushodo/covers/cover-archive.png",
  completed: "/assets/dokushodo/covers/cover-completed.png",
  fantasy: "/assets/dokushodo/covers/cover-fantasy.png",
  mystery: "/assets/dokushodo/covers/cover-mystery.png",
} as const;

const PALETTES = [
  {
    root: "text-secondary-foreground",
    mark: "border-primary/35 bg-primary/12 text-primary",
    rule: "bg-primary",
  },
  {
    root: "text-card-foreground",
    mark: "border-accent/35 bg-accent/12 text-accent",
    rule: "bg-accent",
  },
  {
    root: "text-foreground",
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

function chooseCoverAsset(genres: string[] | null | undefined, status: string | null | undefined): string {
  const statusText = status?.toLowerCase() ?? "";
  if (statusText.includes("complete")) {
    return COVER_ASSETS.completed;
  }

  const genreText = genres?.join(" ").toLowerCase() ?? "";
  if (/(mystery|horror|supernatural|thriller|suspense)/u.test(genreText)) {
    return COVER_ASSETS.mystery;
  }
  if (/(fantasy|isekai|adventure|magic)/u.test(genreText)) {
    return COVER_ASSETS.fantasy;
  }

  return COVER_ASSETS.archive;
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
  const coverAsset = chooseCoverAsset(genres, status);

  return (
    <div
      role="img"
      aria-label={`Generated Dokushodo bookplate for ${safeTitle}`}
      className={cn(
        "relative flex aspect-[2/3] h-full w-full overflow-hidden rounded-lg border border-border bg-card shadow-sm",
        palette.root,
        className
      )}
    >
      <Image
        src={coverAsset}
        alt=""
        aria-hidden="true"
        fill
        sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
        className="absolute inset-0 h-full w-full object-cover"
      />
      <div
        className="absolute inset-0 bg-gradient-to-b from-background/20 via-background/45 to-background/90"
        aria-hidden="true"
      />
      <div
        className="absolute inset-y-0 left-0 w-[12%] border-r border-border/60 bg-background/30"
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
              "flex h-16 w-16 items-center justify-center rounded-md border font-literary text-xl font-medium shadow-sm backdrop-blur-[1px]",
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
