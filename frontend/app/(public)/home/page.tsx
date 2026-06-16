"use client";

import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { GenreChip } from "@/components/public/genre-chip";
import { LatestUpdateRow } from "@/components/public/latest-update-row";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { NovelCard } from "@/components/public/novel-card";
import { RankingRow } from "@/components/public/ranking-row";
import { SectionHeader } from "@/components/public/section-header";

// Preview data - clearly labeled as such per design contract
const PREVIEW_NOVELS = [
  {
    novel_id: "preview-1",
    slug: "preview-novel-1",
    source_title: "è»¢ç”Ÿè³¢è€…ã®é™ã‹ãªæš®ã‚‰ã—",
    title: "The Reincarnated Sage's Quiet Life",
    author: "Tanaka Yuki",
    language: "Japanese",
    status: "Ongoing",
    chapter_count: 42,
    translated_count: 15,
    genres: ["Fantasy", "Slice of Life", "Slow Burn"],
    synopsis:
      "After a second life begins in the mountains, a former court mage chooses tea, quiet rain, and small mysteries over royal intrigue.",
  },
  {
    novel_id: "preview-2",
    slug: "preview-novel-2",
    source_title: "Dungeon Core: Building a Sanctuary",
    title: "Dungeon Core: Building a Sanctuary",
    author: "Kim Min-ho",
    language: "Korean",
    status: "Completed",
    chapter_count: 120,
    translated_count: 120,
    genres: ["Dungeon", "Found Family"],
    synopsis:
      "A living dungeon rebuilds itself as a shelter for wanderers, turning old traps into hearths and hidden gardens.",
  },
  {
    novel_id: "preview-3",
    slug: "preview-novel-3",
    source_title: "Chronicles of the Azure Sky",
    title: "Chronicles of the Azure Sky",
    author: "Li Wei",
    language: "Chinese",
    status: "Ongoing",
    chapter_count: 305,
    translated_count: 89,
    genres: ["Adventure", "Wuxia"],
    synopsis:
      "Across cloud roads and border towns, a courier follows a vanished constellation and the stories it leaves behind.",
  },
];

export default function HomePage() {
  const featuredNovel = PREVIEW_NOVELS[0];

  return (
    <main>
      <section
        className="relative isolate min-h-[85vh] overflow-hidden"
        aria-label="Featured Dokushodo novel"
      >
        <div
          className="absolute inset-0 -z-30 bg-cover bg-center opacity-35 dark:opacity-25"
          style={{
            backgroundImage:
              "url('https://images.unsplash.com/photo-1771893327514-842e33b8bf85?w=1600&h=900&fit=crop&auto=format')",
          }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 -z-20 bg-gradient-to-t from-background via-background/80 to-background/20"
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 -z-10 bg-gradient-to-r from-background via-background/75 to-transparent"
          aria-hidden="true"
        />

        <div className="mx-auto flex min-h-[85vh] max-w-7xl items-end px-4 pb-14 pt-24 sm:px-6 lg:px-8 lg:pb-20">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral" className="font-metadata text-xs">
                Preview Feature
              </Badge>
              <span className="font-metadata text-xs uppercase tracking-[0.2em] text-accent">
                Featured - Editor&apos;s Pick
              </span>
            </div>

            <h1 className="mt-5 max-w-2xl font-literary text-5xl font-medium leading-tight tracking-normal text-foreground md:text-7xl">
              {featuredNovel.source_title}
            </h1>
            <p className="mt-4 max-w-2xl font-literary text-2xl text-accent md:text-3xl">
              {featuredNovel.title}
            </p>

            <NovelMetadataRow
              className="mt-5"
              chapterCount={featuredNovel.chapter_count}
              translatedCount={featuredNovel.translated_count}
              source={featuredNovel.language}
              status={featuredNovel.status}
            />

            <div className="mt-5 flex flex-wrap gap-2">
              {featuredNovel.genres.map((genre) => (
                <GenreChip key={genre} label={genre} />
              ))}
            </div>

            <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
              {featuredNovel.synopsis}
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href={`/novel/${featuredNovel.slug}`}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                <BookOpen className="h-4 w-4" />
                Start Reading
              </Link>
              <Link
                href={`/novel/${featuredNovel.slug}`}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-accent/40 bg-background/70 px-5 text-sm font-medium text-accent backdrop-blur transition-colors hover:bg-accent/10"
              >
                View Details
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <div
            className="pointer-events-none absolute right-10 top-1/2 hidden -translate-y-1/2 font-literary text-6xl text-foreground/10 [writing-mode:vertical-rl] xl:block"
            aria-hidden="true"
          >
            ç•°ä¸–ç•Œã®ç‰©èªž
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <section className="py-14">
          <SectionHeader
            title="Latest Updates"
            actionHref="/browse-novels"
            actionLabel="View all"
          />
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {PREVIEW_NOVELS.map((novel) => (
              <LatestUpdateRow
                key={novel.novel_id}
                href={`/novel/${novel.slug}`}
                title={novel.title}
                sourceTitle={novel.source_title}
                chapterLabel={`Chapter ${novel.translated_count} translated`}
              />
            ))}
          </div>
        </section>

        <section className="mb-12">
          <SectionHeader
            eyebrow="Preview Data"
            title="Featured Novels"
            description="A preview selection of translated novel concepts. Backend trending metrics are pending."
          />
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {PREVIEW_NOVELS.map((novel) => (
              <NovelCard key={novel.novel_id} novel={novel} />
            ))}
          </div>
        </section>

        <section className="mb-16">
          <SectionHeader
            title="Ranking Preview"
            actionHref="/ranking"
            actionLabel="View full ranking"
          />
          <div className="mt-4 rounded-lg bg-card/70">
            <div className="divide-y">
              {PREVIEW_NOVELS.map((novel, index) => (
                <RankingRow
                  key={novel.novel_id}
                  href={`/novel/${novel.slug}`}
                  rank={index + 1}
                  title={novel.title}
                  meta={`${novel.author} / ${novel.language}`}
                />
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
