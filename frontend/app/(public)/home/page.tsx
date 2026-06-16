"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Clock, FileText, Star, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { NovelCard } from "@/components/public/novel-card";

// Preview data - clearly labeled as such per design contract
const PREVIEW_NOVELS = [
  {
    novel_id: "preview-1",
    slug: "preview-novel-1",
    title: "The Reincarnated Sage's Quiet Life",
    author: "Tanaka Yuki",
    language: "Japanese",
    status: "Ongoing",
    chapter_count: 42,
    translated_count: 15,
  },
  {
    novel_id: "preview-2",
    slug: "preview-novel-2",
    title: "Dungeon Core: Building a Sanctuary",
    author: "Kim Min-ho",
    language: "Korean",
    status: "Completed",
    chapter_count: 120,
    translated_count: 120,
  },
  {
    novel_id: "preview-3",
    slug: "preview-novel-3",
    title: "Chronicles of the Azure Sky",
    author: "Li Wei",
    language: "Chinese",
    status: "Ongoing",
    chapter_count: 305,
    translated_count: 89,
  },
];

export default function HomePage() {
  return (
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <section className="py-12 md:py-16">
        <div className="rounded-lg border border-border bg-card p-6 md:p-10">
          <div className="max-w-2xl">
            <h1 className="text-3xl font-semibold tracking-normal font-literary md:text-4xl">
              Read Translated Web Novels
            </h1>
            <p className="mt-3 text-base text-muted-foreground">
              Discover and enjoy high-quality translations of Japanese, Korean, and Chinese web novels.
              Sign in to save your progress, build your library, and request new titles.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/browse-novels"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                <BookOpen className="h-4 w-4" />
                Browse Novels
              </Link>
              <Link
                href="/request-novel"
                className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted"
              >
                <FileText className="h-4 w-4" />
                Request Novel
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Latest Updates Ticker */}
      <section className="mb-12">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold font-literary">Latest Updates</h2>
          <Link href="/browse-novels" className="text-sm text-accent hover:underline">
            View all <ArrowRight className="ml-1 inline h-3 w-3" />
          </Link>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {PREVIEW_NOVELS.map((novel) => (
            <Link
              key={novel.novel_id}
              href={`/novel/${novel.slug}`}
              className="group flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition-colors hover:border-accent/30"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                <BookOpen className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium group-hover:text-accent">
                  {novel.title}
                </p>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>Chapter {novel.translated_count} translated</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured / Trending Novels */}
      <section className="mb-12">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold font-literary">Featured Novels</h2>
          <Badge tone="neutral" className="text-xs">Preview Data</Badge>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          A curated selection of popular translations. Backend trending metrics are pending.
        </p>
        <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PREVIEW_NOVELS.map((novel) => (
            <NovelCard key={novel.novel_id} novel={novel} />
          ))}
        </div>
      </section>

      {/* Ranking Preview */}
      <section className="mb-16">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold font-literary">Ranking Preview</h2>
          <Link href="/ranking" className="text-sm text-accent hover:underline">
            View full ranking <ArrowRight className="ml-1 inline h-3 w-3" />
          </Link>
        </div>
        <div className="mt-4 rounded-lg border border-border bg-card">
          <div className="divide-y">
            {PREVIEW_NOVELS.map((novel, index) => (
              <Link
                key={novel.novel_id}
                href={`/novel/${novel.slug}`}
                className="group flex items-center gap-4 p-4 transition-colors hover:bg-muted/50"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 font-metadata text-sm font-medium text-accent">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium group-hover:text-accent">
                    {novel.title}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {novel.author} • {novel.language}
                  </p>
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Star className="h-3 w-3" />
                  <span>Preview</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
