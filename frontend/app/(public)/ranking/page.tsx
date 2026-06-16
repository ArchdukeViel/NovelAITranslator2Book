"use client";

import { useState } from "react";
import Link from "next/link";
import { BookOpen, Star, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type RankingPeriod = "daily" | "weekly" | "monthly" | "all-time";

const PERIODS: { value: RankingPeriod; label: string }[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "all-time", label: "All Time" },
];

// Preview data - clearly labeled as pending backend metrics
const PREVIEW_RANKINGS = [
  {
    slug: "preview-novel-1",
    title: "The Reincarnated Sage's Quiet Life",
    author: "Tanaka Yuki",
    views: "12.5k",
  },
  {
    slug: "preview-novel-2",
    title: "Dungeon Core: Building a Sanctuary",
    author: "Kim Min-ho",
    views: "9.2k",
  },
  {
    slug: "preview-novel-3",
    title: "Chronicles of the Azure Sky",
    author: "Li Wei",
    views: "8.1k",
  },
  {
    slug: "preview-novel-4",
    title: "The Villainess Retires to the Countryside",
    author: "Sato Hana",
    views: "7.4k",
  },
  {
    slug: "preview-novel-5",
    title: "Magic Academy's Weakest Student",
    author: "Park Ji-sung",
    views: "6.8k",
  },
];

export default function RankingPage() {
  const [activePeriod, setActivePeriod] = useState<RankingPeriod>("weekly");

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal font-literary">Ranking</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Public ranking and trending views are planned, but the metrics and anti-abuse rules are not connected yet.
              The data below is preview scaffolding.
            </p>
          </div>
          <Badge tone="neutral" className="font-metadata">Preview Data</Badge>
        </div>
      </header>

      {/* Period Tabs */}
      <nav className="mb-6 flex gap-1 border-b border-border" aria-label="Ranking period">
        {PERIODS.map((period) => (
          <button
            key={period.value}
            type="button"
            onClick={() => setActivePeriod(period.value)}
            className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              activePeriod === period.value
                ? "border-accent text-accent"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            aria-current={activePeriod === period.value ? "page" : undefined}
          >
            {period.label}
          </button>
        ))}
      </nav>

      {/* Ranking List */}
      <section className="rounded-lg border border-border bg-card">
        <div className="divide-y">
          {PREVIEW_RANKINGS.map((novel, index) => (
            <Link
              key={novel.slug}
              href={`/novels/${novel.slug}`}
              className="group flex items-center gap-4 p-4 transition-colors hover:bg-muted/50"
            >
              {/* Ranking Number */}
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent/10 font-metadata text-lg font-medium text-accent">
                {index + 1}
              </span>

              {/* Novel Info */}
              <div className="min-w-0 flex-1">
                <p className="truncate text-base font-medium font-literary group-hover:text-accent">
                  {novel.title}
                </p>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {novel.author}
                </p>
              </div>

              {/* Metrics (Preview) */}
              <div className="hidden shrink-0 items-center gap-1.5 text-sm text-muted-foreground sm:flex">
                <TrendingUp className="h-4 w-4" />
                <span className="font-metadata">{novel.views}</span>
                <span className="text-xs">views</span>
              </div>

              {/* Action */}
              <div className="shrink-0">
                <span className="inline-flex items-center gap-1.5 text-sm text-primary group-hover:text-accent">
                  <BookOpen className="h-4 w-4" />
                  <span className="hidden sm:inline">Read</span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Footer note */}
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Real-time ranking metrics will be available once the backend aggregation contract is finalized.
      </p>
    </main>
  );
}
